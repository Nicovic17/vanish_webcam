import unittest
from vanish_hud import guidance

class GuidanceTests(unittest.TestCase):
    def test_countdown_never_invites_user_back_before_capture_finishes(self):
        self.assertIn("STEP OUT", guidance("calibrating", 0, 0, "goku", 4)[0])
        self.assertIn("STAY OUT", guidance("calibrating", 3, 0, "goku", 4)[0])
        self.assertIn("STAY OUT", guidance("calibrating", 5, 0, "goku", 4)[0])
    def test_seven_second_instructions_and_return_hint(self):
        self.assertIn("forehead", guidance("ready", 4, 0, "goku", 4)[1])
        self.assertIsNone(guidance("ready", 12, 7, "goku", 4))
        self.assertIn("REAPPEAR", guidance("vanished", 20, 12, "goku", 4)[0])
    def test_goku_hold_progress_visible_after_intro(self):
        self.assertEqual(guidance("ready", 20, 12, "goku", 4, .6)[2], "0.4s")
