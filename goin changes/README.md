# PR handoff

Branch: `codex/vanishcam-effects`
Upstream: `Nicovic17/vanish_webcam` (`main`)

Before opening the PR, run:

```powershell
cd C:\Users\LOQ\vanish_webcam
.\.venv-local\Scripts\python.exe -m unittest discover -q
.\.venv-local\Scripts\python.exe vanish_cam.py --self-test
git status --short
```

Commit and push from your own GitHub fork. The local `origin` points to the upstream author's repository; do not push there. See chat response for exact fork, push, and PR commands. Review the PR diff before submitting. `diagnostics/`, `models/`, and `.venv-local/` are local and ignored.
