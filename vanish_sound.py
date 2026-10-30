"""Preload the Naruto MP3 and play it without blocking video frames."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


SOUND_PATH = Path(__file__).resolve().parent / "assets" / "vanish.MP3"


class VanishSound:
    def __init__(self, path: Path = SOUND_PATH):
        if not path.is_file():
            raise RuntimeError(f"Audio Naruto non trovato: {path}")
        self.path = path
        self.native_sound = None

        if platform.system() == "Darwin":
            # Use the system decoder instead of loading a second SDL library
            # beside OpenCV's copy (duplicate Objective-C classes can crash).
            from AppKit import NSSound
            self.native_sound = NSSound.alloc().initWithContentsOfFile_byReference_(
                str(path), False
            )
            if self.native_sound is None:
                raise RuntimeError(f"Unable to decode audio: {path}")
            return

        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        self.process = None
        self.ffplay = None
        try:
            from pygame import mixer
        except ImportError:
            self.ffplay = shutil.which("ffplay")
            if self.ffplay is None:
                raise RuntimeError("Per riprodurre vanish.MP3 installa pygame o ffplay.")
            return

        self.mixer = mixer
        self.owns_mixer = mixer.get_init() is None
        try:
            if self.owns_mixer:
                mixer.init(frequency=44100, size=-16, channels=2, buffer=256)
            self.sound = mixer.Sound(str(path))  # Decode once, before opening the webcam.
        except Exception as error:
            if self.owns_mixer:
                mixer.quit()
            raise RuntimeError(f"Impossibile aprire l'audio Naruto: {error}") from error

    def play(self) -> None:
        if self.native_sound is not None:
            self.native_sound.stop()
            if not self.native_sound.play():
                raise RuntimeError("Unable to play the disappearance sound.")
            return
        if self.ffplay is not None:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            try:
                self.process = subprocess.Popen(
                    [self.ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet",
                     "-i", str(self.path)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as error:
                raise RuntimeError(f"Impossibile avviare l'audio Naruto: {error}") from error
            return
        self.sound.stop()
        if self.sound.play() is None:
            raise RuntimeError("Impossibile avviare l'audio Naruto: nessun canale libero.")

    def close(self) -> None:
        if self.native_sound is not None:
            self.native_sound.stop()
            return
        if self.ffplay is not None:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            return
        if self.owns_mixer:
            self.mixer.quit()
            self.owns_mixer = False
