# VanishCam — local webcam disappearance effects

VanishCam processes your webcam on your computer. Camera frames are not recorded or uploaded. The virtual-camera feed contains only the camera image and effects. The local preview also shows startup instructions, countdowns, and gesture feedback. The effect menu is a separate window shown before camera output starts.

## Start on this Windows PC

1. Open `C:\Users\LOQ\vanish_webcam` in File Explorer.
2. Double-click **START_VANISHCAM.bat**.
3. Click an effect or press its number, **1–8**.
4. Step completely out of view for **4 seconds** while the background is captured.
5. Wait for green **READY**, then step back in. The required gesture is shown for seven seconds.
6. Make the sign to vanish. Lower your hand, then repeat the same sign to reappear in any mode. **Q / Esc** quits. **V / R** remain keyboard alternatives except in Goku.

The launcher uses the project's `.venv-local` environment. On a fresh checkout, install Python 3.12 first; `AVVIA_LOCALE.bat` creates the environment and installs `requirements.txt`. Required segmentation/gesture model files are downloaded from Google's model storage when missing. Hand and face models are included in the repository. Once these files are present, processing works offline.

## Modes

| Key | CLI name | Effect | Trigger |
| --- | --- | --- | --- |
| 1 | `normal` | Original cyan dissolve, tracking the live silhouette | V sign |
| 2 | `naruto` | Smoke, substitution log, falling log and original sound | Palms together, fingers side by side |
| 3 | `particles` | Colored silhouette fragments carried sideways by wind | V sign |
| 4 | `goku` | Vertical energy lines, a brief flash and instant transmission | Two straight fingers together at the forehead for 1 second |
| 5 | `piccolo` | Green-white ki aura, shockwave ring and rising energy particles | V sign |
| 6 | `burn` | Bottom-up fire, charcoal, embers and drifting ash | V sign |
| 7 | `whoosh` | Curved airflow trails and a 0.4-second disappearance | V sign |
| 8 | `electric` | Blue sparks, lightning traces and a quick teleport | V sign |

For the V sign, extend index and middle fingers, separate their tips, and curl ring and little fingers. The thumb can be hidden. Naruto requires both hands in view. Goku requires the two fingertips to stay together near the forehead or temple continuously for one second. Lower the hand before repeating the gesture. **V and R are disabled in Goku mode.**

Gesture activation requires consecutive observations. A held gesture fires once and must be clearly released before it can trigger again. `R` reverses the procedural effects; Naruto also reverses its substitution animation. Pressing `R` partway through a procedural disappearance reverses from its current progress.

The new visual effects are procedural. Naruto retains `assets/vanish.MP3`. Goku uses `assets/teleport.MP3` if supplied; that file is absent in the upstream checkout, so this version generates an original teleport sound in memory. Fire crackle and whoosh sounds are also generated in memory. Sounds play through your speakers; a virtual camera carries video, not microphone audio.

## Use in Zoom, Meet, Teams, WhatsApp Desktop or a browser

