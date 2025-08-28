# macro-recorder-python
Cross-platform GUI macro recorder with smart visual clicks (OpenCV), multi-monitor &amp; multi-scale matching, wait-for-image, screenshots, OCR, and window restore.

# Macro Recorder v2 (Python)

Enhancements over v1:
- **Multi-monitor** template matching (search all screens)
- **Multi-scale** matching with configurable scales (handles small UI scale changes)
- **Wait for Image** conditional step with timeout
- **Window restore** (records current active window geometry; optionally restores before playback)
- Tunable **match threshold** in the UI

## Install
```bash
pip install -r requirements_v2.txt
