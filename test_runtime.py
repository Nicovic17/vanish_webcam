import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from vanish_runtime import FramePacket, InferenceWorker, LatestFrameCapture


class WorkerTests(unittest.TestCase):
    def test_background_strips_preserve_original_median(self):
        from vanish_runtime import build_background
        rng = np.random.default_rng(42)
        samples = [rng.integers(0, 256, (125, 160, 3), dtype=np.uint8) for _ in range(18)]
        expected = np.median(np.stack(samples), axis=0).astype(np.uint8)
        np.testing.assert_array_equal(build_background(samples), expected)

    def test_pending_inference_keeps_only_newest_and_never_blocks_submit(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        calls = []
        def process(packet):
            calls.append(packet.sequence)
            if packet.sequence == 1:
                entered.set()
                release.wait(2)
            else:
                finished.set()
            return packet
        processor = SimpleNamespace(process=process, close=Mock())
        worker = InferenceWorker(lambda: processor)
        try:
            frame = np.zeros((2, 2, 3), np.uint8)
            worker.submit(FramePacket(1, 0, frame))
            self.assertTrue(entered.wait(2))
            for sequence in range(2, 100):
                worker.submit(FramePacket(sequence, 0, frame))
            self.assertEqual(worker.pending.sequence, 99)
            release.set()
            self.assertTrue(finished.wait(2))
        finally:
            release.set()
            worker.close()
        self.assertEqual(calls, [1, 99])
        self.assertFalse(worker.thread.is_alive())
        processor.close.assert_called_once()

    def test_inference_error_reaches_main_and_closes_models(self):
        failed = threading.Event()
        def process(packet):
            failed.set()
            raise RuntimeError("bad model")
        processor = SimpleNamespace(process=process, close=Mock())
        worker = InferenceWorker(lambda: processor)
        worker.submit(FramePacket(1, 0, np.zeros((2, 2, 3), np.uint8)))
        self.assertTrue(failed.wait(2))
        worker.thread.join(2)
        with self.assertRaisesRegex(RuntimeError, "bad model"):
            worker.poll()
        worker.close()
        processor.close.assert_called_once()

    def test_capture_publishes_latest_and_releases_device(self):
        produced = threading.Event()
        calls = [0]
        def read():
            calls[0] += 1
            if calls[0] >= 20:
                produced.set()
                time.sleep(.005)
            return True, np.full((2, 2, 3), calls[0] % 255, np.uint8)
        capture = SimpleNamespace(read=read, release=Mock())
        reader = LatestFrameCapture(capture)
        try:
            self.assertTrue(produced.wait(2))
            packet = reader.read(timeout=1)
            self.assertGreaterEqual(packet.sequence, 19)
            self.assertEqual(packet.frame[0, 0, 0], packet.sequence % 255)
        finally:
            reader.close()
        self.assertFalse(reader.thread.is_alive())
        capture.release.assert_called_once()

    def test_capture_exception_propagates_and_releases_device(self):
        capture = SimpleNamespace(read=Mock(side_effect=RuntimeError("camera disconnected")), release=Mock())
        reader = LatestFrameCapture(capture)
        try:
            with self.assertRaisesRegex(RuntimeError, "camera disconnected"):
                reader.read(timeout=1)
        finally:
            reader.close()
        capture.release.assert_called_once()
