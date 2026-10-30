# VanishCam effect and runtime update

The webcam preview now guides background capture and gesture timing, then supports eight silhouette effects with hand-sign return. Goku accepts an adjacent two-finger forehead/temple pose, shows its one-second hold, and retains recognized gestures while the transition snapshot is prepared. Local preview guidance does not enter direct virtual-camera output.

Capture and inference use bounded latest-frame workers. Segmentation runs when needed, effects render from reduced-size fields, and the virtual-camera output remains unmirrored RGB. OBS and Unity Capture are tried in order, with a preview fallback and clear driver guidance. Mute/help controls, black-camera detection, recoverable audio errors, and a one-click self-test improve setup and troubleshooting.

Validation: `python -m unittest discover -q` (72 tests), `python vanish_cam.py --self-test`, and `git diff --check`. The synthetic preview and timings can be regenerated with `python benchmark_vanishcam.py`. Live hand gestures and OBS virtual-camera output need testing on a machine with a working camera and installed driver; the development camera returned black frames and the OBS installer was canceled.
