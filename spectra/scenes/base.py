"""Scene base class and the shared screen header.

created by jullewz
"""

import pygame

from .. import assets, ui
from ..config import GOLD, GREY, WIDTH


class Scene:
    music = None

    def __init__(self, app):
        self.app = app
        self.t = 0.0

    @property
    def inp(self):
        return self.app.inp

    @property
    def save(self):
        return self.app.save

    def enter(self):
        if self.music:
            self.app.audio.play_music(self.music)

    def resume(self):
        self.enter()

    def update(self, dt):
        self.t += dt

    def draw(self, screen):
        pass

    def sfx(self, name, vol=1.0):
        self.app.audio.play(name, vol)

    # ---------------------------------------------------------------- shared look

    def backdrop(self, screen, accent):
        """Animated grid backdrop for menu screens."""
        self.app.menu_bg.draw(screen, accent, self.t)

    def header(self, screen, string, accent, flux=True):
        ui.title(screen, string, 64, accent, (WIDTH // 2, 58))
        if flux:
            screen.blit(assets.icon("flux", GOLD, 34, frame=False), (WIDTH - 196, 34))
            assets.text(screen, f"{self.save.flux:,}", 32, GOLD, (WIDTH - 156, 51), "midleft", bold=True)
            assets.text(screen, "flux", 18, GREY, (WIDTH - 156, 72), "midleft", shadow=False)


class MenuBackground:
    """A cheap animated backdrop: drifting grid, glows and particles. Shared by menus."""

    def __init__(self):
        self.cache = {}

    def draw(self, screen, accent, t):
        screen.fill((6, 6, 16))
        off = (t * 30) % 60
        dimc = tuple(int(c * 0.14) for c in accent)
        for x in range(-60, WIDTH + 60, 60):
            pygame.draw.line(screen, dimc, (x + off, 0), (x + off, 720), 1)
        for y in range(-60, 780, 60):
            pygame.draw.line(screen, dimc, (0, y + off * 0.5), (WIDTH, y + off * 0.5), 1)
        import math
        for i in range(3):
            x = WIDTH / 2 + math.cos(t * 0.3 + i * 2.1) * 420
            y = 360 + math.sin(t * 0.23 + i * 1.7) * 220
            assets.blit_glow(screen, x, y, 300, accent if i != 1 else (120, 60, 220), 0.22)
