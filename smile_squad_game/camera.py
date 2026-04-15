"""
Threaded Camera and Face Processing integration.
"""

import threading
import time
import cv2
import numpy as np
from .constants import CAM_DISP_W, CAM_DISP_H

class CameraReader:
    """
    Reads webcam frames in a background daemon thread.

    Key properties:
    • Only the LATEST frame is kept — no buffering lag.
    • If the camera disconnects, it auto-reconnects after a cooldown.
    • The game loop calls .read() which returns instantly (never blocks).
    """

    def __init__(self, src=0):
        self._src = src
        self._cap = None
        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._fail_count = 0
        self._open_camera()
        self._start()

    def _open_camera(self):
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
        self._cap = cv2.VideoCapture(self._src)
        if self._cap.isOpened():
            # Minimize internal buffer so we always get the latest frame
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._fail_count = 0

    def _start(self):
        self._running = True
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def _reader_loop(self):
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(1.0)
                self._open_camera()
                continue

            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._frame = frame
                self._fail_count = 0
            else:
                self._fail_count += 1
                if self._fail_count > 30:
                    # Camera probably disconnected — try to reconnect
                    self._open_camera()
                    time.sleep(0.5)

    def read(self):
        """Return the latest frame instantly (or None)."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def release(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass


class FaceProcessorThread:
    """
    Runs FaceTracker.update() in a background thread.

    Pipeline:  CameraReader → flip → tracker.update() → resize → RGB convert
    The game loop calls .get_latest() to instantly grab the newest result.
    Face-tracker state (expressions, FSI, calibration) is updated in-place
    on the tracker object; CPython's GIL keeps simple attribute reads safe.
    """

    def __init__(self, cam_reader, tracker):
        self._cam_reader = cam_reader
        self._tracker = tracker
        self._lock = threading.Lock()
        self._rgb_array = None  # latest display-ready numpy array (W,H,3)
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            frame = self._cam_reader.read()
            if frame is None:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            frame = self._tracker.update(frame)

            # Prepare display-ready array for pygame (resize + color convert)
            small = cv2.resize(frame, (CAM_DISP_W, CAM_DISP_H))
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            rgb_t = rgb.transpose(1, 0, 2)  # (H,W,3) → (W,H,3) for pygame

            with self._lock:
                self._rgb_array = rgb_t

    def get_latest(self):
        """Return the latest display-ready RGB array (or None)."""
        with self._lock:
            return self._rgb_array.copy() if self._rgb_array is not None else None

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
