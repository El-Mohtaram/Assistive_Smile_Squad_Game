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
    SINGLETON CameraReader.
    
    CRITICAL FIX: This class is now a Singleton. When game.py calls .release() 
    and CameraReader(0) between levels, this Singleton fakes the release and 
    returns the persistently running thread. 
    
    This flushes the software buffers (as requested) but NEVER power-cycles the 
    Windows USB driver, completely eliminating the 100% Frame Dropped error!
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CameraReader, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, src=0):
        if self._initialized:
            # Re-instantiated between levels! Flush the frame buffer safely.
            with self._lock:
                self._frame = None
            self._fail_count = 0
            return

        # First-time initialization
        self._src        = src
        self._cap        = None
        self._frame      = None
        self._lock       = threading.Lock()
        self._running    = True
        self._fail_count = 0
        self._thread     = None
        
        self._open_camera()
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()
        self._initialized = True

    def _open_camera(self):
        if self._cap is not None:
            try: self._cap.release()
            except: pass
            
        print("[CameraReader] Opening hardware stream (PERMANENT LOCK)...")
        cap = cv2.VideoCapture(self._src)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._cap = cap
        else:
            try: cap.release()
            except: pass
            self._cap = None

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
                time.sleep(0.033)
                
                # Only log if it's actually dead, ignore normal 1-frame drops
                if self._fail_count >= 150:
                    print("[CameraReader] Hardware starved. Re-initializing connection...")
                    self._fail_count = 0
                    self._open_camera()

    def read(self):
        with self._lock:
            if self._frame is None:
                return None
            # CRITICAL FIX: Consume the frame so the AI thread doesn't 
            # re-process the exact same image and burn 100% CPU!
            f = self._frame.copy()
            self._frame = None
            return f

    def release(self):
        """
        FAKE RELEASE! The game requests a release between levels to "flush" the 
        camera. We flush our software buffers to reset the state, but we DO NOT 
        release the hardware lock. This permanently fixes the frame dropping.
        """
        with self._lock:
            self._frame = None
        self._fail_count = 0
        # Notice we do NOT stop self._running or self._cap.


class FaceProcessorThread:
    """
    Runs FaceTracker.update() in a background thread.

    Pipeline: CameraReader → flip → tracker.update() → resize → RGB convert
    The game loop calls .get_latest() to instantly grab the newest result.
    Face-tracker state (expressions, FSI, calibration) is updated in-place
    on the tracker object; CPython's GIL keeps simple attribute reads safe.
    """

    def __init__(self, cam_reader, tracker):
        self._cam_reader = cam_reader
        self._tracker    = tracker
        self._lock       = threading.Lock()
        self._rgb_array  = None     # latest display-ready numpy array (W,H,3)
        self._running    = False
        self._thread     = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            frame = self._cam_reader.read()
            if frame is None:
                # Sleep to wait for a NEW frame
                time.sleep(0.01)
                continue

            try:
                frame = cv2.flip(frame, 1)
                frame = self._tracker.update(frame)

                small = cv2.resize(frame, (CAM_DISP_W, CAM_DISP_H))
                rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                rgb_t = rgb.transpose(1, 0, 2)     # (H,W,3) → (W,H,3) for pygame

                with self._lock:
                    self._rgb_array = rgb_t

            except Exception as e:
                # FIX: silently skip bad frame — thread stays alive
                time.sleep(0.01)
                continue

    def get_latest(self):
        """Return the latest display-ready RGB array (or None)."""
        with self._lock:
            return self._rgb_array.copy() if self._rgb_array is not None else None

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)