"""
Level layouts and difficulty progression.
"""

from .constants import GY
from .entities import Platform, Bridge, Door

def build_level(n):
    """
    Returns a dict describing the level layout.
    Mechanics are introduced progressively, following neuromuscular
    retraining principles (one new challenge at a time).
    """

    if n == 1:
        # ── Tutorial: smile only ──────────────────────────────────────────────
        return {
            "name": "The First Smile",
            "hint": "😊  SMILE WIDE  to open the door!",
            "world_w": 1600,
            "platforms": [
                Platform(0, GY, 500),
                Platform(550, GY, 650),
                Platform(1300, GY, 300),
            ],
            "bridges": [],
            "doors": [Door(505, GY - 76)],
            "rock_zones": [],
            "goal_x": 1520,
            "spawn": (60, GY - 56),
        }

    elif n == 2:
        # ── Introduce eyebrow raise / bridge ─────────────────────────────────
        return {
            "name": "Bridge Builder",
            "hint": "👁  RAISE EYEBROWS  for the bridge    😊  SMILE  for the door",
            "world_w": 1900,
            "platforms": [
                Platform(0, GY, 380),
                Platform(730, GY, 500),
                Platform(1430, GY, 400),
            ],
            "bridges": [Bridge(380, GY, 350)],
            "doors": [Door(1385, GY - 76)],
            "rock_zones": [],
            "goal_x": 1730,
            "spawn": (60, GY - 56),
        }

    elif n == 3:
        # ── Introduce shield / falling rocks ─────────────────────────────────
        return {
            "name": "Rock Storm",
            "hint": "💋  PUCKER  for shield    👁  Eyebrows=bridge    😊  Smile=door",
            "world_w": 2000,
            "platforms": [
                Platform(0, GY, 300),
                Platform(620, GY, 400),
                Platform(1250, GY, 500),
            ],
            "bridges": [Bridge(300, GY, 320)],
            "doors": [Door(1205, GY - 76)],
            "rock_zones": [{"x0": 650, "x1": 970, "speed": 3, "interval": 1400}],
            "goal_x": 1650,
            "spawn": (60, GY - 56),
        }

    elif n == 4:
        # ── Two bridges + door + rocks ────────────────────────────────────────
        return {
            "name": "Double Lift",
            "hint": "Keep all expressions ready — two bridges to raise!",
            "world_w": 2200,
            "platforms": [
                Platform(0, GY, 250),
                Platform(580, GY, 280),
                Platform(1130, GY, 300),
                Platform(1700, GY, 400),
            ],
            "bridges": [Bridge(250, GY, 330), Bridge(860, GY, 270)],
            "doors": [Door(1650, GY - 76)],
            "rock_zones": [{"x0": 620, "x1": 820, "speed": 3.5, "interval": 1200},
                           {"x0": 1180, "x1": 1380, "speed": 3.0, "interval": 1600}],
            "goal_x": 2000,
            "spawn": (60, GY - 56),
        }

    else:
        # ── Level 5+: all mechanics, faster rocks, tighter spaces ────────────
        spd = 4 + (n - 5) * 0.5
        itv = max(800, 1300 - (n - 5) * 100)
        return {
            "name": f"Expert Run",
            "hint": "All mechanics! Communicate! 💪",
            "world_w": 2400,
            "platforms": [
                Platform(0, GY, 200),
                Platform(550, GY - 130, 180),
                Platform(930, GY, 320),
                Platform(1480, GY, 280),
                Platform(1950, GY, 350),
            ],
            "bridges": [Bridge(200, GY, 350), Bridge(1250, GY, 230)],
            "doors": [Door(1430, GY - 76)],
            "rock_zones": [
                {"x0": 580, "x1": 870, "speed": spd, "interval": int(itv)},
                {"x0": 980, "x1": 1220, "speed": spd - 0.5, "interval": int(itv * 1.2)},
            ],
            "goal_x": 2200,
            "spawn": (60, GY - 56),
        }
