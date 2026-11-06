## ☕ Buy me a coffee

If you like this project and want to support it, you can buy me a coffee through [PayPal](https://paypal.me/nicovic17) or [Revolut](https://revolut.me/nicoauriemma).

# VanishCam — webcam disappearance effects

Video is processed on your computer. It is neither recorded nor sent to a server. The preview window and virtual camera show only the video and effects, without overlaid menus, instructions, or text.

All packaged Windows EXEs require an active email license and Internet access. The first
launch asks only for your license email, then binds it to this Windows device.
Later launches remember the email but always check Firebase again. No password
or email verification is requested. Only license/device/session data is sent;
the webcam feed stays local. One running instance is allowed across editions.
For owner setup and manual activation, see [GESTIONE_LICENZE.md](GESTIONE_LICENZE.md).

The Python source launched with `AVVIA_LOCALE.bat` is the local development
version: it starts without Firebase or a license check. Packaged EXEs retain
the online license requirement. Until the server rules include a new effect,
the licensed full EXE reports its session mode as `full`, so a valid license
does not stop renewing while that effect runs.

For step-by-step instructions in English and Italian, see the [user guide](USER_GUIDE_EN_IT.md).

## Windows executables

[Browse the shop](https://nicoaauriemma.vercel.app/shop) for published downloads. To build from these sources, first copy `license_config.example.json` to the Git-ignored `license_config.json` and fill in the Firebase project ID and client API key. Then run `BUILD_WINDOWS.bat`. It creates four standalone EXEs in `dist/`:

- `VanishCam.exe` offers Normal, Naruto, Particles, Goku and Itachi.
- `Naruto Vanish Effect.exe` starts Naruto directly.
- `Goku Vanish Effect.exe` starts Goku directly.
- `Normal and Particles Vanish.exe` lets you choose Normal Vanish or Particles with the mouse or keys `1` and `2`.

Each EXE includes the models and assets needed for its modes. No separate Python installation is required to run it. Before opening the video, each EXE shows a camera preview: use `+`/`-` or keys `0`–`9` to choose the webcam, then press **Use this webcam** or `Enter`. Passing `--camera N` skips this screen.

## Getting started

1. Double-click `AVVIA_LOCALE.bat`.
2. In the start menu, choose **Normal Vanish**, **Naruto Vanish**, **Particles**, **Goku**, or **Itachi Uchiha Disappear** with the mouse or keys `1` to `5`.
3. Choose your webcam in the preview, then confirm with the button or `Enter`.
   Goku then asks how long to hold the gesture to disappear or reappear: press
   `Enter` for the default 1 second, or type a positive decimal such as `0.5`
   or `0.1`. A decimal comma (`0,5`) also works. Cancel stops the launch.
4. Step out of the camera frame for 4 seconds while the empty background is captured.

**Normal Vanish:** Raise your index and middle fingers in a V sign. The dissolve starts as soon as the gesture is recognized and lasts about 3.6 seconds.

**Particles:** Make the same V sign as in Normal Vanish. Your silhouette breaks into small colored fragments that drift sideways as if carried by the wind. The effect lasts about 2.1 seconds. It captures your silhouette once when the effect starts to keep the video smooth.

**Goku:** After choosing the webcam, set the gesture hold time (default 1 second; decimals such as `0.5` and `0.1` are accepted). Hold your index and middle fingers straight and together against your forehead for the selected duration. Animated vertical comic-style lines run across your silhouette just before you teleport away and linger briefly afterward. To reappear, lower your hand, then repeat the gesture for the same selected duration. The return uses the reverse effect. If you break the pose, the countdown starts over. `assets/teleport.MP3` plays on both disappearance and reappearance. The terminal shows the countdown for each gesture. The `V` and `R` keys are disabled in this mode: the gesture is the only way to disappear and reappear. No text is overlaid on the video.

Italiano: in modalita Goku, dopo la scelta della webcam compare una finestra
per impostare il tempo di mantenimento del gesto per sparire o riapparire.
Premi `Invio` per 1 secondo, oppure inserisci per esempio `0.5`, `0.1` o `0,5`.
Il valore deve essere maggiore di zero. `Continua` conferma; `Annulla` o `ESC`
chiudono l'avvio. Sparizione e riapparizione usano entrambe il tempo scelto.

**Naruto Vanish:** Bring your palms together in front of the webcam, with your fingers side by side rather than interlaced. Keep both hands visible. As soon as the gesture is recognized, you vanish in a cloud of smoke and a wooden log appears, falls, and remains visible until you press `R`. No microphone is needed. Naruto mode uses `hand_landmarker.task` to track both hands. `assets/vanish.MP3` plays through your computer speakers when the disappearance starts, including when triggered with `V`. You can trigger it again after pressing `R`.

**Itachi Uchiha Disappear:** Touch both hands in front of the center of your chest, with both hands visible. Parts of your captured silhouette turn into individually flapping, cel-shaded crows that fly in curved paths. Larger crows cross the foreground, with brief ink edges, flight streaks and drifting feathers. A translucent blood-red ink texture covers the captured room during the transformation and remains while you are invisible. The supplied Sharingan eyes appear briefly at the top of the frame, then fade away. Release your hands, then touch them at your chest again to reappear as the crows converge and reconstruct your silhouette; the red background fades back to the real room. The transition lasts about 4 seconds in each direction. `V` previews the disappearance and `R` starts the animated return when you are back in frame. This mode uses the bundled hand landmarker and does not add audio. Adjust `EFFECT_SECONDS` and `BODY_RELEASE_SECONDS` in `itachi_effect.py` to tune its pacing.

To start a mode without the menu:

```powershell
local_app\AVVIA_LOCALE.bat --mode naruto
local_app\AVVIA_LOCALE.bat --mode normal
local_app\AVVIA_LOCALE.bat --mode particles
local_app\AVVIA_LOCALE.bat --mode goku
local_app\AVVIA_LOCALE.bat --mode itachi
```

## Virtual camera and OBS

If [OBS Studio](https://obsproject.com/) is installed, the app automatically tries to open **OBS Virtual Camera**. The terminal shows the device name. Use `AVVIA_VIRTUAL.bat` to require a virtual camera. Select **OBS Virtual Camera** in the app that will receive the video. OBS's virtual camera must be stopped while this app is producing its output.

To use the effect in an OBS scene, run `AVVIA_OBS.bat`, add a **Window Capture** source, select **Webcam - Anteprima**, and then start the virtual camera from OBS. Alternatively, use [Unity Capture](https://github.com/schellingb/UnityCapture) as a separate virtual video source:

```powershell
local_app\AVVIA_VIRTUAL.bat --virtual-backend unitycapture
```

OBS has only one virtual camera. Do not use it as both an OBS input and output at the same time. See the [pyvirtualcam documentation](https://github.com/letmaik/pyvirtualcam#supported-virtual-cameras).

## Controls

- `SPACE`: capture a new background.
- `R`: make the person reappear.
- `V`: manually start the selected mode's effect.
- `F`: toggle fullscreen.
- `Q` or `ESC`: quit and release the cameras.

The `V` and `R` keys are disabled in Goku mode.

You can change the camera, resolution, and maximum virtual-output FPS:

```powershell
local_app\AVVIA_LOCALE.bat --camera 1 --width 1280 --height 720 --fps 30
```

To troubleshoot gesture recognition without adding text to the video, pass `--gesture-debug`. Diagnostic information appears only in the terminal.

## Visual assets

The [wooden log](assets/substitution_log.png) is an original illustration generated with ImageGen using the supplied image as a visual reference. Smoke is drawn in real time by `naruto_effect.py` so it follows the person's position and scales with the video. We also considered a [CC0 smoke sprite sheet](https://opengameart.org/content/smoke-sprite-sheet), but the procedural animation adapts better to dynamic positioning without an additional asset.

Goku mode uses the [MediaPipe BlazeFace short-range model](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/web/vision/README.md) to estimate the forehead position and `hand_landmarker.task` to track the fingers. The teleport's visual trace is drawn in code, without anime frames.
