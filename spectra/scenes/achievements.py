"""Achievements and lifetime statistics.

created by jullewz
"""

import pygame

from .. import assets, ui
from ..config import DIM, GOLD, GREY, PANEL, WHITE, WIDTH, YELLOW
from ..data import ACHIEVEMENTS
from ..util import fmt_int, fmt_time, mix
from .base import Scene

COLS = 2
ROW_H = 58
VISIBLE = 8


class AchievementsScene(Scene):
    music = "title"

    def __init__(self, app):
        super().__init__(app)
        self.index = 0
        self.scroll = 0.0

    def update(self, dt):
        super().update(dt)
        inp = self.inp
        if inp.hit("back"):
            self.sfx("ui_back")
            self.app.pop()
            return
        n = len(ACHIEVEMENTS)
        old = self.index
        if inp.hit("down"):
            self.index = min(n - 1, self.index + COLS)
        if inp.hit("up"):
            self.index = max(0, self.index - COLS)
        if inp.hit("right"):
            self.index = min(n - 1, self.index + 1)
        if inp.hit("left"):
            self.index = max(0, self.index - 1)
        if inp.wheel:
            self.index = max(0, min(n - 1, self.index - inp.wheel * COLS))
        if self.index != old:
            self.sfx("ui_move")
        row = self.index // COLS
        target = max(0, min(row - VISIBLE // 2 + 1, (n + COLS - 1) // COLS - VISIBLE))
        self.scroll += (target - self.scroll) * min(1.0, dt * 10)

    def draw(self, screen):
        self.backdrop(screen, YELLOW)
        self.header(screen, "ACHIEVEMENTS", YELLOW)
        got = len(self.save.achievements)
        n = len(ACHIEVEMENTS)
        assets.text(screen, f"{got} / {n} unlocked", 22, GREY, (WIDTH // 2, 100), "center", shadow=False)
        ui.bar(screen, (WIDTH // 2 - 200, 116, 400, 8), got / n, GOLD)
        area = pygame.Rect(40, 140, 820, VISIBLE * ROW_H)
        clip = screen.get_clip()
        screen.set_clip(area)
        w = (area.w - 16) // COLS
        for i, a in enumerate(ACHIEVEMENTS):
            row, col = divmod(i, COLS)
            y = area.y + (row - self.scroll) * ROW_H
            if y < area.y - ROW_H or y > area.bottom:
                continue
            r = pygame.Rect(area.x + col * (w + 16), int(y), w, ROW_H - 8)
            have = a.id in self.save.achievements
            focused = i == self.index
            border = GOLD if have else (70, 70, 96)
            ui.panel(screen, r, border if focused else mix(border, PANEL, 0.5), PANEL, 230, 10,
                     glow=0.7 if focused else 0)
            star = assets.transform(assets.SHAPES["star"], r.x + 26, r.centery, 13, -1.5708)
            pygame.draw.polygon(screen, GOLD if have else DIM, star)
            assets.text(screen, a.name, 21, WHITE if have else GREY, (r.x + 50, r.y + 5), bold=True)
            assets.text(screen, a.desc, 16, GREY if have else DIM, (r.x + 50, r.y + 29), shadow=False)
            assets.text(screen, f"+{a.reward}", 18, GOLD if have else DIM, (r.right - 12, r.y + 7), "topright",
                        bold=True)
        screen.set_clip(clip)
        self.draw_stats(screen)
        ui.hint(screen, "arrows / mouse wheel to scroll   ESC back")

    def draw_stats(self, screen):
        st = self.save.stats
        r = pygame.Rect(884, 140, 356, VISIBLE * ROW_H - 8)
        ui.panel(screen, r, YELLOW, PANEL, 230, 16)
        assets.text(screen, "LIFETIME", 18, YELLOW, (r.x + 20, r.y + 16), bold=True)
        rows = [
            ("Runs", fmt_int(st["runs"])),
            ("Victories", fmt_int(st["wins"])),
            ("Enemies destroyed", fmt_int(st["kills"])),
            ("Time in the void", fmt_time(st["time"])),
            ("Longest run", fmt_time(st["best_time"])),
            ("Highest level", str(st["best_level"])),
            ("Most kills in a run", fmt_int(st["best_kills"])),
            ("Bosses defeated", fmt_int(st["bosses"])),
            ("Evolutions", fmt_int(st["evolutions"])),
            ("Flux earned", fmt_int(st["flux_earned"])),
        ]
        for i, (name, value) in enumerate(rows):
            y = r.y + 50 + i * 40
            assets.text(screen, name, 19, GREY, (r.x + 20, y), shadow=False)
            assets.text(screen, value, 21, WHITE, (r.right - 20, y), "topright", bold=True)
            pygame.draw.line(screen, (36, 36, 60), (r.x + 20, y + 30), (r.right - 20, y + 30), 1)
