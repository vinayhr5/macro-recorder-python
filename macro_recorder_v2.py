#!/usr/bin/env python3
# Macro Recorder v2 (Python) - Enhanced
# Additions over v1:
# - Multi-monitor template matching (search across all monitors)
# - Multi-scale template matching (user-configurable scales, ex: 0.85,0.9,1.0,1.1)
# - "Wait for Image" step with timeout (conditional flow)
# - Window restore (records active window geometry at start; optionally restores before playback)
# - UI controls for match threshold, scales, and monitor search
#
# Optional deps: pywinctl for window restore
# See README_v2.md for details.

import sys, json, time, base64, threading, webbrowser
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List

missing = []

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt
except Exception:
    print("PySide6 is required. pip install PySide6", file=sys.stderr)
    raise

# recording/playback deps
try:
    from pynput import mouse, keyboard
except Exception:
    missing.append("pynput (recording)")
try:
    import pyautogui
except Exception:
    missing.append("pyautogui (playback)")

# vision/ocr/screen
try:
    import mss, mss.tools
    HAVE_MSS = True
except Exception:
    HAVE_MSS = False
try:
    import numpy as np
    HAVE_NP = True
except Exception:
    HAVE_NP = False
try:
    import cv2
    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False
try:
    from PIL import Image
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False
try:
    import pytesseract
    HAVE_TESS = True
except Exception:
    HAVE_TESS = False

# window control (optional)
try:
    import pywinctl
    HAVE_PYWINCTL = True
except Exception:
    HAVE_PYWINCTL = False

@dataclass
class MacroEvent:
    etype: str
    ts: float
    data: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        return {"etype": self.etype, "ts": self.ts, "data": self.data}

    @staticmethod
    def from_json(obj: Dict[str, Any]) -> "MacroEvent":
        return MacroEvent(obj.get("etype",""), float(obj.get("ts",0.0)), obj.get("data",{}))

# ---------- helpers ----------

def b64_png_from_np(img_np: "np.ndarray") -> str:
    if not (HAVE_PIL and HAVE_NP): return ""
    import io
    if img_np.ndim == 2:
        mode = "L"
    elif img_np.shape[2] == 4:
        mode = "RGBA"
    else:
        mode = "RGB"
    im = Image.fromarray(img_np, mode=mode)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")

def np_from_b64_png(b64: str) -> Optional["np.ndarray"]:
    if not (HAVE_PIL and HAVE_NP): return None
    import io
    try:
        raw = base64.b64decode(b64.encode("ascii"))
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        return np.array(im)
    except Exception:
        return None

def screen_regions():
    """Yield (monitor_dict, np_image_bgra) for each monitor; primary first."""
    if not (HAVE_MSS and HAVE_NP):
        return
    with mss.mss() as sct:
        for i, mon in enumerate(sct.monitors[1:], start=1):
            img = sct.grab(mon)  # BGRA
            arr = np.array(img)
            yield mon, arr

def grab_region(x:int,y:int,w:int,h:int) -> Optional["np.ndarray"]:
    if not (HAVE_MSS and HAVE_NP): return None
    with mss.mss() as sct:
        mon = {"top": max(0,y), "left": max(0,x), "width": max(1,w), "height": max(1,h)}
        img = sct.grab(mon)
        return np.array(img)

