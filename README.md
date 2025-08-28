# Macro Recorder (Python)

<img width="1197" height="786" alt="image" src="https://github.com/user-attachments/assets/2330f4e4-a502-45e2-bc5e-28fab91abc1a" />


[![Made with Python](https://img.shields.io/badge/Made%20with-Python-3776AB.svg)](https://www.python.org/)
[![GUI: PySide6](https://img.shields.io/badge/GUI-PySide6-41CD52)](https://doc.qt.io/qtforpython/)
[![Vision: OpenCV](https://img.shields.io/badge/Vision-OpenCV-5C3EE8)](https://opencv.org/)
[![Input: pynput](https://img.shields.io/badge/Input-pynput-20232a.svg)](https://pynput.readthedocs.io/)
[![Playback: pyautogui](https://img.shields.io/badge/Playback-pyautogui-20232a.svg)](https://pyautogui.readthedocs.io/)
[![OCR: Tesseract](https://img.shields.io/badge/OCR-Tesseract-3949AB.svg)](https://github.com/tesseract-ocr/tesseract)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

> Cross-platform GUI macro recorder with **smart visual clicks (OpenCV)**, **multi-monitor & multi-scale matching**, **Wait-for-Image** steps, **screenshots**, **OCR**, and optional **window restore**.

---

## 📌 Quick links

- **Download / Clone**: `git clone https://github.com/<you>/macro-recorder-python.git`
- **Run**: `python macro_recorder_v2.py`
- **Requirements**: See [Installation](#-installation)
- **Issues**: [Open an issue](https://github.com/<you>/macro-recorder-python/issues)

---

## ✨ Features

- **No-code desktop automation** – record & replay **mouse** and **keyboard**.
- **Smart Clicks (visual anchors)** – robust to layout shifts; uses OpenCV template matching.
- **Multi-monitor & multi-scale** search – handles multiple screens and small DPI/zoom changes.
- **Wait-for-Image** step – block until a UI element appears (with timeout) instead of fixed sleeps.
- **Screenshot step** – capture full screen or a region; saved to files during playback.
- **OCR Region** – extract text to clipboard (requires Tesseract).
- **Window Restore (optional)** – record active window geometry and restore before playback.
- **Built-in macro editor** – reorder/delete steps; edit delays; edit text/URL.
- **Save/Load** macros – portable JSON format for version control.

---
Shortcuts included (when app window is focused):

Recording & playback

Ctrl+Shift+R → Record

Esc → Stop (recording or playback)

Ctrl+Enter → Play

File

Ctrl+N → New (clear all)

Ctrl+O → Open…

Ctrl+S → Save…

Edit rows

Alt+Up / Alt+Down → Move Up / Move Down

Delete → Delete selected row

Ctrl+E → Edit Delay

Ctrl+Shift+E → Edit Text/URL

Add steps

Ctrl+W → + Wait

Ctrl+T → + Type Text

Ctrl+L → + Open URL (L = link)

Ctrl+Shift+P → 📸 Screenshot

Ctrl+Shift+O → 🔎 OCR Region

Ctrl+I → + Wait for Image

Toggles

Ctrl+G → Toggle Smart Click (visual)

Ctrl+M → Toggle Search all monitors

--------------

### How to capture a GIF (two easy options)

- **Windows:** use [ScreenToGif](https://www.screentogif.com/) and export to `screenshots/demo.gif`.
- **ffmpeg (any OS):**
  ```bash
  # record a short mp4 with your screen tool (e.g. OBS) to demo.mp4
  # then convert to a compact GIF:
  ffmpeg -i demo.mp4 -vf "fps=10,scale=1024:-1:flags=lanczos" -loop 0 screenshots/demo.gif
🧩 Architecture (high level)
GUI: PySide6 (Qt for Python).

Recording: pynput global hooks (mouse/keyboard).

Playback: pyautogui for mouse/keyboard actions.

Screen Capture: mss (+ Pillow, numpy).

Smart Clicks: OpenCV matchTemplate across monitors and scales.

OCR: pytesseract + Tesseract binary.

Window control (optional): pywinctl.

Event schema (JSON):

json
{
  "etype": "mouse_click",
  "ts": 0.134,
  "data": {
    "x": 812,
    "y": 446,
    "button": "Button.left",
    "pressed": true,
    "anchor_b64": "<base64 PNG>",
    "anchor_offset": [35, 35]
  }
}
etype ∈ mouse_move | mouse_click | mouse_scroll | key_down | key_up | text | wait | screenshot | ocr_region | open_url | wait_for_image | window_restore
ts = delay before event (seconds).
data = event-specific payload.

📦 Installation
Requirements

Python 3.10+

OS: Windows / macOS / Linux

On Linux, X11/Xorg is recommended for global hooks; Wayland may limit functionality.

Install

bash
# 1) Clone
git clone https://github.com/<you>/macro-recorder-python.git
cd macro-recorder-python

# 2) Optional: create a venv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3) Install deps
pip install -r requirements.txt
OCR (optional)
Install the Tesseract binary for your platform and ensure tesseract works in your terminal.

Windows: Install from the Tesseract project (add to PATH).

macOS: brew install tesseract

Linux (Debian/Ubuntu): sudo apt-get install tesseract-ocr

▶️ Usage
bash
python macro_recorder_v2.py
Typical flow

Record – click “● Record” and perform your actions.

Stop – click “⏹ Stop”.

Edit – reorder/delete steps; tweak “Delay (s)”; edit Text/URL.

Add Steps – Wait, Type Text, Open URL, Screenshot, OCR, Wait-for-Image.

Smart Click – leave enabled to anchor clicks visually.

Play – hit “▶ Play” to replay.

Save/Load – store macro as JSON and reuse any time.

Options bar

Smart Click (visual) – enable/disable anchor-based clicking.

Search all monitors – include all screens in matching.

Match threshold – 0.5–0.99 (default 0.87).

Scales – comma-separated (e.g. 0.85,0.9,1.0,1.1,1.2).

Restore active window – relocate/resize the recorded window (if pywinctl present).

🧯 Troubleshooting
“Missing dependency” shown in status bar
Run pip install -r requirements.txt.

Clicks/typing blocked (macOS)
System Settings → Privacy & Security → Accessibility → allow Terminal/Python/IDE.
Also allow Screen Recording if prompted.

Smart Click can’t find target

Lower threshold (e.g., 0.82).

Add more scales (0.75,0.85,0.9,1.0,1.1,1.2).

Re-record click so the anchor contains distinctive UI features.

OCR returns nothing
Confirm tesseract runs in the terminal and your region is crisp/zoomed.

Linux + Wayland
Global hooks/screen capture may be limited; use Xorg session for full support.

🔐 Security & Privacy
Keystrokes/mouse events and small on-screen image patches (anchors/screenshots) are recorded locally only.

Treat saved macros as sensitive — they can contain base64-embedded images and typed text.

Avoid recording credentials or sensitive data whenever possible.

📦 Building Releases (optional)
Windows (.exe) with PyInstaller

bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name "MacroRecorder" macro_recorder_v2.py
# Result: dist/MacroRecorder.exe
macOS app bundle

bash
pyinstaller --windowed --name "MacroRecorder" macro_recorder_v2.py
# Result: dist/MacroRecorder.app
Linux AppImage
Consider pyinstaller + appimagetool (outside the scope of this README).

🧭 Roadmap
Per-step branching (IF/ELSE on image match, timeouts).

Re-add repeat/speed controls in the v2 UI (present in v1).

Accessibility API targets (beyond image matching).

Multi-scale pyramid + mask-aware template matching for even more robustness.

Import/export from popular macro tools.

🤝 Contributing
PRs welcome!
Please keep features cross-platform when possible and avoid breaking the macro JSON schema.

Ideas

CI for linting on PRs (ruff/black).

Unit tests for event serialization and image matching helpers.

Localized UI strings.

🧾 License
MIT — see LICENSE.

🙌 Acknowledgements
PySide6 (Qt for Python) – GUI

OpenCV, NumPy, MSS, Pillow – vision & screen capture

pynput – recording hooks

pyautogui – playback

pytesseract + Tesseract – OCR

pywinctl – optional window management
