import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock,patch

import numpy as np

from local_app import goku_settings as settings
from local_app import vanish_cam as app


class SettingsTests(unittest.TestCase):
    def test_parse_default_positive_decimals_and_decimal_comma(self):
        for text,expected in (('',1),('1',1),('0.5',.5),('0.1',.1),(' 0,5 ',.5),('.1',.1),('2.5',2.5)):
            self.assertEqual(settings.parse_goku_delay(text),expected)
        for text in ('0','-1','nan','inf','1.2.3','abc'):
            with self.assertRaises(ValueError):
                settings.parse_goku_delay(text)

    def dialog(self,keys,check=None):
        with ExitStack() as stack:
            for name in ('namedWindow','setMouseCallback','imshow','destroyWindow'):
                stack.enter_context(patch.object(settings.cv2,name))
            stack.enter_context(patch.object(settings.cv2,'getWindowProperty',return_value=1))
            stack.enter_context(patch.object(settings.cv2,'waitKey',side_effect=keys))
            return settings.choose_goku_delay(check_license=check)

    def test_keyboard_default_and_fractional_entry_replace_default(self):
        self.assertEqual(self.dialog([13]),1)
        for text in ('0.5','0.1','0,5','.5'):
            self.assertEqual(self.dialog([*map(ord,text),13]),float(text.replace(',','.')))

    def test_invalid_zero_can_be_corrected_and_license_checked_while_typing(self):
        check=Mock()
        self.assertEqual(self.dialog([ord('0'),13,ord('0'),ord('.'),ord('5'),13],check),.5)
        self.assertEqual(check.call_count,6)
        self.assertIsNone(self.dialog([27]))

    def test_camera_then_delay_then_video_and_cancellation(self):
        for delay in (.1,None):
            args=SimpleNamespace(mode='goku',camera=None,no_mirror=False)
            events=[]
            def camera(**kwargs):
                events.append('camera')
                return 2
            def choose_delay():
                self.assertEqual(args.camera,2)
                events.append('delay')
                return delay
            def video(*args):
                events.append('video')
                self.assertEqual(args[0].goku_delay,.1)
                return 0
            with patch.object(app,'parse_args',return_value=args), \
                 patch.object(app,'choose_camera',side_effect=camera), \
                 patch.object(app,'choose_goku_delay',side_effect=choose_delay), \
                 patch.object(app,'run_camera',side_effect=video):
                self.assertEqual(app.run(),0)
            self.assertEqual(events,['camera','delay']+(['video'] if delay is not None else []))

    def test_other_modes_skip_delay_and_camera_cancel_stops_launch(self):
        for mode in ('naruto','goku'):
            args=SimpleNamespace(mode=mode,camera=None,no_mirror=False)
            with patch.object(app,'parse_args',return_value=args), \
                 patch.object(app,'choose_camera',return_value=None if mode=='goku' else 1), \
                 patch.object(app,'choose_goku_delay') as delay, \
                 patch.object(app,'run_camera',return_value=0) as video:
                self.assertEqual(app.run(),0)
                delay.assert_not_called()
                self.assertEqual(video.call_count,0 if mode=='goku' else 1)

    def test_fractional_choice_controls_both_disappearance_and_reappearance(self):
        clock=[0.]
        times=iter((.1,4.1,4.3,4.401,4.8,4.95,5.35,5.5,5.601,6.0))
        frame=np.full((80,120,3),100,np.uint8)
        capture=Mock()
        def read():
            clock[0]=next(times)
            return True,frame.copy()
        capture.read.side_effect=read
        recognizer=Mock()
        recognizer.recognize_pose.side_effect=lambda image,ms: clock[0] not in (4.95,5.35)
        sound=Mock()
        args=SimpleNamespace(camera=0,width=120,height=80,fps=30,fullscreen=False,
                             no_mirror=True,gesture_debug=False,goku_delay=.1)
        with ExitStack() as stack:
            stack.enter_context(patch('builtins.print'))
            stack.enter_context(patch.object(app,'download_models'))
            stack.enter_context(patch.object(app,'open_camera',return_value=capture))
            stack.enter_context(patch.object(app,'create_tasks',return_value=(Mock(),recognizer)))
            stack.enter_context(patch.object(app,'open_virtual_camera',return_value=None))
            stack.enter_context(patch.object(app,'VanishSound',return_value=sound))
            stack.enter_context(patch.object(app,'person_mask',return_value=np.ones((80,120),np.float32)))
            stack.enter_context(patch.object(app.time,'perf_counter',side_effect=lambda:clock[0]))
            for name in ('namedWindow','resizeWindow','destroyAllWindows','imshow'):
                stack.enter_context(patch.object(app.cv2,name))
            stack.enter_context(patch.object(app.cv2,'waitKey',side_effect=([0]*9+[ord('q')])) )
            with ExitStack() as resources:
                self.assertEqual(app.run_camera(args,resources,'goku'),0)
        self.assertEqual(sound.play.call_count,2)


if __name__=='__main__':
    unittest.main()