def find_template_any_monitor(template_rgba: "np.ndarray", threshold: float, scales: List[float], search_all: bool=True) -> Optional[Tuple[int,int,float,float]]:
    """Return (abs_x, abs_y, score, scale) of best match or None."""
    if not (HAVE_CV2 and HAVE_NP and HAVE_MSS):
        return None
    best = (None, -1.0, 1.0, (0,0))  # (loc, score, scale, offset)
    for mon, arr in screen_regions():
        # restrict to first monitor if search_all is False
        if not search_all and (mon is not list(screen_regions())[0]):
            # This inefficient line would consume generator; instead handle separately:
            pass
    # Re-implement to avoid generator consumption:
    screens = []
    if not (HAVE_MSS and HAVE_NP):
        return None
    with mss.mss() as sct:
        mons = [sct.monitors[1]] if not search_all else sct.monitors[1:]
        for mon in mons:
            img = sct.grab(mon)
            screens.append((mon, np.array(img)))

    for mon, screen_bgra in screens:
        scr = cv2.cvtColor(screen_bgra, cv2.COLOR_BGRA2BGR)
        for sc in scales:
            try:
                if abs(sc - 1.0) > 1e-6:
                    tmpl = cv2.resize(template_rgba, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA if sc<1.0 else cv2.INTER_CUBIC)
                else:
                    tmpl = template_rgba
                if tmpl.shape[2] == 4:
                    tmpl = cv2.cvtColor(tmpl, cv2.COLOR_RGBA2BGR)
                res = cv2.matchTemplate(scr, tmpl, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                if max_val > best[1]:
                    best = (max_loc, max_val, sc, (mon["left"], mon["top"]))
            except Exception:
                continue

    loc, score, sc, offs = best
    if loc is None:
        return None
    if score >= threshold:
        abs_x = offs[0] + loc[0]
        abs_y = offs[1] + loc[1]
        return (abs_x, abs_y, score, sc)
    return None

# ---------- Recorder ----------

class GlobalRecorder(QtCore.QObject):
    event_recorded = QtCore.Signal(MacroEvent)
    stopped = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._last_ts = 0.0
        self._mouse_listener = None
        self._key_listener = None

    def start(self):
        if self._running: return
        self._running = True
        self._last_ts = time.time()

        def on_move(x,y):
            if not self._running: return False
            now = time.time(); dt = now - self._last_ts; self._last_ts = now
            self.event_recorded.emit(MacroEvent("mouse_move", dt, {"x":x,"y":y}))

        def on_click(x,y,button,pressed):
            if not self._running: return False
            now = time.time(); dt = now - self._last_ts; self._last_ts = now
            self.event_recorded.emit(MacroEvent("mouse_click", dt, {"x":x,"y":y,"button":str(button),"pressed":pressed}))

        def on_scroll(x,y,dx,dy):
            if not self._running: return False
            now = time.time(); dt = now - self._last_ts; self._last_ts = now
            self.event_recorded.emit(MacroEvent("mouse_scroll", dt, {"x":x,"y":y,"dx":dx,"dy":dy}))

        def on_press(key):
            if not self._running: return False
            now = time.time(); dt = now - self._last_ts; self._last_ts = now
            try:
                k = key.char if hasattr(key,"char") and key.char is not None else str(key)
            except Exception:
                k = str(key)
            self.event_recorded.emit(MacroEvent("key_down", dt, {"key":k}))

        def on_release(key):
            if not self._running: return False
            now = time.time(); dt = now - self._last_ts; self._last_ts = now
            try:
                k = key.char if hasattr(key,"char") and key.char is not None else str(key)
            except Exception:
                k = str(key)
            self.event_recorded.emit(MacroEvent("key_up", dt, {"key":k}))

        self._mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        self._key_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._mouse_listener.start(); self._key_listener.start()

    def stop(self):
        if not self._running: return
        self._running = False
        try:
            if self._mouse_listener: self._mouse_listener.stop()
            if self._key_listener: self._key_listener.stop()
        finally:
            self._mouse_listener = None
            self._key_listener = None
            self.stopped.emit()

# ---------- Region selector ----------

class RegionSelector(QtWidgets.QWidget):
    region_selected = QtCore.Signal(QtCore.QRect)
    def __init__(self):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._origin = None
        self._rect = QtCore.QRect()
        geo = QtGui.QGuiApplication.primaryScreen().geometry()
        self.setGeometry(geo)

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QtGui.QColor(0,0,0,80))
        pen = QtGui.QPen(Qt.white, 2, Qt.DashLine)
        p.setPen(pen); p.setBrush(QtGui.QColor(255,255,255,40))
        p.drawRect(self._rect)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._origin = ev.position().toPoint()
            self._rect = QtCore.QRect(self._origin, QtCore.QSize()); self.update()

    def mouseMoveEvent(self, ev):
        if self._origin:
            cur = ev.position().toPoint()
            self._rect = QtCore.QRect(self._origin, cur).normalized(); self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and not self._rect.isNull():
            self.region_selected.emit(self._rect); self.close()