1. Install **[OBS Studio for Windows](https://obsproject.com/download)**, accepting the Windows administrator prompt.
2. Open OBS once. Click **Start Virtual Camera**, then **Stop Virtual Camera**. Keep it stopped while VanishCam runs.
3. Close and reopen the meeting app or browser after driver installation.
4. Start **START_VANISHCAM.bat** and select a mode.
5. In the receiving app's camera settings, select **OBS Virtual Camera**.

VanishCam tries `obs`, then `unitycapture` on Windows. The successful device name is printed in the terminal. OBS does not need to remain open. If neither backend is available, the normal launcher continues with a clear **preview-only** message. Installing `pyvirtualcam` alone does not install a Windows camera driver.

The outgoing video is **unmirrored RGB** at the physical camera's negotiated resolution and the requested output FPS. The local preview remains mirrored by default. Some meeting apps mirror their own self-preview; that does not mean VanishCam sent mirrored video. Camera support and permissions are controlled by each receiving app; individual apps can restrict virtual cameras.

If OBS is installed but the camera is missing, follow the official [OBS virtual-camera repair instructions](https://obsproject.com/kb/virtual-camera-troubleshooting). If it is registered but busy, stop OBS's virtual camera and close other VanishCam instances. [Unity Capture](https://github.com/schellingb/UnityCapture) is an alternative driver. OBS has a single virtual camera; do not use it as both an OBS input and output simultaneously. See [pyvirtualcam's supported cameras](https://github.com/letmaik/pyvirtualcam#supported-virtual-cameras).

`AVVIA_VIRTUAL.bat` retains its strict behavior: it requires a working virtual camera. `AVVIA_OBS.bat` disables direct virtual output so you can use an OBS Window Capture source, selecting **Webcam - Anteprima**, then start the virtual camera from OBS itself.

## Controls and CLI

Run commands from the repository folder in PowerShell:

```powershell
.\START_VANISHCAM.bat
.\START_VANISHCAM.bat --mode piccolo --profile
.\START_VANISHCAM.bat --mode burn --detection-light --gesture-debug
.\START_VANISHCAM.bat --camera 1 --width 1280 --height 720 --fps 30
.\START_VANISHCAM.bat --headless --mode goku
.\AVVIA_LOCALE.bat --no-virtual-camera --mode particles
.\AVVIA_VIRTUAL.bat --virtual-backend unitycapture --mode whoosh
```

| Flag | Meaning |
| --- | --- |
| `--mode NAME` | Skip the menu; use a name from the mode table |
| `--camera N` | Physical camera index; default 0 |
| `--width W --height H --fps N` | Request capture/output settings; default 1280×720 at 30 FPS |
| `--virtual-camera` | Require a virtual camera; report an error if no backend works |
| `--no-virtual-camera` | Preview only |
| `--virtual-backend NAME` | Require a specific backend; `obs`, `unitycapture`, or Linux `v4l2loopback` |
| `--virtual-device NAME` | Select a specific virtual device |
| `--headless` | No GUI windows; requires a working virtual camera |
| `--profile` | Terminal output FPS and mean/p95 timing measurements every 2 seconds |
| `--gesture-debug` | Terminal-only hand states, geometry scores, smoothing, hold duration and latch state |
| `--gesture-frames N` | Consecutive detections needed to trigger; default 3 |
| `--gesture-release-frames M` | Clear misses needed to rearm; default 5 |
| `--detection-width W` | Width of the inference copy; default 640; output resolution is unchanged |
| `--detection-light` | Mild local contrast normalization on the detection copy only |
| `--no-mirror` | Disable mirroring in the local preview; outgoing camera remains unmirrored |
| `--fullscreen` | Start the preview fullscreen |
| `--duration SECONDS` | Automatically stop after this duration; default 0 means no limit |

**SPACE** captures a new background. **H** repeats help. **M** toggles sound. **F** toggles preview fullscreen. **Q / Esc / Ctrl+C** close the cameras and workers. Close the preview window to quit as well.

In headless mode, omitting `--mode` shows a numbered terminal menu. Use the terminal for Q, Esc, Space, V and R. No OpenCV window is created, and the program exits with installation guidance if virtual output is unavailable. On non-Windows systems use Ctrl+C to quit; interactive headless key polling is Windows-specific.

## Performance and gesture tuning

Camera capture has one latest-frame slot, and inference has one replaceable pending job. Rendering never waits for a hand or face inference call. MediaPipe uses CPU VIDEO tracking with two hands on a 640-pixel-wide copy. Normalized landmarks are mapped back to the full image dimensions. Finger geometry uses joint angles and palm-relative distances, including a 2D fallback when depth estimates are unreliable.

Segmentation runs when a transition needs a snapshot and while Normal tracks its dissolve. Other modes cache the silhouette once per transition. Snapshot preparation happens in the worker. Effect fields use at most 480 pixels of width (320 for Burn); the camera and background remain at full resolution. Background capture keeps the original median calculation and runs it in a separate worker using small strips. Noise fields, particle trajectories, kernels and image buffers are reused. The output loop is paced independently at the requested FPS. OpenCV uses one native worker thread to avoid the oversubscription measured on this PC.

**30 FPS is a target, not a guarantee for every laptop, camera or lighting condition.** Check `--profile`: `capture_age` measures the age of the most recent camera frame, `detection_age` measures the current landmark result's age, and `render`, `segment`, `landmarks` and `effect_prepare` show the cost of each stage. Detection can run slower than output without buffering the live video. Deliberate gesture hold/release thresholds add trigger latency.

For dim rooms, try `--detection-light` and improve light on the hands. If false triggers occur, increase `--gesture-frames` to 4 or 5. If rearming takes too long, reduce `--gesture-release-frames` to 3. These counters count inference observations, not repeated output frames. Goku always requires one continuous second. If a camera lowers its hardware frame rate under low light, the program cannot invent new motion frames; increase room lighting or use a lower capture resolution.

If the camera is unavailable, close Windows Camera, another VanishCam window, or any app using the physical webcam. In Windows **Settings > Privacy & security > Camera**, allow camera access and desktop-app camera access. Try `--camera 1` if needed. If the background contains your body, press Space and leave the frame for four seconds again.

MediaPipe's `inference_feedback_manager` and `NORM_RECT` warning lines are diagnostic messages; they do not by themselves mean the camera failed. Read the final error or the `[Camera]` message for actionable failures.

## Verification

```powershell
.\.venv-local\Scripts\python.exe -m unittest discover -q
.\.venv-local\Scripts\python.exe vanish_cam.py --self-test
.\.venv-local\Scripts\python.exe benchmark_vanishcam.py
.\.venv-local\Scripts\python.exe benchmark_vanishcam.py --live --mode goku --seconds 12
```

The synthetic benchmark writes generated test graphics and timings under `diagnostics/`. The optional live benchmark uses the physical camera temporarily, saves only timing statistics, and never saves webcam images. Its output-loop benchmark does not prove compatibility with every meeting app; virtual-device tests also cover RGB conversion, backend fallback, mirroring, headless operation and cleanup using controlled device doubles.

## Assets and credits

The wooden log is an updated version of the repository sprite. Naruto smoke, new energy effects, flames, fragments and sparks are generated procedurally; no anime frames are included. The original project's support links are [PayPal](https://paypal.me/nicovic17) and [Revolut](https://revolut.me/nicoauriemma).


## Startup guidance and recovery

The preview shows a four-second step-out countdown. Once the background is ready, it shows the selected gesture for seven seconds. Press **H** to show instructions again. Repeat the gesture after lowering your hand to reappear. Goku shows a one-second hold bar and accepts adjacent fingers at the forehead or temple.

Press **M** to mute effects. Audio failures mute sound while video continues; press M to retry on the next effect. If a camera frame is black, background capture pauses and the preview asks you to check the privacy shutter and lighting. Detection and silhouette errors also appear in the preview.

Double-click **CHECK_VANISHCAM.bat** to check dependencies, models, assets, and audio without opening the webcam. This does not test the physical camera or the OBS driver.
