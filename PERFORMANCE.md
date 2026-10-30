# Performance notes

Measured locally on the i7-13650HX Windows laptop at 1280×720. Results are workload dependent; run `benchmark_vanishcam.py` to reproduce the effect benchmark and add `--live` for camera/inference measurements.

## Baseline before changes

Warm synthetic stage timings, 20 samples per stage:

| Stage | Mean ms | p95 ms |
| --- | ---: | ---: |
| Hand detection with no-hand retry views | 61.23 | 67.80 |
| Full-resolution segmentation/postprocessing | 174.74 | 192.50 |
| Normal effect at midpoint | 169.22 | 175.51 |
| Naruto effect at midpoint | 131.48 | 146.26 |

The original loop ran these operations synchronously. OpenCV defaulted to 20 threads. Limiting OpenCV to one thread reduced the Normal-effect median to approximately 44 ms before changing its compositing implementation.

## Changes and measurement limits

Capture and inference now use independent workers with bounded latest-frame slots. The render loop uses immutable published results. Segmentation is requested for transition snapshots and Normal's moving dissolve, rather than on every idle detection. CPU image operations use reduced-resolution effect fields, native blending, reusable buffers and silhouette bounding regions. Transition preparation also runs off the render thread.

A prior 12-second synthetic-effect plus camera workload reached 30 output FPS and 28 fresh-camera FPS. Results depend on lighting and camera state; the later hardware check returned black frames at about one frame per second.

The benchmark writes local timing files under `diagnostics/`. The effect benchmark samples the whole transition, whereas the original baseline sampled one midpoint; use these as evidence of bottleneck reduction, not a perfectly matched speedup ratio. Background load caused substantial timing variation between runs. Every mode is also checked for deterministic reverse seeking, unchanged inputs, valid output shape and exact clean-background endpoints (Naruto intentionally leaves the log).

Remaining hardware validation: test real gesture poses and lighting interactively, then install a virtual-camera driver and verify the selected receiving app. The OBS installation attempt returned Windows error 0x800704c7 (operation canceled by the user). No universal receiving-app compatibility claim is made.

## Current validation

`python -m unittest discover -q` passes 72 tests. `python vanish_cam.py --self-test` loads hand, face, and segmentation models and checks image/audio assets. Synthetic mode timings are produced locally by `python benchmark_vanishcam.py`; these vary with CPU load and are not included in the PR.

Real gesture behavior and virtual-camera compatibility still require hardware testing. On the development PC, the latest physical-camera check returned black frames at about one frame per second, so Goku could not be verified with a live hand. OBS installation was canceled by Windows with `0x800704c7`; virtual output remains unverified.
