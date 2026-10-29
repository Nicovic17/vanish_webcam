import subprocess
import unittest
from unittest.mock import patch

from vanish_sound import SOUND_PATH, VanishSound


class MacAudioTests(unittest.TestCase):
    @patch("vanish_sound.subprocess.Popen")
    @patch("vanish_sound.shutil.which", return_value="/usr/bin/afplay")
    @patch("vanish_sound.sys.platform", "darwin")
    def test_macos_uses_native_player(self, which, popen):
        sound = VanishSound()
        which.assert_called_once_with("afplay")
        sound.play()
        self.assertEqual(popen.call_args.args[0], ["/usr/bin/afplay", str(SOUND_PATH)])
        self.assertEqual(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(popen.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(popen.call_args.kwargs["stderr"], subprocess.DEVNULL)
        popen.return_value.poll.return_value = None
        sound.close()
        popen.return_value.terminate.assert_called_once()

    @patch("vanish_sound.shutil.which", return_value=None)
    @patch("vanish_sound.sys.platform", "darwin")
    def test_missing_native_player_reports_error(self, which):
        with self.assertRaisesRegex(RuntimeError, "afplay"):
            VanishSound()
        which.assert_called_once_with("afplay")


if __name__ == "__main__":
    unittest.main()
