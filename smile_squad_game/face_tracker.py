"""
FaceTracker — MediaPipe FaceMesh wrapper with calibration, EMA smoothing,
hysteresis, adaptive difficulty, FSI computation and session logging.
"""

import os
import sys
import time
import json
import numpy as np
import cv2
import mediapipe as mp
from datetime import datetime


class FaceTracker:
    """
    Wraps MediaPipe FaceMesh with three layers of signal improvement:

    1. CALIBRATION WITH STILLNESS GATING
       Only accepts frames where the face is genuinely still (inter-frame
       landmark motion < STILL_THRESH). The patient must hold steady
       for CALIB_TARGET consecutive-ish still frames (~3 s).

    2. EXPONENTIAL MOVING AVERAGE (EMA) SMOOTHING
       Raw landmark measurements are smoothed with a low-pass EMA filter
       (alpha=0.15) before any expression score is computed. Expression scores
       get a second pass of EMA (alpha=0.25).

    3. HYSTERESIS ON TRIGGERS
       Each expression activates at 0.65 and only deactivates when it drops
       back below 0.30, preventing rapid on/off flickering.

    Also computes:
    - Facial Symmetry Index (FSI): 1 = symmetric, 0 = fully asymmetric
    - Rep counting per muscle group
    - Adaptive difficulty tied to patient's range of motion
    """

    CALIB_TARGET = 60
    STILL_THRESH = 0.014
    EMA_RAW = 0.15
    EMA_EXPR = 0.25
    HYSTER_ON = 0.65
    HYSTER_OFF = 0.30

    # ── Landmark index groups (MediaPipe 468-point mesh) ──────────────────────
    _L_MOUTH_IDX = [61, 76, 77]
    _R_MOUTH_IDX = [291, 306, 307]
    _UPPER_LIP = [13, 312, 82]
    _LOWER_LIP = [14, 317, 87]
    _L_EYE_TOP = [159, 160, 161]
    _R_EYE_TOP = [386, 385, 384]
    _L_BROW_IDX = [70, 63, 105]
    _R_BROW_IDX = [300, 293, 334]
    _NOSE_TIP = [4, 5, 6]

    def __init__(self):
        mp_fm = mp.solutions.face_mesh

        # Suppress MediaPipe C++ stderr initialization warnings (XNNPACK/absl)
        # We keep stderr muted through constructor + a dummy .process() call
        # to force all lazy C++ init (XNNPACK delegate, worker threads) to
        # complete while stderr is silenced.
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            old_stderr = os.dup(sys.stderr.fileno())
            os.dup2(devnull, sys.stderr.fileno())
        except Exception:
            old_stderr = None

        try:
            self.face_mesh = mp_fm.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.60,
                min_tracking_confidence=0.60,
            )
            # Dummy process to trigger XNNPACK delegate creation while muted
            _dummy = np.zeros((100, 100, 3), dtype=np.uint8)
            self.face_mesh.process(_dummy)
            time.sleep(0.15)
        finally:
            if old_stderr is not None:
                os.dup2(old_stderr, sys.stderr.fileno())
                os.close(old_stderr)
                os.close(devnull)

        self.draw_spec = mp.solutions.drawing_utils.DrawingSpec(
            color=(0, 200, 140), thickness=1, circle_radius=1)
        self.mp_fm = mp_fm

        # ── Calibration state ────────────────────────────────────────────────
        self.calibrated = False
        self._still_buf = []
        self._prev_raw = None
        self._still_streak = 0
        self.calib_progress = 0.0
        self.is_still = False
        self._baseline = {}

        # ── EMA state ────────────────────────────────────────────────────────
        self._raw_ema = {}
        self._expr_ema = {"smile": 0.0, "eyebrow": 0.0, "pucker": 0.0}

        # ── Hysteresis state ─────────────────────────────────────────────────
        self._expr_active = {"smile": False, "eyebrow": False, "pucker": False}

        # ── Adaptive thresholds ──────────────────────────────────────────────
        self.thresh = {"smile": 0.055, "eyebrow": 0.048, "pucker": 0.038}

        # ── Public live values ───────────────────────────────────────────────
        self.face_detected = False
        self.expressions = {"smile": 0.0, "eyebrow": 0.0, "pucker": 0.0}
        self.fsi = 1.0
        self.motion_level = 0.0

        # ── Session log ──────────────────────────────────────────────────────
        self.fsi_history = []
        self.rep_log = []
        self.rep_count = {"smile": 0, "eyebrow": 0, "pucker": 0}

    # ─────────────────────────── geometry helpers ─────────────────────────────
    def _cluster(self, lms, indices, w, h):
        """Return the centroid of a cluster of landmarks (sub-pixel accuracy)."""
        pts = [np.array([lms[i].x * w, lms[i].y * h]) for i in indices]
        return np.mean(pts, axis=0)

    def _d(self, a, b):
        return float(np.linalg.norm(a - b))

    def _iod(self, lms, w, h):
        """Inter-ocular distance — normalization denominator."""
        l = self._cluster(lms, self._L_EYE_TOP, w, h)
        r = self._cluster(lms, self._R_EYE_TOP, w, h)
        return max(self._d(l, r), 1.0)

    # ─────────────────────────── measurements ────────────────────────────────
    def _measure(self, lms, w, h):
        scale = self._iod(lms, w, h)
        lm = self._cluster(lms, self._L_MOUTH_IDX, w, h)
        rm = self._cluster(lms, self._R_MOUTH_IDX, w, h)
        ul = self._cluster(lms, self._UPPER_LIP, w, h)
        ll = self._cluster(lms, self._LOWER_LIP, w, h)
        let = self._cluster(lms, self._L_EYE_TOP, w, h)
        ret = self._cluster(lms, self._R_EYE_TOP, w, h)
        lb = self._cluster(lms, self._L_BROW_IDX, w, h)
        rb = self._cluster(lms, self._R_BROW_IDX, w, h)
        nos = self._cluster(lms, self._NOSE_TIP, w, h)

        mouth_w = self._d(lm, rm) / scale
        lip_h = self._d(ul, ll) / scale
        l_brow = self._d(lb, let) / scale
        r_brow = self._d(rb, ret) / scale
        brow_avg = (l_brow + r_brow) / 2.0
        pucker_r = lip_h / max(mouth_w, 0.01)
        l_mouth_d = self._d(lm, nos) / scale
        r_mouth_d = self._d(rm, nos) / scale

        return {
            "mouth_w": mouth_w, "lip_h": lip_h,
            "l_brow": l_brow, "r_brow": r_brow, "brow_avg": brow_avg,
            "pucker_r": pucker_r,
            "l_mouth_d": l_mouth_d, "r_mouth_d": r_mouth_d,
        }

    # ─────────────────────────── EMA smoothing ────────────────────────────────
    def _ema_raw(self, m):
        if not self._raw_ema:
            self._raw_ema = dict(m)
            return dict(m)
        a = self.EMA_RAW
        for k in m:
            self._raw_ema[k] = a * m[k] + (1 - a) * self._raw_ema[k]
        return dict(self._raw_ema)

    def _ema_expr(self, scores):
        a = self.EMA_EXPR
        for k in scores:
            self._expr_ema[k] = a * scores[k] + (1 - a) * self._expr_ema[k]
        return dict(self._expr_ema)

    # ─────────────────────────── FSI ─────────────────────────────────────────
    def _calc_fsi(self, m):
        mouth_asym = abs(m["l_mouth_d"] - m["r_mouth_d"])
        brow_asym = abs(m["l_brow"] - m["r_brow"])
        combined = mouth_asym * 0.65 + brow_asym * 0.35
        return float(max(0.0, min(1.0, 1.0 - combined * 4.5)))

    # ─────────────────────────── stillness gate ───────────────────────────────
    def _motion_delta(self, m_new):
        if self._prev_raw is None:
            self._prev_raw = dict(m_new)
            return 0.0
        keys = ["mouth_w", "brow_avg", "pucker_r"]
        delta = float(np.mean([abs(m_new[k] - self._prev_raw[k]) for k in keys]))
        self._prev_raw = dict(m_new)
        return delta

    # ─────────────────────────── calibration ─────────────────────────────────
    def _feed_calibration(self, m_raw):
        delta = self._motion_delta(m_raw)
        self.motion_level = min(delta / (self.STILL_THRESH * 2), 1.0)
        self.is_still = delta <= self.STILL_THRESH

        if self.is_still:
            self._still_buf.append(m_raw)
        else:
            discard = min(1, len(self._still_buf))
            self._still_buf = self._still_buf[:-discard] if discard else self._still_buf

        accepted = len(self._still_buf)
        self.calib_progress = min(accepted / self.CALIB_TARGET, 1.0)

        if accepted >= self.CALIB_TARGET:
            self._baseline = {
                k: float(np.median([f[k] for f in self._still_buf]))
                for k in self._still_buf[0]
            }
            self.calibrated = True
            self._still_buf = []
            self._prev_raw = None
            self._raw_ema = {}

    # ─────────────────────────── hysteresis ──────────────────────────────────
    def _apply_hysteresis(self, scores):
        for k, v in scores.items():
            if not self._expr_active[k] and v >= self.HYSTER_ON:
                self._expr_active[k] = True
            elif self._expr_active[k] and v < self.HYSTER_OFF:
                self._expr_active[k] = False
        return dict(self._expr_active)

    # ─────────────────────────── main update ─────────────────────────────────
    def update(self, frame):
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = self.face_mesh.process(rgb)

        self.face_detected = False
        if not res.multi_face_landmarks:
            self.is_still = False
            self.motion_level = 0.0
            return frame

        self.face_detected = True
        lms = res.multi_face_landmarks[0].landmark

        # Draw mesh overlay
        mp.solutions.drawing_utils.draw_landmarks(
            frame, res.multi_face_landmarks[0],
            self.mp_fm.FACEMESH_CONTOURS,
            landmark_drawing_spec=None,
            connection_drawing_spec=self.draw_spec,
        )

        m_raw = self._measure(lms, w, h)

        if not self.calibrated:
            self._feed_calibration(m_raw)
            return frame

        m = self._ema_raw(m_raw)

        self.fsi = self._calc_fsi(m)
        self.fsi_history.append(self.fsi)
        if len(self.fsi_history) > 3600:
            self.fsi_history = self.fsi_history[-1800:]

        raw_scores = {
            "smile": max((m["mouth_w"] - self._baseline["mouth_w"]) / self.thresh["smile"], 0.0),
            "eyebrow": max((m["brow_avg"] - self._baseline["brow_avg"]) / self.thresh["eyebrow"], 0.0),
            "pucker": max((m["pucker_r"] - self._baseline["pucker_r"]) / self.thresh["pucker"], 0.0),
        }

        smile_inhibition = min(raw_scores["smile"] * 1.8, 1.0)
        raw_scores["pucker"] = raw_scores["pucker"] * (1.0 - smile_inhibition)

        for k in raw_scores:
            raw_scores[k] = min(raw_scores[k], 1.0)

        smoothed = self._ema_expr(raw_scores)
        self.expressions = smoothed
        self._apply_hysteresis(smoothed)

        return frame

    # ─────────────────────────── public helpers ───────────────────────────────
    def expr_triggered(self, name):
        """True if expression has crossed activation threshold (hysteresis)."""
        return self._expr_active[name]

    def log_rep(self, expr_name):
        self.rep_count[expr_name] += 1
        self.rep_log.append({
            "t": round(time.time(), 2),
            "expr": expr_name,
            "fsi": round(self.fsi, 3),
        })

    # ─────────────────────────── adaptive difficulty ──────────────────────────
    def adapt_difficulty(self):
        if len(self.fsi_history) < 30:
            return
        recent = float(np.mean(self.fsi_history[-120:]))
        factor = 1.06 if recent > 0.72 else (0.94 if recent < 0.48 else 1.0)
        for k in self.thresh:
            self.thresh[k] = round(max(0.025, min(0.22, self.thresh[k] * factor)), 4)

    # ─────────────────────────── session save ────────────────────────────────
    def save_session(self):
        if not self.rep_log and not self.fsi_history:
            return None
        os.makedirs("session_data", exist_ok=True)
        tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"session_data/session_{tag}.json"
        avg_fsi = round(float(np.mean(self.fsi_history)), 3) if self.fsi_history else 0.0
        payload = {
            "date": datetime.now().isoformat(),
            "total_reps": self.rep_count,
            "avg_fsi": avg_fsi,
            "final_thresholds": self.thresh,
            "fsi_timeline": [round(v, 3) for v in self.fsi_history[::30]],
            "rep_log": self.rep_log,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        return path
