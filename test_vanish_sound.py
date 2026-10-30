"""Exercise both audio backends without an audio device or OS framework."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vanish_sound import SOUND_PATH, VanishSound


class VanishSoundTests(unittest.TestCase):
    def test_mac_uses_native_audio_without_importing_pygame(self):
        native = Mock()
        factory = Mock()
        factory.alloc.return_value.initWithContentsOfFile_byReference_.return_value = native
        with patch("vanish_sound.platform.system", return_value="Darwin"), patch.dict(
            "sys.modules", AppKit=SimpleNamespace(NSSound=factory), pygame=None
        ):
            sound = VanishSound()
            sound.play()
            sound.play()
            sound.close()
        self.assertEqual(native.play.call_count, 2)
        self.assertEqual(native.stop.call_count, 3)

    def test_mac_reports_decode_and_playback_failure(self):
        factory = Mock()
        constructor = factory.alloc.return_value.initWithContentsOfFile_byReference_
        with patch("vanish_sound.platform.system", return_value="Darwin"), patch.dict(
            "sys.modules", AppKit=SimpleNamespace(NSSound=factory)
        ):
            constructor.return_value = None
            with self.assertRaisesRegex(RuntimeError, "decode audio"):
                VanishSound()
            constructor.return_value = Mock()
            sound = VanishSound()
            sound.native_sound.play.return_value = False
            with self.assertRaisesRegex(RuntimeError, "play the disappearance"):
                sound.play()
            sound.close()

    def test_windows_retains_pygame_and_owns_only_its_mixer(self):
        mixer = Mock()
        mixer.get_init.return_value = None
        with patch("vanish_sound.platform.system", return_value="Windows"), patch.dict(
            "sys.modules", pygame=SimpleNamespace(mixer=mixer), AppKit=None
        ):
            sound = VanishSound()
            sound.play()
            sound.close()
            sound.close()
        mixer.Sound.assert_called_once_with(str(SOUND_PATH))
        mixer.Sound.return_value.play.assert_called_once()
        mixer.init.assert_called_once()
        mixer.quit.assert_called_once()

    def test_existing_windows_mixer_is_left_running(self):
        mixer = Mock()
        mixer.get_init.return_value = (44100, -16, 2)
        with patch("vanish_sound.platform.system", return_value="Windows"), patch.dict(
            "sys.modules", pygame=SimpleNamespace(mixer=mixer)
        ):
            sound = VanishSound()
            sound.close()
        mixer.init.assert_not_called()
        mixer.quit.assert_not_called()

    def test_windows_can_still_fall_back_to_ffplay(self):
        with patch("vanish_sound.platform.system", return_value="Windows"), patch.dict(
            "sys.modules", pygame=None
        ), patch("vanish_sound.shutil.which", return_value="ffplay"), patch(
            "vanish_sound.subprocess.Popen"
        ) as process:
            sound = VanishSound()
            sound.play()
            process.return_value.poll.return_value = None
            sound.close()
        self.assertEqual(process.call_args.args[0][0], "ffplay")
        process.return_value.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
