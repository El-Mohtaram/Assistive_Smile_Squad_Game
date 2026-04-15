"""
Heads Up Display (HUD) overlay for real-time tracking metrics.
"""

import pygame
import numpy as np
from .constants import (
    SCREEN_W, SCREEN_H, C_TEXT, C_GOOD, C_WARN, C_BAD
)

class HUD:
    def __init__(self):
        self.f_lg = pygame.font.SysFont("Arial", 21, bold=True)
        self.f_md = pygame.font.SysFont("Arial", 15)
        self.f_sm = pygame.font.SysFont("Arial", 13)

    def _bar(self, surf, x, y, w, h, val, color, label, threshold_mark=None):
        # Track
        pygame.draw.rect(surf, (25, 30, 60), (x, y, w, h), border_radius=3)
        # Fill
        fill_w = max(2, int(w * val))
        pygame.draw.rect(surf, color, (x, y, fill_w, h), border_radius=3)
        # Outline
        pygame.draw.rect(surf, (80, 90, 130), (x, y, w, h), 1, border_radius=3)
        # Threshold mark (shows when expression will trigger)
        if threshold_mark is not None:
            mx = x + int(w * threshold_mark)
            pygame.draw.line(surf, (255, 255, 100), (mx, y - 2), (mx, y + h + 2), 2)
        # Label
        lbl = self.f_sm.render(label, True, C_TEXT)
        surf.blit(lbl, (x + w + 10, y - 1))

    def draw(self, surf, tracker, lives, level_num, hint):
        # ── Left panel ───────────────────────────────────────────────────────
        panel_h = 215
        panel = pygame.Surface((270, panel_h), pygame.SRCALPHA)
        panel.fill((5, 10, 28, 210))
        surf.blit(panel, (8, 8))

        y = 16
        # Face status
        if not tracker.face_detected:
            sc, st = C_BAD, "● NO FACE DETECTED"
        elif not tracker.calibrated:
            sc, st = C_WARN, f"● CALIBRATING  {int(tracker.calib_progress * 100)}%"
        else:
            sc, st = C_GOOD, "● FACE TRACKED"
        surf.blit(self.f_md.render(st, True, sc), (16, y))
        y += 22

        # FSI bar
        fsi = tracker.fsi
        fsi_col = C_GOOD if fsi > 0.72 else (C_WARN if fsi > 0.50 else C_BAD)
        surf.blit(self.f_sm.render(f"Symmetry Index (FSI): {fsi:.2f}", True, fsi_col), (16, y))
        y += 14
        self._bar(surf, 16, y, 170, 10, fsi, fsi_col, "")
        y += 18

        # Expression bars (trigger threshold at HYSTER_ON = 0.65)
        TRIG = 0.65
        acts = tracker._expr_active

        def expr_row(surf, x, y, w, h, val, color, label, active):
            # Active indicator dot
            dot_col = color if active else (50, 55, 80)
            pygame.draw.circle(surf, dot_col, (x - 12, y + h // 2), 5)
            self._bar(surf, x, y, w, h, val, color if active else (80, 85, 110), label, TRIG)

        expr_row(surf, 16, y, 150, 13, tracker.expressions["eyebrow"],
                 (255, 220, 60), " 👁 Eyebrow", acts["eyebrow"])
        y += 22
        expr_row(surf, 16, y, 150, 13, tracker.expressions["smile"],
                 (60, 230, 110), " 😊 Smile  ", acts["smile"])
        y += 22
        expr_row(surf, 16, y, 150, 13, tracker.expressions["pucker"],
                 (80, 200, 255), " 💋 Pucker ", acts["pucker"])
        y += 24

        # Rep summary
        rc = tracker.rep_count
        reps = self.f_sm.render(
            f"Reps →  👁 {rc['eyebrow']}   😊 {rc['smile']}   💋 {rc['pucker']}",
            True, (170, 180, 220))
        surf.blit(reps, (16, y))
        y += 18
        th_txt = self.f_sm.render(
            f"Adaptive threshold: {tracker.thresh['smile']:.3f}", True, (120, 130, 170))
        surf.blit(th_txt, (16, y))

        # ── Top-right: lives & level ──────────────────────────────────────────
        lvl = self.f_lg.render(f"LEVEL {level_num}", True, C_TEXT)
        surf.blit(lvl, (SCREEN_W - lvl.get_width() - 18, 14))
        hearts = "♥ " * lives + "♡ " * max(0, 5 - lives)
        ht = self.f_lg.render(hearts, True, (220, 60, 80))
        surf.blit(ht, (SCREEN_W - ht.get_width() - 18, 44))

        # ── Bottom hint ───────────────────────────────────────────────────────
        if hint:
            h_surf = self.f_md.render(hint, True, C_TEXT)
            hx = SCREEN_W // 2 - h_surf.get_width() // 2
            bg = pygame.Surface((h_surf.get_width() + 24, h_surf.get_height() + 12), pygame.SRCALPHA)
            bg.fill((0, 0, 10, 180))
            surf.blit(bg, (hx - 12, SCREEN_H - 88))
            surf.blit(h_surf, (hx, SCREEN_H - 82))

        # ── Debug HUD (toggled with T) ────────────────────────────────────────
        if getattr(self, 'show_debug', False):
            debug_lines = [
                f"smile thresh:   {tracker.thresh['smile']:.4f}",
                f"eyebrow thresh: {tracker.thresh['eyebrow']:.4f}",
                f"pucker thresh:  {tracker.thresh['pucker']:.4f}",
                f"FSI (last 120): {round(float(np.mean(tracker.fsi_history[-120:])), 3) if len(tracker.fsi_history) >= 120 else 'collecting...'}",
                f"FSI samples:    {len(tracker.fsi_history)}",
            ]
            for i, line in enumerate(debug_lines):
                t = self.f_sm.render(line, True, (180, 220, 255))
                surf.blit(t, (16, SCREEN_H - 130 + i * 18))