# ---------- UI ----------

class MacroTable(QtWidgets.QTableWidget):
    HEADERS = ["#", "Type", "Delay (s)", "Details"]
    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)
        self.setAlternatingRowColors(True)

    def add_event(self, evt: MacroEvent):
        r = self.rowCount(); self.insertRow(r); self._fill(r, evt)

    def set_events(self, events: List[MacroEvent]):
        self.setRowCount(0)
        for i,e in enumerate(events):
            self.insertRow(i); self._fill(i, e)

    def _fill(self, row: int, evt: MacroEvent):
        it0 = QtWidgets.QTableWidgetItem(str(row+1))
        it1 = QtWidgets.QTableWidgetItem(evt.etype)
        it2 = QtWidgets.QTableWidgetItem(f"{evt.ts:.3f}")
        it3 = QtWidgets.QTableWidgetItem(json.dumps(evt.data, ensure_ascii=False))
        for it in (it0,it1,it2,it3):
            it.setFlags(it.flags() ^ Qt.ItemIsEditable)
        self.setItem(row,0,it0); self.setItem(row,1,it1); self.setItem(row,2,it2); self.setItem(row,3,it3)

    def refresh_indices(self):
        for r in range(self.rowCount()):
            self.item(r,0).setText(str(r+1))

class MousePathView(QtWidgets.QWidget):
    def __init__(self, provider, parent=None):
        super().__init__(parent); self._provider = provider
        self.setMinimumHeight(120)
    def paintEvent(self, ev):
        p = QtGui.QPainter(self); p.fillRect(self.rect(), self.palette().base())
        evts = self._provider()
        pts = [(e.data.get("x"), e.data.get("y")) for e in evts if e.etype == "mouse_move"]
        if len(pts) < 2: return
        xs=[x for x,_ in pts]; ys=[y for _,y in pts]
        minx,maxx, miny,maxy = min(xs),max(xs), min(ys),max(ys)
        w=max(1,maxx-minx); h=max(1,maxy-miny)
        r = self.rect().adjusted(8,8,-8,-8)
        qpts=[]
        for x,y in pts:
            nx = r.left() + (x-minx)/w * r.width()
            ny = r.top()  + (y-miny)/h * r.height()
            qpts.append(QtCore.QPointF(nx,ny))
        pen = QtGui.QPen(self.palette().highlight().color(), 2); p.setPen(pen)
        for i in range(len(qpts)-1): p.drawLine(qpts[i], qpts[i+1])
        p.setBrush(self.palette().highlight())
        p.drawEllipse(qpts[0],4,4); p.drawEllipse(qpts[-1],4,4)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Recorder v2 (Python)")
        self.resize(1200, 760)
        self.events: List[MacroEvent] = []
        self.recorder = GlobalRecorder()
        self.recorder.event_recorded.connect(self.on_event_recorded)
        self.recorder.stopped.connect(self.on_record_stopped)
        self.playing=False; self.stop_flag=False; self.play_thread=None

        # central UI
        cw = QtWidgets.QWidget(); self.setCentralWidget(cw)
        v = QtWidgets.QVBoxLayout(cw)

        # top controls
        row1 = QtWidgets.QHBoxLayout()
        self.btn_record = QtWidgets.QPushButton("● Record")
        self.btn_stop   = QtWidgets.QPushButton("⏹ Stop"); self.btn_stop.setEnabled(False)
        self.btn_play   = QtWidgets.QPushButton("▶ Play")
        self.btn_wait   = QtWidgets.QPushButton("+ Wait")
        self.btn_text   = QtWidgets.QPushButton("+ Type Text")
        self.btn_url    = QtWidgets.QPushButton("+ Open URL")
        self.btn_sshot  = QtWidgets.QPushButton("📸 Screenshot")
        self.btn_ocr    = QtWidgets.QPushButton("🔎 OCR Region")
        self.btn_waitimg= QtWidgets.QPushButton("+ Wait for Image")
        for b in [self.btn_record,self.btn_stop,self.btn_play,self.btn_wait,self.btn_text,self.btn_url,self.btn_sshot,self.btn_ocr,self.btn_waitimg]:
            row1.addWidget(b)
        row1.addStretch(1)
        v.addLayout(row1)

        # options
        row2 = QtWidgets.QHBoxLayout()
        self.chk_anchor = QtWidgets.QCheckBox("Smart Click (visual)")
        self.chk_anchor.setChecked(HAVE_CV2 and HAVE_MSS and HAVE_NP)
        self.chk_anchor.setEnabled(HAVE_CV2 and HAVE_MSS and HAVE_NP)
        self.chk_allmons= QtWidgets.QCheckBox("Search all monitors")
        self.chk_allmons.setChecked(True)
        row2.addWidget(self.chk_anchor)
        row2.addWidget(self.chk_allmons)
        row2.addSpacing(12)
        row2.addWidget(QtWidgets.QLabel("Match threshold:"))
        self.spn_thresh = QtWidgets.QDoubleSpinBox(); self.spn_thresh.setRange(0.5, 0.99); self.spn_thresh.setSingleStep(0.01); self.spn_thresh.setValue(0.87)
        row2.addWidget(self.spn_thresh)
        row2.addSpacing(12)
        row2.addWidget(QtWidgets.QLabel("Scales:"))
        self.ed_scales = QtWidgets.QLineEdit("0.85,0.9,1.0,1.1,1.2")
        self.ed_scales.setToolTip("Comma-separated scale factors for template matching")
        row2.addWidget(self.ed_scales)
        row2.addSpacing(12)
        self.chk_restore = QtWidgets.QCheckBox("Restore active window before playback")
        self.chk_restore.setChecked(HAVE_PYWINCTL)
        self.chk_restore.setEnabled(HAVE_PYWINCTL)
        row2.addWidget(self.chk_restore)
        row2.addStretch(1)
        v.addLayout(row2)

        # table
        self.table = MacroTable(); v.addWidget(self.table)

        # edit row
        row3 = QtWidgets.QHBoxLayout()
        self.btn_up=QtWidgets.QPushButton("Move Up")
        self.btn_dn=QtWidgets.QPushButton("Move Down")
        self.btn_edelay=QtWidgets.QPushButton("Edit Delay")
        self.btn_etext=QtWidgets.QPushButton("Edit Text/URL")
        self.btn_del=QtWidgets.QPushButton("Delete")
        self.btn_clear=QtWidgets.QPushButton("Clear All")
        for b in [self.btn_up,self.btn_dn,self.btn_edelay,self.btn_etext,self.btn_del]:
            row3.addWidget(b)
        row3.addStretch(1)
        row3.addWidget(self.btn_clear)
        v.addLayout(row3)

        # path view
        self.path = MousePathView(lambda: [e for e in self.events if e.etype=="mouse_move"])
        v.addWidget(self.path)

        # status
        self.status = QtWidgets.QStatusBar(); self.setStatusBar(self.status)
        if missing: self.status.showMessage("Missing optional deps: " + ", ".join(missing))

        self._build_menus()

        # connect
        self.btn_record.clicked.connect(self.start_record)
        self.btn_stop.clicked.connect(self.stop_all)
        self.btn_play.clicked.connect(self.start_play)
        self.btn_wait.clicked.connect(self.add_wait)
        self.btn_text.clicked.connect(self.add_text)
        self.btn_url.clicked.connect(self.add_url)
        self.btn_sshot.clicked.connect(self.add_screenshot)
        self.btn_ocr.clicked.connect(self.add_ocr)
        self.btn_waitimg.clicked.connect(self.add_wait_image)

        self.btn_up.clicked.connect(self.move_up)
        self.btn_dn.clicked.connect(self.move_down)
        self.btn_edelay.clicked.connect(self.edit_delay)
        self.btn_etext.clicked.connect(self.edit_text)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_clear.clicked.connect(self.clear_all)

    def _build_menus(self):
        bar = self.menuBar()
        fm = bar.addMenu("&File")
        a_new = fm.addAction("New"); a_open=fm.addAction("Open..."); a_save=fm.addAction("Save..."); fm.addSeparator(); a_quit=fm.addAction("Quit")
        a_new.triggered.connect(self.clear_all); a_open.triggered.connect(self.load_macro); a_save.triggered.connect(self.save_macro); a_quit.triggered.connect(self.close)
        hm = bar.addMenu("&Help")
        a_about = hm.addAction("About"); a_about.triggered.connect(lambda: QtWidgets.QMessageBox.information(self,"About",
            "Macro Recorder v2\nMulti-monitor, multi-scale visual anchors, Wait-for-Image step, window restore."))

    # utilities
    def _current_row(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        return rows[0] if rows else -1

    def _parse_scales(self) -> List[float]:
        try:
            vals=[float(x.strip()) for x in self.ed_scales.text().split(",") if x.strip()]
            vals = [v for v in vals if 0.2 <= v <= 3.0]
            return vals or [1.0]
        except Exception:
            return [1.0]

    # recording
    def start_record(self):
        if "pynput (recording)" in missing:
            QtWidgets.QMessageBox.warning(self,"Missing","Install pynput to record: pip install pynput"); return
        if self.playing:
            QtWidgets.QMessageBox.warning(self,"Busy","Stop playback first."); return
        self.events.clear(); self.table.set_events(self.events); self.path.update()
        # Capture active window state (optional)
        if HAVE_PYWINCTL:
            try:
                w = pywinctl.getActiveWindow()
                if w:
                    g = w.getClientFrame() if hasattr(w,"getClientFrame") else w.getWindowRect()
                    data = {"title": w.title, "x": g[0], "y": g[1], "w": g[2]-g[0], "h": g[3]-g[1]}
                    self.events.append(MacroEvent("window_restore", 0.05, data)); self.table.add_event(self.events[-1])
            except Exception:
                pass
        self.status.showMessage("Recording... Press Stop to finish.")
        self.btn_record.setEnabled(False); self.btn_stop.setEnabled(True); self.btn_play.setEnabled(False)
        self.recorder.start()

    def on_event_recorded(self, evt: MacroEvent):
        if evt.etype == "mouse_click" and evt.data.get("pressed") and self.chk_anchor.isChecked() and HAVE_MSS and HAVE_NP:
            x,y = int(evt.data["x"]), int(evt.data["y"])
            pad = 35
            img = grab_region(x-pad, y-pad, pad*2, pad*2)
            if img is not None:
                evt.data["anchor_b64"] = b64_png_from_np(img)
                evt.data["anchor_offset"] = [pad,pad]
        self.events.append(evt); self.table.add_event(evt)
        if evt.etype == "mouse_move": self.path.update()

    def on_record_stopped(self):
        self.status.showMessage(f"Recording stopped. {len(self.events)} events captured.", 5000)
        self.btn_record.setEnabled(True); self.btn_stop.setEnabled(False); self.btn_play.setEnabled(True)

    def stop_all(self):
        self.recorder.stop()
        if self.playing: self.stop_flag = True

    # add/edit steps
    def add_wait(self):
        val,ok = QtWidgets.QInputDialog.getDouble(self,"Add Wait","Delay (seconds):",0.5,0.0,600.0,2)
        if ok: self._add(MacroEvent("wait", float(val), {}))

    def add_text(self):
        txt,ok = QtWidgets.QInputDialog.getMultiLineText(self,"Add Text","Text:","")
        if ok and txt: self._add(MacroEvent("text", 0.1, {"text": txt}))

    def add_url(self):
        url,ok = QtWidgets.QInputDialog.getText(self,"Add Open URL","URL:","https://")
        if ok and url: self._add(MacroEvent("open_url", 0.1, {"url": url}))

    def add_screenshot(self):
        if not (HAVE_MSS and HAVE_PIL):
            QtWidgets.QMessageBox.warning(self,"Missing","Install mss and pillow for screenshots."); return
        ans = QtWidgets.QMessageBox.question(self,"Screenshot","Capture region? Yes = region, No = full screen")
        if ans == QtWidgets.QMessageBox.Yes:
            rect = self._select_region()
            if not rect: return
            x,y,w,h = rect; img = grab_region(x,y,w,h)
        else:
            # full primary
            with mss.mss() as sct:
                mon = sct.monitors[1]; img = np.array(sct.grab(mon))
        if img is None:
            QtWidgets.QMessageBox.warning(self,"Screenshot","Failed to capture."); return
        self._add(MacroEvent("screenshot", 0.1, {"image_b64": b64_png_from_np(img)}))
        self.status.showMessage("Screenshot step added.", 3000)

    def add_ocr(self):
        if not (HAVE_TESS and HAVE_MSS and HAVE_PIL):
            QtWidgets.QMessageBox.warning(self,"Missing","Needs pytesseract, mss, pillow, plus Tesseract binary on PATH."); return
        rect = self._select_region()
        if not rect: return
        x,y,w,h = rect
        self._add(MacroEvent("ocr_region", 0.1, {"x":x,"y":y,"w":w,"h":h}))
        self.status.showMessage("OCR step added.", 3000)

    def add_wait_image(self):
        if not (HAVE_MSS and HAVE_NP):
            QtWidgets.QMessageBox.warning(self,"Missing","Needs mss & numpy."); return
        rect = self._select_region()
        if not rect: return
        x,y,w,h = rect
        img = grab_region(x,y,w,h)
        if img is None:
            QtWidgets.QMessageBox.warning(self,"Wait for Image","Failed to capture region."); return
        b64 = b64_png_from_np(img)
        timeout,ok = QtWidgets.QInputDialog.getDouble(self,"Wait for Image","Timeout (seconds):",30.0,0.5,3600.0,1)
        if not ok: return
        evt = MacroEvent("wait_for_image", 0.0, {"anchor_b64": b64, "timeout": float(timeout)})
        self._add(evt)
        self.status.showMessage("Wait-for-Image step added.", 3000)

    def _select_region(self) -> Optional[Tuple[int,int,int,int]]:
        sel = RegionSelector()
        result = {}
        def on_sel(rect: QtCore.QRect): result["rect"]=rect
        sel.region_selected.connect(on_sel)
        sel.showFullScreen(); sel.activateWindow(); sel.raise_()
        loop = QtCore.QEventLoop()
        sel.destroyed.connect(loop.quit)
        sel.region_selected.connect(lambda _: loop.quit())
        loop.exec()
        rect = result.get("rect")
        if not rect: return None
        return rect.x(), rect.y(), rect.width(), rect.height()

    def _add(self, evt: MacroEvent):
        self.events.append(evt); self.table.add_event(evt); self.table.refresh_indices(); self.path.update()

    def edit_delay(self):
        r=self._current_row()
        if r<0: return
        evt=self.events[r]
        val,ok = QtWidgets.QInputDialog.getDouble(self,"Edit Delay","Delay (seconds) before this event:",evt.ts,0.0,600.0,3)
        if ok: evt.ts=float(val); self.table.set_events(self.events); self.table.selectRow(r)

    def edit_text(self):
        r=self._current_row()
        if r<0: return
        evt=self.events[r]
        if evt.etype=="text":
            txt,ok=QtWidgets.QInputDialog.getMultiLineText(self,"Edit Text","Text:",evt.data.get("text",""))
            if ok: evt.data["text"]=txt
        elif evt.etype=="open_url":
            url,ok=QtWidgets.QInputDialog.getText(self,"Edit URL","URL:", text=evt.data.get("url",""))
            if ok: evt.data["url"]=url
        else:
            QtWidgets.QMessageBox.information(self,"Edit","Select a 'text' or 'open_url' row.")
            return
        self.table.set_events(self.events); self.table.selectRow(r)

    def move_up(self):
        r=self._current_row()
        if r>0:
            self.events[r-1],self.events[r]=self.events[r],self.events[r-1]
            self.table.set_events(self.events); self.table.selectRow(r-1); self.table.refresh_indices(); self.path.update()

    def move_down(self):
        r=self._current_row()
        if 0<=r<len(self.events)-1:
            self.events[r+1],self.events[r]=self.events[r],self.events[r+1]
            self.table.set_events(self.events); self.table.selectRow(r+1); self.table.refresh_indices(); self.path.update()

    def delete_selected(self):
        r=self._current_row()
        if r>=0:
            del self.events[r]
            self.table.set_events(self.events); self.table.refresh_indices(); self.path.update()

    def clear_all(self):
        self.events.clear(); self.table.set_events(self.events); self.table.refresh_indices(); self.path.update()

    # save/load
    def save_macro(self):
        path,_ = QtWidgets.QFileDialog.getSaveFileName(self,"Save Macro","macro.json","JSON (*.json)")
        if not path: return
        with open(path,"w",encoding="utf-8") as f:
            json.dump([e.to_json() for e in self.events], f, ensure_ascii=False, indent=2)
        self.status.showMessage(f"Saved to {path}", 4000)

    def load_macro(self):
        path,_ = QtWidgets.QFileDialog.getOpenFileName(self,"Open Macro","","JSON (*.json)")
        if not path: return
        with open(path,"r",encoding="utf-8") as f:
            arr=json.load(f)
        self.events=[MacroEvent.from_json(x) for x in arr]
        self.table.set_events(self.events); self.table.refresh_indices(); self.path.update()
        self.status.showMessage(f"Loaded {len(self.events)} events.",4000)

    # playback
    def start_play(self):
        if "pyautogui (playback)" in missing:
            QtWidgets.QMessageBox.warning(self,"Missing","Install pyautogui to play: pip install pyautogui"); return
        if self.playing or not self.events:
            if not self.events: QtWidgets.QMessageBox.information(self,"Play","No events to play.")
            return
        self.playing=True; self.stop_flag=False
        self.btn_record.setEnabled(False); self.btn_stop.setEnabled(True); self.btn_play.setEnabled(False)
        self.status.showMessage("Playing macro...")
        # Use single pass (repeat can be added similarly to v1)
        speed = 1.0
        threshold = float(self.spn_thresh.value())
        scales = self._parse_scales()
        search_all = self.chk_allmons.isChecked()
        restore = self.chk_restore.isChecked() and HAVE_PYWINCTL

        def runner():
            try:
                # attempt window restore if first event is window_restore
                if restore:
                    for ev in self.events:
                        if ev.etype=="window_restore":
                            self._do_window_restore(ev.data)
                            break
                self._play_once(speed, threshold, scales, search_all)
                self.status.showMessage("Playback finished.", 4000)
            except Exception as e:
                self.status.showMessage(f"Playback error: {e}", 8000)
            finally:
                self.playing=False; self.stop_flag=False
                QtCore.QMetaObject.invokeMethod(self, "_restore_controls", Qt.QueuedConnection)

        self.play_thread = threading.Thread(target=runner, daemon=True); self.play_thread.start()

    @QtCore.Slot()
    def _restore_controls(self):
        self.btn_record.setEnabled(True); self.btn_stop.setEnabled(False); self.btn_play.setEnabled(True)

    def _sleep_responsive(self, secs: float):
        end=time.time()+max(0.0,secs)
        while time.time()<end:
            if self.stop_flag: return
            time.sleep(min(0.05, end-time.time()))

    def _type_key(self, key: str, down: bool):
        if key is None: return
        k=str(key)
        if k.startswith("Key."):
            name=k.split(".",1)[1]
            mapping={"enter":"enter","space":"space","tab":"tab","backspace":"backspace",
                     "esc":"esc","escape":"esc","delete":"delete","shift":"shift",
                     "ctrl":"ctrl","alt":"alt","cmd":"command","left":"left","right":"right",
                     "up":"up","down":"down","home":"home","end":"end","page_up":"pageup","page_down":"pagedown"}
            keyname=mapping.get(name)
            if keyname:
                if down: pyautogui.keyDown(keyname)
                else: pyautogui.keyUp(keyname)
        else:
            if len(k)==1:
                if down: pyautogui.keyDown(k)
                else: pyautogui.keyUp(k)

    def _do_window_restore(self, data: Dict[str,Any]):
        try:
            title = data.get("title","")
            x,y,w,h = int(data.get("x",0)), int(data.get("y",0)), int(data.get("w",800)), int(data.get("h",600))
            wins = pywinctl.getWindowsWithTitle(title) if title else []
            tgt = wins[0] if wins else pywinctl.getActiveWindow()
            if tgt:
                tgt.resizeTo(w,h); tgt.moveTo(x,y)
        except Exception:
            pass

    def _play_once(self, speed: float, threshold: float, scales: List[float], search_all: bool):
        for evt in self.events:
            if self.stop_flag: return
            self._sleep_responsive(evt.ts / max(0.1,speed) if evt.ts>0 else 0)
            et, d = evt.etype, evt.data
            if et=="mouse_move":
                try: pyautogui.moveTo(d.get("x"), d.get("y"))
                except Exception: pass
            elif et=="mouse_click":
                x,y = d.get("x"), d.get("y")
                btn = d.get("button","Button.left"); pressed = d.get("pressed",True)
                button = pyautogui.LEFT
                if "right" in btn.lower(): button=pyautogui.RIGHT
                elif "middle" in btn.lower(): button=pyautogui.MIDDLE
                if pressed:
                    if self.chk_anchor.isChecked() and d.get("anchor_b64"):
                        tmpl = np_from_b64_png(d["anchor_b64"]) if HAVE_NP else None
                        if tmpl is not None:
                            res = find_template_any_monitor(tmpl, threshold, scales, search_all)
                            if res is not None:
                                ax,ay,score,sc = res
                                off = d.get("anchor_offset",[0,0])
                                x,y = int(ax+off[0]), int(ay+off[1])
                    try:
                        pyautogui.moveTo(x,y); pyautogui.mouseDown(button=button)
                    except Exception: pass
                else:
                    try: pyautogui.mouseUp(button=button)
                    except Exception: pass
            elif et=="mouse_scroll":
                try: pyautogui.scroll(int(d.get("dy",0))*120)
                except Exception: pass
            elif et=="key_down":
                self._type_key(d.get("key"), True)
            elif et=="key_up":
                self._type_key(d.get("key"), False)
            elif et=="text":
                try: pyautogui.typewrite(d.get("text",""), interval=max(0.0,0.002/speed))
                except Exception: pass
            elif et=="wait":
                pass
            elif et=="screenshot":
                if HAVE_PIL and HAVE_NP:
                    img = np_from_b64_png(d.get("image_b64",""))
                    if img is not None:
                        import time as _t
                        Image.fromarray(img).save(f"screenshot_{int(_t.time())}.png")
                        self.status.showMessage("Saved screenshot file.",3000)
            elif et=="ocr_region":
                if HAVE_TESS and HAVE_MSS and HAVE_PIL:
                    x,y,w,h = int(d.get("x",0)), int(d.get("y",0)), int(d.get("w",100)), int(d.get("h",100))
                    img = grab_region(x,y,w,h)
                    if img is not None:
                        rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB) if HAVE_CV2 else img[:,:,:3][:,:,::-1]
                        pil = Image.fromarray(rgb)
                        try:
                            text = pytesseract.image_to_string(pil)
                        except Exception as e:
                            text = f"[OCR error: {e}]"
                        QtWidgets.QApplication.clipboard().setText(text)
                        self.status.showMessage("OCR result copied to clipboard.",3000)
            elif et=="open_url":
                url = d.get("url","");
                if url: webbrowser.open(url)
            elif et=="wait_for_image":
                b64 = d.get("anchor_b64",""); timeout = float(d.get("timeout",30.0))
                tmpl = np_from_b64_png(b64) if HAVE_NP else None
                if tmpl is None: continue
                end = time.time()+timeout
                found=False
                while time.time()<end and not self.stop_flag:
                    res = find_template_any_monitor(tmpl, threshold, scales, search_all)
                    if res is not None:
                        found=True; break
                    time.sleep(0.2)
                if not found:
                    self.status.showMessage("Wait-for-Image: timeout reached.",4000)
                    # continue flow (non-fatal). Could add branching later if needed.

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__=="__main__":
    main()
