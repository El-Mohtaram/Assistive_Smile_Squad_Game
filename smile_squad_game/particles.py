"""
Particle objects and ParticleSystem for visual feedback.
"""

import pygame
import random

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size")

    def __init__(self, x, y, color, vx=0, vy=0, life=40, size=5):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx + random.uniform(-1.5, 1.5), vy + random.uniform(-2, 0)
        self.life = self.max_life = life
        self.color = color
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.12
        self.life -= 1
        return self.life > 0

    def draw(self, surf, cam_x):
        alpha = self.life / self.max_life
        r = max(1, int(self.size * alpha))
        pygame.draw.circle(surf, self.color, (int(self.x - cam_x), int(self.y)), r)


class ParticleSystem:
    def __init__(self):
        self._pool = []

    def burst(self, x, y, color, n=18, size=6):
        for _ in range(n):
            vx = random.uniform(-3, 3)
            vy = random.uniform(-5, -1)
            self._pool.append(Particle(x, y, color, vx, vy, life=random.randint(25, 50), size=size))

    def update_draw(self, surf, cam_x):
        self._pool = [p for p in self._pool if p.update()]
        for p in self._pool:
            p.draw(surf, cam_x)
