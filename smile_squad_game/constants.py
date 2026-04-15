"""
Constants — screen dimensions, colors, physics, and MediaPipe landmark indices.
"""

# ── Screen & Physics ─────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 720
CAM_DISP_W, CAM_DISP_H = 320, 240
FPS = 60
GRAVITY = 0.55
JUMP_VEL = -13.5
PLAYER_SPEED = 5

# ── Palette — deep space medical theme ────────────────────────────────────────
C_BG_TOP = (8, 12, 35)
C_BG_BOT = (18, 28, 60)
C_PLATFORM = (45, 90, 200)
C_PLAT_TOP = (80, 140, 255)
C_PLAYER = (255, 210, 70)
C_PLAYER_SH = (200, 155, 20)
C_DOOR_CLOSED = (220, 60, 60)
C_DOOR_OPEN = (60, 230, 100)
C_BRIDGE = (180, 130, 50)
C_BRIDGE_LT = (220, 180, 90)
C_SHIELD = (80, 200, 255)
C_ROCK = (140, 90, 55)
C_GOAL = (80, 255, 140)
C_TEXT = (230, 235, 255)
C_GOOD = (80, 255, 140)
C_WARN = (255, 210, 60)
C_BAD = (255, 70, 70)
C_HUD_BG = (5, 10, 25)
C_STAR = (150, 160, 220)

# ── Ground Y ──────────────────────────────────────────────────────────────────
GY = SCREEN_H - 65

# ── MediaPipe landmark indices (468-point FaceMesh) ───────────────────────────
NP_NOSE_TIP = 4
NP_L_MOUTH = 61
NP_R_MOUTH = 291
NP_UPPER_LIP = 13
NP_LOWER_LIP = 14
NP_L_EYE_TOP = 159
NP_L_EYE_BOT = 145
NP_R_EYE_TOP = 386
NP_R_EYE_BOT = 374
NP_L_BROW_HIGH = 70
NP_R_BROW_HIGH = 300
NP_L_BROW_MID = 105
NP_R_BROW_MID = 334
