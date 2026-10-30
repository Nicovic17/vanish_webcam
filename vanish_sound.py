"""Preload the Naruto MP3 and play it without blocking video frames."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


SOUND_PATH = Path(__file__).resolve().parent / "assets" / "vanish.MP3"


class VanishSound:
    def __init__(self, path: Path = SOUND_PATH):
        if not path.is_file():
            raise RuntimeError(f"Audio Naruto non trovato: {path}")
        self.path = path

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

    def stop(self) -> None:
        if self.ffplay is not None:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
        elif self.sound is not None:
            self.sound.stop()

    def close(self) -> None:
        self.stop()
        if self.ffplay is not None:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            return
        if self.owns_mixer:
            self.mixer.quit()
            self.owns_mixer = False


def synthesized_samples(kind, sample_rate=44100):
    """Generate original stereo PCM once, with no microphone or network access."""
    import numpy as np
    duration = {"burn": 2.8, "goku": .75, "piccolo": 1.65,
                "electric": .7, "whoosh": .4, "particles": 2.1}.get(kind, .4)
    count = round(duration * sample_rate)
    t = np.arange(count, dtype=np.float32) / sample_rate
    p = t / duration
    rng = np.random.default_rng(9127)
    noise = rng.standard_normal(count).astype(np.float32)
    soft_noise = np.convolve(noise, np.ones(21, np.float32) / 21, mode="same")
    envelope = np.sin(np.pi * p) ** 1.5
    wave = soft_noise * envelope * .65
    if kind == "burn":
        crackle = (rng.random(count) > .996) * noise
        wave += np.convolve(crackle, np.exp(-np.arange(80) / 12), mode="same") * .24 * (1 - p)
        wave += soft_noise * np.exp(-((p - .7) / .14) ** 2) * .65
    elif kind in ("goku", "piccolo", "electric"):
        phase = 2 * np.pi * (260 * t + (900 if kind == "goku" else 420) * t * t)
        wave += np.sin(phase) * envelope * .15
    wave *= np.minimum(1, t / .01) * np.minimum(1, (duration - t) / .025)
    pcm = (np.clip(wave, -.8, .8) * 32767).astype(np.int16)
    return np.ascontiguousarray(np.column_stack((pcm, pcm)))


class ProceduralSound:
    def __init__(self, kind):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        from pygame import mixer
        self.mixer = mixer
        self.owns_mixer = mixer.get_init() is None
        try:
            if self.owns_mixer:
                mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            rate, bits, channels = mixer.get_init()
            if bits != -16 or channels != 2:
                raise RuntimeError("Procedural audio requires a 16-bit stereo mixer.")
            self.samples = synthesized_samples(kind, rate)
            self.sound = mixer.Sound(buffer=self.samples.tobytes())
        except Exception:
            if self.owns_mixer:
                mixer.quit()
            raise

    def play(self):
        self.sound.stop()
        self.sound.play()

    def stop(self):
        self.sound.stop()

    def close(self):
        self.stop()
        if self.owns_mixer:
            self.mixer.quit()
            self.owns_mixer = False
