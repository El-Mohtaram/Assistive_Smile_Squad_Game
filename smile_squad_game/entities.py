"""
Game objects: Player, Platform, Bridge, Door, FallingRock, GoalFlag.
"""

import pygame
import math
from .constants import (
    PLAYER_SPEED, JUMP_VEL, GRAVITY, SCREEN_H,
    C_PLAYER_SH, C_PLAYER, C_SHIELD, C_PLATFORM, C_PLAT_TOP,
    C_BRIDGE_LT, C_BRIDGE, C_DOOR_OPEN, C_DOOR_CLOSED,
    C_ROCK, C_GOAL, C_TEXT, C_GOOD
)

class Player:
    W, H = 34, 50

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, self.W, self.H)
        self.vel_y = 0.0
        self.on_ground = False
        self.shielded = False
        self._shield_t = 0.0  # 0–1 for smooth shield alpha
        self.facing = 1  # 1=right, -1=left
        self._walk_t = 0.0  # walk animation phase

    def handle_input(self, keys):
        dx = 0
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        jump = keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_SPACE]

        if left:  dx = -PLAYER_SPEED; self.facing = -1
        if right: dx = PLAYER_SPEED; self.facing = 1
        if jump and self.on_ground:
            self.vel_y = JUMP_VEL

        if dx != 0:
            self._walk_t += 0.25
        else:
            self._walk_t = 0

        self.rect.x += dx
        return dx

    def apply_gravity(self, solid_rects, world_w):
        self.vel_y = min(self.vel_y + GRAVITY, 22)
        self.rect.y += int(self.vel_y)
        self.on_ground = False
        self.rect.x = max(0, min(self.rect.x, world_w - self.W))

        for r in solid_rects:
            if self.rect.colliderect(r) and self.vel_y >= 0:
                self.rect.bottom = r.top
                self.vel_y = 0
                self.on_ground = True

    def draw(self, surf, cam_x, inv_frames=0):
        if inv_frames > 0 and (inv_frames // 5) % 2:
            return
        rx = self.rect.x - int(cam_x)
        ry = self.rect.y
        w, h = self.W, self.H

        # ── Body ──
        pygame.draw.rect(surf, C_PLAYER_SH, (rx + 3, ry + 4, w, h), border_radius=8)
        pygame.draw.rect(surf, C_PLAYER, (rx, ry, w, h), border_radius=8)

        # ── Eye ──
        ex = rx + w // 2 + self.facing * 7
        pygame.draw.circle(surf, (30, 30, 50), (ex, ry + 15), 6)
        pygame.draw.circle(surf, (255, 255, 255), (ex + self.facing, ry + 14), 2)

        # ── Legs (walk cycle) ──
        bob = int(math.sin(self._walk_t) * 4)
        pygame.draw.rect(surf, C_PLAYER_SH, (rx + 5, ry + h - 14 + bob, 10, 14), border_radius=4)
        pygame.draw.rect(surf, C_PLAYER_SH, (rx + w - 15, ry + h - 14 - bob, 10, 14), border_radius=4)

        # ── Shield ring ──
        target = 1.0 if self.shielded else 0.0
        self._shield_t += (target - self._shield_t) * 0.18
        if self._shield_t > 0.02:
            a = int(self._shield_t * 180)
            shield_s = pygame.Surface((w + 30, h + 30), pygame.SRCALPHA)
            pygame.draw.ellipse(shield_s, (*C_SHIELD, a), shield_s.get_rect())
            pygame.draw.ellipse(shield_s, (*C_SHIELD, min(255, a + 60)),
                                shield_s.get_rect(), 3)
            surf.blit(shield_s, (rx - 15, ry - 15))


class Platform:
    def __init__(self, x, y, w, h=22, color=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = color or C_PLATFORM

    @property
    def solid_rect(self):
        return self.rect

    def draw(self, surf, cam_x):
        r = self.rect.move(-int(cam_x), 0)
        # Shadow
        pygame.draw.rect(surf, (20, 30, 70), (r.x + 3, r.y + 4, r.w, r.h), border_radius=5)
        # Body
        pygame.draw.rect(surf, self.color, r, border_radius=5)
        # Top shine
        shine = pygame.Rect(r.x + 4, r.y + 2, r.w - 8, 4)
        pygame.draw.rect(surf, C_PLAT_TOP, shine, border_radius=3)


class Bridge:
    """Rises when patient raises eyebrows (Frontalis muscle)."""

    def __init__(self, x, gap_y, w):
        self._gap_y = gap_y  # lowered  position (non-walkable — IN the gap)
        self._up_y = gap_y - 80  # raised   position (walkable  — above the gap)
        self._prog = 0.0  # 0=down, 1=up
        self.rect = pygame.Rect(x, gap_y, w, 18)
        self.active = False  # True when solid (raised enough)
        self._font = None  # set lazily

    def update(self, brow_score):
        target = 1.0 if brow_score > 0.55 else 0.0
        self._prog += (target - self._prog) * 0.10
        self.rect.y = int(self._gap_y + self._prog * (self._up_y - self._gap_y))
        self.active = self._prog > 0.45

    def draw(self, surf, cam_x):
        r = self.rect.move(-int(cam_x), 0)
        # Glow when active
        if self._prog > 0.1:
            glow = pygame.Surface((r.w + 8, r.h + 8), pygame.SRCALPHA)
            a = int(self._prog * 100)
            pygame.draw.rect(glow, (*C_BRIDGE_LT, a), glow.get_rect(), border_radius=5)
            surf.blit(glow, (r.x - 4, r.y - 4))

        pygame.draw.rect(surf, C_BRIDGE, r, border_radius=4)
        pygame.draw.rect(surf, C_BRIDGE_LT, (r.x, r.y, r.w, 5), border_radius=4)

        if self._prog > 0.05:
            if self._font is None:
                self._font = pygame.font.SysFont("Arial", 13, bold=True)
            lbl = self._font.render("▲ BRIDGE ▲", True, (255, 240, 160))
            surf.blit(lbl, (r.centerx - lbl.get_width() // 2, r.y - 18))


class Door:
    """Opens when patient smiles (Zygomaticus major)."""

    def __init__(self, x, y, w=44, h=76):
        self.rect = pygame.Rect(x, y, w, h)
        self._prog = 0.0  # 0=closed, 1=fully open
        self.open = False
        self._font = None

    def update(self, smile_score):
        target = 1.0 if smile_score > 0.65 else 0.0
        self._prog += (target - self._prog) * 0.09
        self.open = self._prog > 0.5

    @property
    def solid_rect(self):
        """Return blocking rect — shrinks as door opens."""
        visible_h = int(self.rect.h * (1.0 - self._prog))
        return pygame.Rect(self.rect.x, self.rect.y, self.rect.w, max(visible_h, 0))

    def draw(self, surf, cam_x):
        r = self.rect.move(-int(cam_x), 0)
        col = C_DOOR_OPEN if self.open else C_DOOR_CLOSED
        # Frame
        pygame.draw.rect(surf, (80, 40, 40), (r.x + 3, r.y + 4, r.w, r.h), border_radius=6)
        # Door panel (slides up)
        vis_h = int(self.rect.h * (1.0 - self._prog))
        if vis_h > 0:
            dr = pygame.Rect(r.x, r.y, r.w, vis_h)
            pygame.draw.rect(surf, col, dr, border_radius=6)
            pygame.draw.rect(surf, (255, 255, 255), dr, 2, border_radius=6)
            # Knob
            kx = r.x + r.w - 10
            ky = r.y + vis_h // 2
            pygame.draw.circle(surf, (255, 220, 100), (kx, ky), 5)

        if self._font is None:
            self._font = pygame.font.SysFont("Arial", 13, bold=True)
        label = "✓ OPEN" if self.open else "😊 SMILE"
        lbl = self._font.render(label, True, C_TEXT)
        surf.blit(lbl, (r.centerx - lbl.get_width() // 2, r.y - 20))


class FallingRock:
    """Hazard. Blocked by lip-pucker shield (Orbicularis oris)."""

    def __init__(self, x, y, speed):
        self.rect = pygame.Rect(x, y, 26, 26)
        self.speed = speed
        self.alive = True
        self._rot = 0

    def update(self, player_rect, shielded):
        self.rect.y += self.speed
        self._rot += 3

        if self.rect.top > SCREEN_H + 60:
            self.alive = False
            return None

        if self.rect.colliderect(player_rect):
            self.alive = False
            if shielded:
                return "blocked"
            return "hit"

        return None

    def draw(self, surf, cam_x):
        cx = self.rect.centerx - int(cam_x)
        cy = self.rect.centery
        r = self.rect.w // 2
        angle = math.radians(self._rot)
        pts = []
        for i in range(6):
            a = angle + i * math.pi / 3
            dist = r * (0.7 + 0.3 * ((i * 137) % 3) / 3)
            pts.append((cx + math.cos(a) * dist, cy + math.sin(a) * dist))
        pygame.draw.polygon(surf, (100, 60, 30), pts)
        pygame.draw.polygon(surf, C_ROCK, pts, 0)
        pygame.draw.polygon(surf, (180, 120, 70), pts, 2)


class GoalFlag:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self._t = 0

    def update(self):
        self._t += 0.05

    def draw(self, surf, cam_x):
        gx = self.x - int(cam_x)
        gy = self.y
        # Pole
        pygame.draw.line(surf, (200, 210, 230), (gx, gy), (gx, gy - 90), 3)
        # Waving flag
        pts = [(gx, gy - 90)]
        for i in range(5):
            px = gx + 4 + i * 10
            py = gy - 90 + 25 + int(10 * math.sin(self._t + i * 0.7))
            pts.append((px, py))
        pts += [(gx, gy - 65)]
        pygame.draw.polygon(surf, C_GOAL, pts)
        # Text
        if not hasattr(self, "_font"):
            self._font = pygame.font.SysFont("Arial", 15, bold=True)
        lbl = self._font.render("GOAL!", True, C_GOOD)
        surf.blit(lbl, (gx - lbl.get_width() // 2, gy - 115))
