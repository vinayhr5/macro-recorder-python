# macro-recorder-python
Cross-platform GUI macro recorder with smart visual clicks (OpenCV), multi-monitor &amp; multi-scale matching, wait-for-image, screenshots, OCR, and window restore.

# Macro Recorder(Python)

- **Multi-monitor** template matching (search all screens)
- **Multi-scale** matching with configurable scales (handles small UI scale changes)
- **Wait for Image** conditional step with timeout
- **Window restore** (records current active window geometry; optionally restores before playback)
- Tunable **match threshold** in the UI

## Install
```bash
pip install -r requirements_v2.txt

✨ Highlights

No-code desktop automation: record & replay mouse and keyboard.

Smart Clicks that survive layout shifts using visual anchors.

Multi-monitor + multi-scale matching (DPI/zoom tolerant).

Wait-for-Image step for conditional flows.

Screenshots & OCR (Tesseract) as first-class steps.

Window restore (record active window geometry and restore on playback).

Simple macro editor: reorder, delete, edit delays & text/URL.

JSON save/load for your macros.

🧩 Features
Recording

Global mouse move/click/scroll and keyboard capture.

Per-event delay (ts) is recorded for timing fidelity.

Playback

Uses pyautogui to replay actions.

Honors per-event delays (you can edit them).

Optional window restore before playback (via pywinctl).

Smart Click (Visual Anchor)

On mouse press events (when enabled), a small image patch around the click is stored.

On playback, OpenCV template matching finds that region:

Multi-monitor search (all screens)

Multi-scale (e.g., 0.85,0.9,1.0,1.1,1.2) for DPI/zoom changes

Tunable threshold (default 0.87)

Falls back to absolute X/Y if visual match isn’t available.

Wait-for-Image (Conditional)

Inserts a step that repeatedly searches the screen for a captured snippet until it appears or a timeout is reached.

Useful to synchronize with app states without hardcoded sleeps.

Screenshots & OCR

Screenshot step (full screen or region). Saves the captured image during playback.

OCR Region step: extracts text from a region into clipboard (requires Tesseract).

Editor

Reorder, delete, clear all.

Edit Delay for any row.

Edit Text/URL for text typing and open-URL steps.

Save / Load

Macros are plain JSON (one event per row). Easy to version control.

🛠️ How It Works (Under the Hood)

Event model:

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


etype: "mouse_move" | "mouse_click" | "mouse_scroll" | "key_down" | "key_up" | "text" | "wait" | "screenshot" | "ocr_region" | "open_url" | "wait_for_image" | "window_restore"

ts: delay before executing this event.

data: event-specific fields (e.g., coordinates, text, URL, image anchor).

Visual matching:

Captured anchor (around the click) is matched via cv2.matchTemplate over one or more scales across one or more monitors (via mss).

If score ≥ threshold → derived click point = match top-left + recorded offset.

📦 Requirements

Python 3.10+

OS: Windows / macOS / Linux

Pip packages (see requirements.txt):

PySide6
pynput
pyautogui
mss
numpy
opencv-python
pillow
pytesseract
pywinctl


OCR (optional): Install the Tesseract binary and ensure tesseract is on PATH.

macOS: grant Accessibility permissions to allow input control & screen capture.
Windows: you may get SmartScreen prompts; allow access.
Linux: global input hooks may be limited on Wayland; X11/Xorg is typically required for full functionality.

🚀 Installation
# 1) Clone your repo
git clone https://github.com/<you>/macro-recorder-python.git
cd macro-recorder-python

# 2) Create & activate a venv (recommended)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3) Install deps
pip install -r requirements.txt

OCR support (optional)

Install Tesseract for your platform (ensure tesseract command works in the terminal).

Then the OCR Region step will copy recognized text to the clipboard.

▶️ Run
python macro_recorder_v2.py


Typical flow:

Click Record (window may also be captured in window-restore step).

Perform your actions in any app.

Click Stop.

Review/edit steps in the table (tweak delays, add Text/URL, Screenshot, OCR, Wait-for-Image, etc.).

Click Play to replay the macro.

Save as JSON for reuse.

Options bar:

Smart Click (visual): toggle anchor-based clicking.

Search all monitors: include all screens in the image search.

Match threshold: increase to reduce false positives (0.5–0.99).

Scales: comma-separated factors to search (e.g., 0.85,0.9,1.0,1.1).

Restore active window: uses pywinctl to relocate/resize the original window.

🧪 Macro JSON Example
[
  {
    "etype": "window_restore",
    "ts": 0.05,
    "data": { "title": "My App", "x": 100, "y": 120, "w": 1280, "h": 800 }
  },
  {
    "etype": "mouse_click",
    "ts": 0.230,
    "data": {
      "x": 800, "y": 450,
      "button": "Button.left", "pressed": true,
      "anchor_b64": "<base64 PNG>", "anchor_offset": [35, 35]
    }
  },
  {
    "etype": "text",
    "ts": 0.100,
    "data": { "text": "Hello world!" }
  }
]

🧯 Troubleshooting

“Missing dependency” in status bar
Install the listed packages (see requirements.txt).

Nothing types/clicks on macOS
System Settings → Privacy & Security → Accessibility → allow Python/Terminal & your IDE.

Smart Click doesn’t find target

Lower the threshold slightly (e.g., 0.82).

Add more scales (e.g., 0.75,0.85,0.9,1.0,1.1,1.2).

Re-record the step so the anchor contains distinct UI context.

OCR returns empty
Confirm tesseract works in the terminal and the region has crisp text (zoom in if needed).

Linux + Wayland
pynput and global screen capture may be limited; use Xorg/X11 session if possible.

🔐 Security & Privacy

Your keystrokes/mouse and small on-screen image anchors are recorded locally.

Be mindful when recording sensitive information.

Macro JSON may embed base64 PNGs (anchors/screenshots) — treat files as sensitive.

🧭 Roadmap

Per-step branching (IF/ELSE on image matches / timeouts).

Repeat/Speed controls in v2 UI (v1 had a simple repeat; re-add here).

Element handles via platform accessibility APIs.

Multi-scale pyramid + mask-aware template matching for robustness.

Export/import to additional macro formats.

🤝 Contributing

PRs welcome!
Guidelines:

Keep features cross-platform when possible (Windows/macOS/Linux).

Avoid breaking changes to the macro JSON schema.

Add comments & small unit tests where feasible.

🙌 Acknowledgements

PySide6 (Qt for Python) for the GUI

OpenCV, NumPy, MSS, Pillow for vision & screen capture

pynput for global input hooks

pyautogui for playback

pytesseract + Tesseract for OCR

pywinctl for optional window management
