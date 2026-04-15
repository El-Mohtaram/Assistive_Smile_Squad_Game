"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         S M I L E   S Q U A D                               ║
║              Asymmetrical Co-Op Facial Rehabilitation Game                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Player 1 → Keyboard (WASD / Arrow Keys)  — runs, jumps                     ║
║  Player 2 → Webcam  (Facial Expressions)  — controls the environment        ║
║                                                                              ║
║  Scientific Features:                                                        ║
║  • Real-time Facial Symmetry Index (FSI)                                     ║
║  • Nose-origin coordinate normalization (camera-position invariant)          ║
║  • Adaptive difficulty tied to patient's range of motion                     ║
║  • Calibration to patient-specific neutral baseline                          ║
║  • Session JSON log for physician review                                     ║
║  • Rep counting per muscle group (smile / eyebrow / pucker)                 ║
║                                                                              ║
║  Install:  pip install mediapipe opencv-python pygame numpy                  ║
║  Run:      python main.py                                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import warnings

# Suppress protobuf dependency warnings sometimes seen with Mediapipe
warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf.symbol_database")
# Suppress some common C++ backend warnings from TensorFlow/Mediapipe layers
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '2'

from smile_squad_game.game import SmileSquad

if __name__ == "__main__":
    # Fix console encoding on Windows (avoids UnicodeEncodeError with box-drawing chars)
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("========================================")
    print("       SMILE SQUAD  --  Loading         ")
    print("========================================")
    print()
    print("Controls:")
    print("  Player 1 (keyboard)  -> WASD or Arrow keys")
    print("  Player 2 (webcam)    -> Facial expressions")
    print()
    print("Facial controls:")
    print("  SMILE WIDE      -> opens doors")
    print("  RAISE EYEBROWS  -> lifts bridges")
    print("  PUCKER LIPS     -> activates shield")
    print()
    print("Session data will be saved to ./session_data/")
    print("Starting game...")
    print()

    game = SmileSquad()
    game.run()
