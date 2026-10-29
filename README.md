# VanishCam — webcam disappearance effects

Video is processed on your computer. It is neither recorded nor sent to a server. On first run, the app downloads its MediaPipe model files from Google Cloud Storage; camera frames are not sent with those downloads. The preview window and virtual camera show only the video and effects, without overlaid menus, instructions, or text.

## ☕ Buy me a coffee

If you like this project and want to support it, you can buy me a coffee through [PayPal](https://paypal.me/nicovic17) or [Revolut](https://revolut.me/nicoauriemma).

## Windows

[Download VanishCam.exe]( https://nicoaauriemma.vercel.app/shop ) and double-click it to run the app. You do not need to install Python.

To run from source, double-click `AVVIA_LOCALE.bat`. It creates a local virtual environment and installs the dependencies the first time it runs.

## macOS

Build a native `.app` bundle on the Mac that will run it:

```bash
./BUILD_MACOS.sh
```

The script creates `.venv-macos`, installs the requirements and PyInstaller, downloads the MediaPipe models, builds `dist/macos/VanishCam.app`, and runs its self-test. A working internet connection is required for the first setup. Python 3.10–3.13 is required; set `PYTHON=/path/to/python3.13` to select a specific interpreter. The build is local and unsigned; it is not notarized for distribution to other Macs.

To run from source instead of building the app bundle:

```bash
source .venv-macos/bin/activate
python vanish_cam.py
```

macOS may ask for camera permission; grant or revoke it in **System Settings → Privacy & Security → Camera**. VanishCam does not need microphone access.

## Getting started

1. Double-click `AVVIA_LOCALE.bat`.
2. In the start menu, choose **Normal Vanish** or **Naruto Vanish** with the mouse or the `1` and `2` keys.
3. Step out of the camera frame for 4 seconds while the background is captured. The terminal tells you when you can step back in.

**Normal Vanish:** Raise your index and middle fingers in a V sign. The dissolve starts as soon as the gesture is recognized and lasts about 3.6 seconds.

**Naruto Vanish:** Bring your palms together in front of the webcam, with your fingers side by side rather than interlaced. Keep both hands visible. As soon as the gesture is recognized, you vanish in a cloud of smoke and a wooden log appears, falls, and remains visible until you press `R`. No microphone is needed. Naruto mode uses `hand_landmarker.task` to track both hands. `assets/vanish.MP3` plays through your computer speakers when the disappearance starts, including when triggered with `V`. You can trigger it again after pressing `R`.

To start a mode without the menu:

```powershell
.\AVVIA_LOCALE.bat --mode naruto
.\AVVIA_LOCALE.bat --mode normal
```

On macOS, use `python vanish_cam.py --mode naruto` or `python vanish_cam.py --mode normal` from the project directory after activating `.venv-macos`.

## Virtual camera and OBS

If [OBS Studio](https://obsproject.com/) is installed, the app automatically tries to open **OBS Virtual Camera**. The terminal shows the device name. Use `AVVIA_VIRTUAL.bat` to require a virtual camera. Select **OBS Virtual Camera** in the app that will receive the video. OBS's virtual camera must be stopped while this app is producing its output.

To use the effect in an OBS scene, run `AVVIA_OBS.bat`, add a **Window Capture** source, select **Webcam - Anteprima**, and then start the virtual camera from OBS. Alternatively, use [Unity Capture](https://github.com/schellingb/UnityCapture) as a separate virtual video source:

```powershell
.\AVVIA_VIRTUAL.bat --virtual-backend unitycapture
```

OBS has only one virtual camera. Do not use it as both an OBS input and output at the same time. See the [pyvirtualcam documentation](https://github.com/letmaik/pyvirtualcam#supported-virtual-cameras).

## Controls

- `SPACE`: capture a new background.
- `R`: make the person reappear.
- `V`: manually start the selected mode's effect.
- `F`: toggle fullscreen.
- `Q` or `ESC`: quit and release the cameras.

You can change the camera, resolution, and maximum virtual-output FPS:

```powershell
.\AVVIA_LOCALE.bat --camera 1 --width 1280 --height 720 --fps 30
```

To troubleshoot gesture recognition without adding text to the video, pass `--gesture-debug`. Diagnostic information appears only in the terminal.

## Visual assets

The [wooden log](assets/substitution_log.png) is an original illustration generated with ImageGen using the supplied image as a visual reference. Smoke is drawn in real time by `naruto_effect.py` so it follows the person's position and scales with the video. We also considered a [CC0 smoke sprite sheet](https://opengameart.org/content/smoke-sprite-sheet), but the procedural animation adapts better to dynamic positioning without an additional asset. No anime frames or assets are included in the project.
