# VanishCam — webcam disappearance effects

Video is processed on your computer. It is neither recorded nor sent to a server. The preview window and virtual camera show only the video and effects, without overlaid menus, instructions, or text.

For step-by-step instructions in English and Italian, see the [user guide](USER_GUIDE_EN_IT.md).

## ☕ Buy me a coffee

If you like this project and want to support it, you can buy me a coffee through [PayPal](https://paypal.me/nicovic17) or [Revolut](https://revolut.me/nicoauriemma).

## Download for Windows

[Download VanishCam.exe]( https://nicoaauriemma.vercel.app/shop ) and double-click it to run the app. You do not need to install Python.

The published EXE may predate the Particles and Goku modes. To use them now, run the local scripts or rebuild the EXE from these sources.

## macOS (Apple silicon)

The macOS build supports Normal Vanish and Naruto Vanish, the modes currently
implemented in `vanish_cam.py`. It requires an Apple silicon Mac and macOS 14 or
later. Intel Mac builds are not supported by this build configuration.

To build from a fresh checkout, install Python 3.12, then run:

```sh
./BUILD_MACOS.command
```

The script creates an isolated `.venv-macos`, installs dependencies, downloads the
MediaPipe models, builds `dist/VanishCam.app`, and checks the bundled models and
assets without opening the camera. Copy the app to Applications; Python is not
needed to run the built app. The local build is ad-hoc signed. Distribution to
other Macs may require Developer ID signing and notarization.

Open VanishCam, select an effect, and allow Camera access when macOS asks. After
the camera opens, step out of frame for 4 seconds to capture an empty background.
If access was denied, enable VanishCam in **System Settings → Privacy & Security →
Camera**, then reopen it. No microphone permission is required.

Use **Quit** in the mode chooser, **⌘Q**, or **Q / Esc** in the preview to quit.
Closing the preview also releases the camera. Click the preview before using
keyboard controls. Startup errors are shown in a dialog; diagnostic logs are
written to `~/Library/Logs/VanishCam/VanishCam.log`.

For development, the same platform-aware requirements work on Windows and macOS:

```sh
python3.12 -m venv .venv-macos
.venv-macos/bin/python -m pip install -r requirements.txt
.venv-macos/bin/python macos_launcher.py
```

macOS uses MediaPipe 0.10.35 because 1.0.1 aborts while opening its detection graph
on Apple silicon. Sound plays through native `NSSound` to avoid conflicting SDL
libraries. Windows retains MediaPipe 1.0.1 and pygame/ffplay audio.

## Building and testing

On Windows, put Python 3.12 on PATH (or set `PYTHON_BIN` to its executable) and run
`BUILD_WINDOWS.bat` to create `dist/VanishCam.exe`. The build uses that interpreter
instead of the Python launcher's newest installed version. The existing `.bat`
launchers remain available; the local launcher creates its environment with
Python 3.12 when using `py`.

Run the camera-free unit suite from the repository root:

```sh
python -m unittest discover -v
```

After installing dependencies and downloading models, check real model inference:

```sh
python -c "from vanish_cam import download_models; download_models()"
python vanish_cam.py --self-test
```

The GitHub Actions workflow runs the tests, model checks, and packaged build
checks on Windows and Apple silicon macOS. Live gestures, camera permission
prompts, and OBS output still need a manual check with real hardware.

## Getting started

1. Double-click `AVVIA_LOCALE.bat`.
2. In the start menu, choose **Normal Vanish**, **Naruto Vanish**, **Particles**, or **Goku** with the mouse or the `1`, `2`, `3`, and `4` keys.
3. Step out of the camera frame for 4 seconds while the background is captured. The terminal tells you when you can step back in.

**Normal Vanish:** Raise your index and middle fingers in a V sign. The dissolve starts as soon as the gesture is recognized and lasts about 3.6 seconds.

**Particles:** Make the same V sign as in Normal Vanish. Your silhouette breaks into small colored fragments that drift sideways as if carried by the wind. The effect lasts about 2.1 seconds. It captures your silhouette once when the effect starts to keep the video smooth.

**Goku:** Hold your index and middle fingers straight and together against your forehead for 1 second. Animated vertical comic-style lines run across your silhouette just before you teleport away and linger briefly afterward. To reappear, lower your hand, then repeat the gesture for another 1 second. The return uses the reverse effect. If you break the pose, the countdown starts over. `assets/teleport.MP3` plays on both disappearance and reappearance. The terminal shows the countdown for each gesture. The `V` and `R` keys are disabled in this mode: the gesture is the only way to disappear and reappear. No text is overlaid on the video.

**Naruto Vanish:** Bring your palms together in front of the webcam, with your fingers side by side rather than interlaced. Keep both hands visible. As soon as the gesture is recognized, you vanish in a cloud of smoke and a wooden log appears, falls, and remains visible until you press `R`. No microphone is needed. Naruto mode uses `hand_landmarker.task` to track both hands. `assets/vanish.MP3` plays through your computer speakers when the disappearance starts, including when triggered with `V`. You can trigger it again after pressing `R`.

To start a mode without the menu:

```powershell
.\AVVIA_LOCALE.bat --mode naruto
.\AVVIA_LOCALE.bat --mode normal
```

## Virtual camera and OBS

If [OBS Studio](https://obsproject.com/) is installed, the app automatically tries to open **OBS Virtual Camera**. The terminal shows the device name. Use `AVVIA_VIRTUAL.bat` to require a virtual camera. Select **OBS Virtual Camera** in the app that will receive the video. OBS's virtual camera must be stopped while this app is producing its output.

To use the effect in an OBS scene, run `AVVIA_OBS.bat`, add a **Window Capture** source, select **Webcam - Anteprima**, and then start the virtual camera from OBS. Alternatively, use [Unity Capture](https://github.com/schellingb/UnityCapture) as a separate virtual video source:

```powershell
.\AVVIA_VIRTUAL.bat --virtual-backend unitycapture
```

OBS has only one virtual camera. Do not use it as both an OBS input and output at the same time. See the [pyvirtualcam documentation](https://github.com/letmaik/pyvirtualcam#supported-virtual-cameras).

On macOS, install OBS Studio 30 or later, start and stop its virtual camera once,
and close OBS before selecting a VanishCam mode. The app then automatically tries
to publish to **OBS Virtual Camera**, falling back to the local preview if the
driver is unavailable. See [pyvirtualcam's macOS setup](https://github.com/letmaik/pyvirtualcam#macos-obs).
The Windows-only Unity Capture backend is not available on macOS.

## Controls

- `SPACE`: capture a new background.
- `R`: make the person reappear.
- `V`: manually start the selected mode's effect.
- `F`: toggle fullscreen.
- `Q` or `ESC`: quit and release the cameras.

The `V` and `R` keys are disabled in Goku mode.

You can change the camera, resolution, and maximum virtual-output FPS:

```powershell
.\AVVIA_LOCALE.bat --camera 1 --width 1280 --height 720 --fps 30
```

To troubleshoot gesture recognition without adding text to the video, pass `--gesture-debug`. Diagnostic information appears only in the terminal.

## Visual assets

The [wooden log](assets/substitution_log.png) is an original illustration generated with ImageGen using the supplied image as a visual reference. Smoke is drawn in real time by `naruto_effect.py` so it follows the person's position and scales with the video. We also considered a [CC0 smoke sprite sheet](https://opengameart.org/content/smoke-sprite-sheet), but the procedural animation adapts better to dynamic positioning without an additional asset. No anime frames or assets are included in the project.

Goku mode uses the [MediaPipe BlazeFace short-range model](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/web/vision/README.md) to estimate the forehead position and `hand_landmarker.task` to track the fingers. The teleport's visual trace is drawn in code, without anime frames.
