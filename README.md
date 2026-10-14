# Vanish Cam - Webcam with Disappearance Effects

Real-time video processing performed entirely on your computer. Video is never recorded or sent to any server. Both the preview window and the virtual webcam output provide a completely clean video feed with the effect—no menus, instructions, watermarks, or text overlays.

---

## ☕ Buy Me a Coffee

If you enjoy this project and would like to support it, you can buy me a coffee via [PayPal](https://paypal.me/nicovic17) or [Revolut](https://revolut.me/nicoauriemma).

---

## ✨ Features

- **Normal Vanish:** Raise your index and middle fingers in a V sign. The person dissolves progressively into the background over ~3.6 seconds with a stylized particle edge glow.
- **Naruto Vanish (Body Replacement Technique):** Bring your palms together in front of the camera (clapped hands pose). Your body instantly disappears in an expanding cloud of smoke and a wooden substitution log falls to the ground with a bounce, accompanied by the classic anime sound effect (`assets/vanish.MP3`).
- **Clean Output:** Designed specifically for virtual webcam feeds (Zoom, Google Meet, Discord, OBS, Teams). The output has zero HUD or overlays.
- **Cross-Platform:** Full support for both **Linux** and **Windows**.

---

## 🐧 Instructions for Linux

### 1. Prerequisites

- **Python 3.10+** (Python 3.10, 3.11, or 3.12)
- `python3-venv` and `python3-pip`

Install system packages:

**Ubuntu / Debian / Linux Mint:**
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip v4l-utils
```

**Fedora / RHEL:**
```bash
sudo dnf install python3 python3-pip v4l-utils
```

**Arch Linux / Manjaro:**
```bash
sudo pacman -S python python-pip v4l-utils
```

### 2. Quick Start

Run the automated startup script:

```bash
./run_local.sh
```

The script will automatically create a `.venv` virtual environment, install dependencies from `requirements.txt` on first launch, download required MediaPipe vision models if needed, and start the application.

To launch a specific mode directly without the initial menu:

```bash
./run_local.sh --mode naruto
./run_local.sh --mode normal
```

### 3. Virtual Camera on Linux (v4l2loopback)

To send the clean video stream to other apps (Discord, Google Meet, Zoom, OBS, etc.) as a virtual camera, install and enable `v4l2loopback`:

**Ubuntu / Debian:**
```bash
sudo apt install v4l2loopback-dkms
```

**Arch Linux:**
```bash
sudo pacman -S v4l2loopback-dkms
```

**Fedora:**
```bash
sudo dnf install v4l2loopback
```

Load the kernel module to create a virtual video device (e.g., `/dev/video10`):
```bash
sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="Vanish Cam" exclusive_caps=1
```

Now, when you start Vanish Cam, it will automatically detect and stream to `/dev/video10` (or your chosen device), making "Vanish Cam" selectable in your video calling apps.

To run without a virtual camera (preview window only):
```bash
./run_obs.sh
# or:
./run_local.sh --no-virtual-camera
```

### 4. Linux Permissions & Troubleshooting

- **Camera access:** Ensure your user belongs to the `video` group:
  ```bash
  sudo usermod -aG video $USER
  ```
  *(Log out and log back in for group changes to take effect).*
- **List available cameras:**
  ```bash
  v4l2-ctl --list-devices
  ```
  If your physical camera is `/dev/video2`, specify `--camera 2`.
- **Audio playback:** The Naruto effect plays sound using `pygame` (included in `requirements.txt`). Alternatively, if `ffplay` (`ffmpeg`) is installed on your system, it will be used as a fallback.

---

## 🪟 Instructions for Windows

### Windows Executable
You can download the pre-built standalone executable [VanishCam.exe](https://firebasestorage.googleapis.com/v0/b/graficammece-9b254.firebasestorage.app/o/vanish_cam%2FVanishCam.exe?alt=media&token=82017e0a-52b9-420d-88ba-a4640d5e2ffc) and run it with a double click. No Python installation needed.

### Running from Source (Windows)
Double-click `run_local.bat` (or `AVVIA_LOCALE.bat`).
It will set up a local virtual environment, install dependencies, and launch the camera.

Direct mode startup:
```powershell
.\run_local.bat --mode naruto
.\run_local.bat --mode normal
```

---

## 🎮 How to Use

1. Launch the app and choose **Normal Vanish** or **Naruto Vanish** with the mouse or by pressing `1` or `2`.
2. **Background Calibration:** Step out of the camera frame for 4 seconds while the background is calibrated and captured. The terminal will indicate when you can step back in.
3. Trigger the effect:
   - **Normal Vanish:** Raise your index and middle fingers in a V sign.
   - **Naruto Vanish:** Bring both palms together in front of the camera (palms touching, fingers side-by-side and pointing up, not interlaced). Keep both hands visible.
4. The effect will trigger immediately upon detection!

### Keyboard Controls

- `SPACE`: Recapture background (step out of frame for 4 seconds).
- `R`: Reappear (reset vanish effect back to live camera feed).
- `V`: Manually trigger the chosen vanish effect.
- `F`: Toggle fullscreen window mode.
- `Q` or `ESC`: Quit and release all cameras.

---

## ⚙️ Command-Line Options

```
usage: vanish_cam.py [-h] [--camera CAMERA] [--width WIDTH] [--height HEIGHT]
                     [--fullscreen] [--no-mirror] [--fps FPS]
                     [--virtual-camera | --no-virtual-camera]
                     [--virtual-backend {obs,unitycapture,v4l2loopback}]
                     [--virtual-device VIRTUAL_DEVICE]
                     [--mode {normal,naruto}] [--gesture-debug]
```

| Option | Description |
|---|---|
| `--camera <int>` | Camera device index (default: `0`) |
| `--width <int>` | Video feed width (default: `960`) |
| `--height <int>` | Video feed height (default: `540`) |
| `--fps <float>` | Maximum virtual output FPS (default: `30`) |
| `--no-mirror` | Disable horizontal mirroring |
| `--fullscreen` | Launch window in fullscreen mode |
| `--virtual-camera` | Force enable virtual camera output |
| `--no-virtual-camera`| Disable virtual camera output (preview window only) |
| `--virtual-backend` | Virtual camera driver backend (`v4l2loopback`, `obs`, or `unitycapture`) |
| `--virtual-device` | Virtual camera device name or path |
| `--mode {normal,naruto}` | Skip initial menu and start selected effect directly |
| `--gesture-debug` | Print gesture recognition diagnostics to terminal (no video overlay) |

Example custom command:
```bash
./run_local.sh --camera 0 --width 1280 --height 720 --fps 30 --gesture-debug
```

---

## 🎨 Visual Assets & Design

- The [substitution log](assets/substitution_log.png) is an original transparent-background illustration generated with ImageGen using a visual reference.
- Smoke is procedurally generated in real time in `naruto_effect.py` so that it dynamically conforms to the detected silhouette's size and position in the frame.
- No copyrighted frames or anime assets are included in this project.
