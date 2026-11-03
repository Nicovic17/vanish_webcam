"""Keep MediaPipe's internal ROI notice out of the local app console.

The HandLandmarker task does not expose its calculator graph, so the app
cannot connect IMAGE_DIMENSIONS to that graph. Other stderr messages remain
visible, including actual model and camera errors.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_ROI_NOTICE = b"Using NORM_RECT without IMAGE_DIMENSIONS is only supported for the square ROI."
_ROI_SOURCE = b"landmark_projection_calculator.cc:"
_CHILD_MARKER = "VANISH_CAM_FILTERED_CHILD"


def forward_stderr(source, destination) -> None:
    for line in source:
        if _ROI_SOURCE in line and _ROI_NOTICE in line:
            continue
        if hasattr(destination, "buffer"):
            destination.buffer.write(line)
        else:
            try:
                destination.write(line)
            except TypeError:
                destination.write(line.decode("utf-8", errors="replace"))
        destination.flush()


def run_local_filtered(script: Path, arguments: list[str]) -> int:
    environment = os.environ.copy()
    environment[_CHILD_MARKER] = "1"
    process = subprocess.Popen(
        [sys.executable, str(script), *arguments],
        stdin=None,
        stdout=None,
        stderr=subprocess.PIPE,
        env=environment,
    )
    try:
        assert process.stderr is not None
        forward_stderr(process.stderr, sys.stderr)
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        return 130
    finally:
        if process.stderr is not None:
            process.stderr.close()


def needs_filter(arguments: list[str]) -> bool:
    return (os.environ.get(_CHILD_MARKER) != "1"
            and not any(flag in arguments for flag in ("--self-test", "--help", "-h")))
