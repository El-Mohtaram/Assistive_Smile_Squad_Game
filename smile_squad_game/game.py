"""
Main SmileSquad game orchestrator class.
"""

import math
import random
import pygame
import numpy as np
from .constants import (
    SCREEN_W, SCREEN_H, FPS, GY, CAM_DISP_W, CAM_DISP_H,
    C_BG_TOP, C_BG_BOT, C_STAR, C_TEXT, C_WARN, C_GOOD, C_BAD, C_SHIELD
)
from .camera import CameraReader, FaceProcessorThread
from .face_tracker import FaceTracker
from .hud import HUD
from .particles import ParticleSystem
from .entities import Player, FallingRock
from .levels import build_level

class SmileSquad:
    MAX_LEVELS = 5

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Smile Squad 🎮 — Facial Rehabilitation")
        self.clock = pygame.time.Clock()

        # Webcam — fully threaded pipeline: capture → face tracking → display
        self.cam_reader = CameraReader(0)
        self.tracker = FaceTracker()
        self._face_proc = FaceProcessorThread(self.cam_reader, self.tracker)
        self._face_proc.start()

        # UI helpers
        self.hud = HUD()
        self.particles = ParticleSystem()

        # Fonts
        self.f_xl = pygame.font.SysFont("Arial", 58, bold=True)
        self.f_lg = pygame.font.SysFont("Arial", 34, bold=True)
        self.f_md = pygame.font.SysFont("Arial", 20)
        self.f_sm = pygame.font.SysFont("Arial", 15)

        # Pre-render gradient background (avoids 720+ draw calls per frame)
        self._bg_surface = pygame.Surface((SCREEN_W, SCREEN_H))
        for row in range(0, SCREEN_H, 4):
            t = row / SCREEN_H
            col = tuple(int(C_BG_TOP[i] + t * (C_BG_BOT[i] - C_BG_TOP[i])) for i in range(3))
            pygame.draw.line(self._bg_surface, col, (0, row), (SCREEN_W, row))
            pygame.draw.line(self._bg_surface, col, (0, row + 1), (SCREEN_W, row + 1))
            pygame.draw.line(self._bg_surface, col, (0, row + 2), (SCREEN_W, row + 2))
            pygame.draw.line(self._bg_surface, col, (0, row + 3), (SCREEN_W, row + 3))

        # Background stars (static seed)
        self._stars = [(random.randint(0, SCREEN_W), random.randint(0, SCREEN_H - 80),
                        random.randint(1, 2)) for _ in range(60)]

        # Game state
        self.state = "menu"
        self.level_num = 1
        self.lives = 5

        # Level objects
        self.player = None
        self.platforms = []
        self.bridges = []
        self.doors = []
        self.rocks = []
        self.goal = None
        self.world_w = 1600
        self.cam_x = 0.0
        self.hint = ""
        self._rock_timers = []  # one timer per rock_zone

        # Invincibility frames after hit
        self.inv_frames = 0

        # Expression cooldown tracking (prevents double-counting reps)
        self._expr_cd = {"smile": 0, "eyebrow": 0, "pucker": 0}
        self._EXPR_CD = 900  # ms

        # Camera surface
        self.cam_surf = None

    # ─────────────────────────────── level loading ────────────────────────────
    def load_level(self, n):
        data = build_level(n)
        sx, sy = data["spawn"]
        self.player = Player(sx, sy)
        self.platforms = data["platforms"]
        self.bridges = data["bridges"]
        self.doors = data["doors"]
        self.world_w = data["world_w"]
        self.hint = data["hint"]
        self.goal = data.get("goal")
        if not self.goal and "goal_x" in data:
            # Fallback for entities.GoalFlag since it's initialized inside build_level directly
            from .entities import GoalFlag
            self.goal = GoalFlag(data["goal_x"], GY - 5)
        self.rocks = []
        self.cam_x = 0.0
        self.inv_frames = 0

        self._rock_zones = data.get("rock_zones", [])
        self._rock_timers = [0] * len(self._rock_zones)

        self.tracker.adapt_difficulty()

    # ─────────────────────────────── webcam ───────────────────────────────────
    def _update_camera(self):
        rgb_array = self._face_proc.get_latest()
        if rgb_array is None:
            return
        self.cam_surf = pygame.surfarray.make_surface(rgb_array)

    def _draw_camera(self):
        if self.cam_surf is None:
            return
        cx = SCREEN_W - CAM_DISP_W - 10
        cy = SCREEN_H - CAM_DISP_H - 10
        self.screen.blit(self.cam_surf, (cx, cy))
        fsi_col = C_GOOD if self.tracker.fsi > 0.72 else (C_WARN if self.tracker.fsi > 0.5 else C_BAD)
        pygame.draw.rect(self.screen, fsi_col,
                         (cx - 3, cy - 3, CAM_DISP_W + 6, CAM_DISP_H + 6), 3, border_radius=6)
        lbl = self.f_sm.render("Player 2 — Webcam", True, C_TEXT)
        self.screen.blit(lbl, (cx, cy - 20))

    # ─────────────────────────────── background ───────────────────────────────
    def _draw_background(self):
        # Cached gradient blit (pre-rendered in __init__)
        self.screen.blit(self._bg_surface, (0, 0))

        # Parallax stars
        for sx, sy, sz in self._stars:
            px = (sx - int(self.cam_x) // 6) % SCREEN_W
            pygame.draw.circle(self.screen, C_STAR, (px, sy), sz)

        # Ground bar
        pygame.draw.rect(self.screen, (15, 25, 55), (0, GY + 22, SCREEN_W, SCREEN_H))

    # ─────────────────────────────── screens ──────────────────────────────────
    def _draw_menu(self):
        self._draw_background()
        title = self.f_xl.render("SMILE SQUAD", True, (255, 220, 70))
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 140))

        sub = self.f_lg.render("Asymmetrical Facial Rehabilitation Game", True, (180, 190, 240))
        self.screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 220))

        lines = [
            "",
            "PLAYER 1  →  Keyboard (WASD / ← ↑ → ↓)  — runs and jumps",
            "PLAYER 2  →  Webcam & your FACE           — controls the world",
            "",
            "  😊  SMILE WIDE    →  Opens locked doors",
            "  👁  RAISE EYEBROWS →  Lifts bridges across gaps",
            "  💋  PUCKER LIPS   →  Activates shield against rocks",
            "",
            "Great for Bell's Palsy & post-stroke facial therapy.",
            "",
            "[ PRESS  SPACE  OR  ENTER  TO  START ]",
        ]
        for i, line in enumerate(lines):
            col = (255, 220, 70) if "PLAYER" in line else C_TEXT
            bold = "PLAYER" in line or "PRESS" in line
            fnt = self.f_md if bold else self.f_sm
            t = fnt.render(line, True, col)
            self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 285 + i * 30))

    def _draw_calibration(self):
        self._draw_background()
        t = self.tracker
        cx = SCREEN_W // 2 - CAM_DISP_W
        cy = 270

        if self.cam_surf:
            # Tinted border: green = still, red = moving
            still_col = C_GOOD if t.is_still else C_BAD
            pygame.draw.rect(self.screen, still_col,
                             (cx - 4, cy - 4, CAM_DISP_W * 2 + 8, CAM_DISP_H + 8), 4, border_radius=6)
            self.screen.blit(self.cam_surf, (cx, cy))
            # Scale the cam surface to double width for larger calibration view
            scaled = pygame.transform.scale(self.cam_surf, (CAM_DISP_W * 2, CAM_DISP_H))
            self.screen.blit(scaled, (cx, cy))

        # Title
        msg = self.f_lg.render("CALIBRATION  —  Relax & Hold Still", True, C_WARN)
        self.screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, 160))
        sub = self.f_sm.render("Look straight at the camera. Neutral face. Don't move.", True, C_TEXT)
        self.screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 210))

        bar_x = SCREEN_W // 2 - 200
        bar_w = 400
        bar_y = cy + CAM_DISP_H + 16

        # ── Motion indicator ──────────────────────────────────────────────────
        mot = t.motion_level
        mot_c = C_GOOD if mot < 0.25 else (C_WARN if mot < 0.65 else C_BAD)
        still_txt = "✔  HOLD STILL!" if not t.is_still else "✔  GOOD — hold..."
        mot_label = self.f_md.render(
            ("🔴  MOVE LESS  —  stop moving" if not t.is_still else "🟢  " + still_txt),
            True, mot_c)
        self.screen.blit(mot_label, (SCREEN_W // 2 - mot_label.get_width() // 2, bar_y))
        bar_y += 32

        # Motion bar (red = moving, should be low)
        pygame.draw.rect(self.screen, (30, 40, 60), (bar_x, bar_y, bar_w, 14), border_radius=4)
        pygame.draw.rect(self.screen, mot_c, (bar_x, bar_y, int(bar_w * mot), 14), border_radius=4)
        mot_lbl = self.f_sm.render("Motion  (keep low)", True, (160, 170, 200))
        self.screen.blit(mot_lbl, (bar_x + bar_w + 10, bar_y))
        bar_y += 24

        # ── Progress bar (accepted still frames) ─────────────────────────────
        prog = t.calib_progress
        pygame.draw.rect(self.screen, (30, 40, 60), (bar_x, bar_y, bar_w, 14), border_radius=4)
        pygame.draw.rect(self.screen, C_GOOD, (bar_x, bar_y, int(bar_w * prog), 14), border_radius=4)
        prog_lbl = self.f_sm.render(f"Good frames  {int(prog * 100)}%", True, C_GOOD)
        self.screen.blit(prog_lbl, (bar_x + bar_w + 10, bar_y))

        # Tip
        tip = self.f_sm.render(
            "Tip: Rest your elbow on a table. Look at the green dot on your webcam.", True, (140, 150, 190))
        self.screen.blit(tip, (SCREEN_W // 2 - tip.get_width() // 2, bar_y + 40))

    def _draw_level_complete(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 15, 0, 180))
        self.screen.blit(overlay, (0, 0))

        msg = self.f_xl.render(f"LEVEL {self.level_num}  COMPLETE!", True, C_GOOD)
        self.screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, 200))

        fsi = self.tracker.fsi
        fcol = C_GOOD if fsi > 0.72 else (C_WARN if fsi > 0.5 else C_BAD)
        fsi_t = self.f_lg.render(f"Symmetry Index: {fsi:.2f}", True, fcol)
        self.screen.blit(fsi_t, (SCREEN_W // 2 - fsi_t.get_width() // 2, 300))

        rc = self.tracker.rep_count
        reps = self.f_md.render(
            f"Reps this session —  👁 {rc['eyebrow']}   😊 {rc['smile']}   💋 {rc['pucker']}",
            True, C_TEXT)
        self.screen.blit(reps, (SCREEN_W // 2 - reps.get_width() // 2, 360))

        cont = self.f_md.render("Press SPACE to continue", True, (180, 190, 220))
        self.screen.blit(cont, (SCREEN_W // 2 - cont.get_width() // 2, 440))

    def _draw_game_over(self):
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((40, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))
        msg = self.f_xl.render("GAME OVER", True, C_BAD)
        self.screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, 250))
        cont = self.f_md.render("Press SPACE to retry this level", True, C_TEXT)
        self.screen.blit(cont, (SCREEN_W // 2 - cont.get_width() // 2, 360))

    def _draw_loading_level(self):
        self._draw_background()
        msg = self.f_xl.render(f"Loading Level {self.level_num}...", True, (255, 220, 70))
        self.screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, 250))
        sub = self.f_md.render("Re-initializing camera and face AI for stability...", True, C_TEXT)
        self.screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, 320))

    def _draw_session_end(self):
        self._draw_background()
        title = self.f_xl.render("SESSION COMPLETE!", True, (255, 220, 70))
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 120))

        rc = self.tracker.rep_count
        avg_fsi = round(float(np.mean(self.tracker.fsi_history)), 3) if self.tracker.fsi_history else 0.0
        fsi_col = C_GOOD if avg_fsi > 0.72 else (C_WARN if avg_fsi > 0.5 else C_BAD)

        lines = [
            ("", C_TEXT),
            (f"  😊  Smile reps:      {rc['smile']}", C_GOOD),
            (f"  👁  Eyebrow reps:    {rc['eyebrow']}", (255, 220, 70)),
            (f"  💋  Pucker reps:     {rc['pucker']}", C_SHIELD),
            ("", C_TEXT),
            (f"  📊  Average FSI:     {avg_fsi:.2f}  (1.0 = full symmetry)", fsi_col),
            ("", C_TEXT),
            ("  Session data saved to  session_data/", (160, 170, 200)),
            ("  Share the JSON file with your physiotherapist.", (140, 150, 180)),
            ("", C_TEXT),
            ("  SPACE → play again      ESC → quit", C_TEXT),
        ]
        for i, (line, col) in enumerate(lines):
            t = self.f_md.render(line, True, col)
            self.screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 235 + i * 36))

    # ─────────────────────────────── game loop ────────────────────────────────
    def run(self):
        running = True

        while running:
            dt = self.clock.tick(FPS)
            keys = pygame.key.get_pressed()

            # ── Events ────────────────────────────────────────────────────────
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

                    elif event.key == pygame.K_t:
                        self.hud.show_debug = not getattr(self.hud, 'show_debug', False)

                    elif event.key == pygame.K_b:
                        self.tracker._simulate_bells = not getattr(self.tracker, '_simulate_bells', False)
                        print("Bell's simulation:", self.tracker._simulate_bells)

                    elif self.state == "menu":
                        if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                            self.state = "calibrating"

                    elif self.state == "level_complete":
                        if event.key == pygame.K_SPACE:
                            if self.level_num >= self.MAX_LEVELS:
                                self.tracker.save_session()
                                self.state = "session_end"
                            else:
                                self.level_num += 1
                                self.state = "loading_level"

                    elif self.state == "game_over":
                        if event.key == pygame.K_SPACE:
                            self.lives = 5
                            self.load_level(self.level_num)
                            self.state = "playing"

                    elif self.state == "session_end":
                        if event.key == pygame.K_SPACE:
                            # Full restart — stop threads first
                            self._face_proc.stop()
                            self.cam_reader.release()
                            self.tracker.close()
                            self.__class__.__init__(self)
                            break

            # ── Camera (every frame, all states) ──────────────────────────────
            self._update_camera()

            # ── State machine ─────────────────────────────────────────────────
            if self.state == "menu":
                self._draw_menu()

            elif self.state == "calibrating":
                self._draw_calibration()
                if self.tracker.calibrated:
                    self.load_level(self.level_num)
                    self.state = "playing"

            elif self.state == "playing":
                self._update_playing(dt, keys)
                self._draw_playing()

            elif self.state == "level_complete":
                self._draw_background()
                for p in self.platforms: p.draw(self.screen, self.cam_x)
                self._draw_level_complete()

            elif self.state == "game_over":
                self._draw_background()
                self._draw_game_over()

            elif self.state == "session_end":
                self._draw_session_end()

            elif self.state == "loading_level":
                self._draw_loading_level()
                pygame.display.flip()  # Force draw immediately
                
                # Heavy lifting: Reset camera pipeline to flush OS buffers
                print(f"Loading Level {self.level_num}: Re-initializing Camera & MediaPipe...")
                self._face_proc.stop()
                self.cam_reader.release()
                import time
                
                # CRITICAL FIX: The Windows USB driver needs at least 2-3 seconds to completely 
                # power down the webcam endpoint and release the memory lock. 0.5s is too fast 
                # and causes a ghost lock on the 4th/5th retry, resulting in permanent frame drops.
                time.sleep(3.0)  
                
                from .camera import CameraReader, FaceProcessorThread
                self.cam_reader = CameraReader(0)
                self._face_proc = FaceProcessorThread(self.cam_reader, self.tracker)
                self._face_proc.start()
                
                self.load_level(self.level_num)
                self.state = "playing"

            # Camera overlay
            if self.state in ("playing", "calibrating", "level_complete"):
                self._draw_camera()

            pygame.display.flip()

        # Cleanup
        self.tracker.save_session()
        self._face_proc.stop()
        self.cam_reader.release()
        self.tracker.close()
        pygame.quit()

    # ─────────────────────────────── playing update ───────────────────────────
    def _update_playing(self, dt, keys):
        exprs = self.tracker.expressions

        # ── Bridges update ────────────────────────────────────────────────────
        for br in self.bridges:
            br.update(exprs["eyebrow"])

        # ── Doors update ──────────────────────────────────────────────────────
        for dr in self.doors:
            dr.update(exprs["smile"])

        # ── Shield — use hysteresis state for stability ────────────────────────
        self.player.shielded = self.tracker.expr_triggered("pucker")

        # ── Rep counting (medical logging) ────────────────────────────────────
        for name in ("smile", "eyebrow", "pucker"):
            now = pygame.time.get_ticks()
            active = self.tracker.expr_triggered(name)
            # Log a rep on the rising edge (just became active) with cooldown
            if active and now - self._expr_cd.get(name, 0) > self._EXPR_CD:
                self._expr_cd[name] = now
                self.tracker.log_rep(name)

        # ── Solid surfaces for physics ────────────────────────────────────────
        solids = [p.rect for p in self.platforms]
        for br in self.bridges:
            if br.active:
                solids.append(br.rect)

        # ── Player movement ───────────────────────────────────────────────────
        self.player.handle_input(keys)
        # Block by closed doors
        for dr in self.doors:
            if not dr.open:
                if self.player.rect.colliderect(dr.rect):
                    if self.player.rect.centerx < dr.rect.centerx:
                        self.player.rect.right = dr.rect.left
                    else:
                        self.player.rect.left = dr.rect.right
        self.player.apply_gravity(solids, self.world_w)

        # ── Camera smooth follow ──────────────────────────────────────────────
        target_cam = self.player.rect.centerx - SCREEN_W // 3
        self.cam_x += (target_cam - self.cam_x) * 0.08
        self.cam_x = max(0, min(self.cam_x, self.world_w - SCREEN_W))

        # ── Rock spawning ─────────────────────────────────────────────────────
        for i, zone in enumerate(self._rock_zones):
            self._rock_timers[i] += dt
            if self._rock_timers[i] >= zone["interval"]:
                self._rock_timers[i] = 0
                sx = random.randint(zone["x0"], zone["x1"])
                self.rocks.append(FallingRock(sx, -40, zone["speed"]))

        # ── Rock update ───────────────────────────────────────────────────────
        new_rocks = []
        for rock in self.rocks:
            result = rock.update(self.player.rect, self.player.shielded)
            if result == "hit" and self.inv_frames == 0:
                self.lives -= 1
                self.inv_frames = 90
                self.particles.burst(self.player.rect.centerx, self.player.rect.centery,
                                     C_BAD, n=20)
            elif result == "blocked":
                self.particles.burst(rock.rect.centerx, rock.rect.centery,
                                     C_SHIELD, n=14)
            if rock.alive:
                new_rocks.append(rock)
        self.rocks = new_rocks

        if self.inv_frames > 0:
            self.inv_frames -= 1

        # ── Goal check ────────────────────────────────────────────────────────
        if self.player.rect.right >= self.goal.x:
            self.particles.burst(self.goal.x, GY - 50, C_GOOD, n=40, size=8)
            self.state = "level_complete"

        # ── Fall off world ────────────────────────────────────────────────────
        if self.player.rect.top > SCREEN_H + 80:
            self.lives -= 1
            self.particles.burst(self.player.rect.centerx, SCREEN_H, C_BAD, n=12)
            if self.lives <= 0:
                self.state = "game_over"
            else:
                sx, sy = build_level(self.level_num)["spawn"]
                self.player.rect.topleft = (sx, sy)
                self.player.vel_y = 0
                self.inv_frames = 120

        if self.lives <= 0:
            self.state = "game_over"

        # ── Goal animation ────────────────────────────────────────────────────
        self.goal.update()

    # ─────────────────────────────── playing draw ─────────────────────────────
    def _draw_playing(self):
        self._draw_background()

        cx = int(self.cam_x)

        # World objects
        self.goal.draw(self.screen, cx)
        for p in self.platforms: p.draw(self.screen, cx)
        for br in self.bridges:   br.draw(self.screen, cx)
        for dr in self.doors:     dr.draw(self.screen, cx)
        for r in self.rocks:     r.draw(self.screen, cx)

        # Particles
        self.particles.update_draw(self.screen, cx)

        # Player
        self.player.draw(self.screen, cx, self.inv_frames)

        # HUD
        self.hud.draw(self.screen, self.tracker, self.lives, self.level_num, self.hint)
