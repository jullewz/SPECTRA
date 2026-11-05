"""Audio, video and gameplay options plus the control reference.

created by jullewz
"""

import pygame

from .. import assets, ui
from ..config import CYAN, GREY, PANEL, PURPLE, WHITE, WIDTH
from ..util import mix, scale
from .base import Scene

ROWS = [
    ("master", "Master volume", "slider"),
    ("music", "Music", "slider"),
    ("sfx", "Sound effects", "slider"),
    ("bloom", "Bloom glow", "toggle"),
    ("shake", "Screen shake", "toggle"),
    ("numbers", "Damage numbers", "toggle"),
    ("fullscreen", "Fullscreen", "toggle"),
    ("fps", "Show FPS", "toggle"),
]

CONTROLS = [
    ("Move", "WASD / arrows / left stick"),
    ("Confirm", "ENTER / SPACE / A"),
    ("Back / pause", "ESC / P / B / START"),
    ("Reroll", "R / pad X"),
    ("Skip upgrade", "X / pad Y"),
    ("Fullscreen", "F11"),
    ("FPS counter", "F3"),
    ("Screenshot", "F12"),
]


class SettingsScene(Scene):
    music = "title"

    def __init__(self, app):
        super().__init__(app)
        self.index = 0
        self.rects = [pygame.Rect(90, 130 + i * 58, 600, 50) for i in range(len(ROWS))]
        self.hover = [0.0] * len(ROWS)
        self.dragging = None

    @property
    def settings(self):
        return self.save.settings

    def change(self, key, kind, step):
        s = self.settings
        if kind == "slider":
            s[key] = round(max(0.0, min(1.0, s[key] + step * 0.05)), 2)
            self.sfx("ui_move")
        else:
            s[key] = not s[key]
            self.sfx("ui_select")
            if key == "fullscreen":
                self.app.set_fullscreen(s[key])

    def update(self, dt):
        super().update(dt)
        inp = self.inp
        if inp.hit("back"):
            self.save.save()
            self.sfx("ui_back")
            self.app.pop()
            return
        old = self.index
        if inp.hit("down"):
            self.index = (self.index + 1) % len(ROWS)
        if inp.hit("up"):
            self.index = (self.index - 1) % len(ROWS)
        if inp.mouse_moved or inp.clicked:
            for i, r in enumerate(self.rects):
                if r.collidepoint(inp.mouse_pos):
                    self.index = i
        if self.index != old:
            self.sfx("ui_move")
        key, _, kind = ROWS[self.index]
        step = (1 if inp.hit("right") else 0) - (1 if inp.hit("left") else 0)
        if step:
            self.change(key, kind, step)
        if inp.hit("confirm"):
            self.change(key, kind, 1 if kind == "toggle" else 0)
        if inp.clicked and self.rects[self.index].collidepoint(inp.mouse_pos):
            if kind == "toggle":
                self.change(key, kind, 1)
            else:
                self.dragging = self.index
        held = pygame.mouse.get_pressed()[0] if pygame.display.get_init() else False
        if self.dragging is not None:
            if not held:
                self.dragging = None
                self.save.save()
            else:
                k2 = ROWS[self.dragging][0]
                bar = self.slider_rect(self.rects[self.dragging])
                frac = (inp.mouse_pos[0] - bar.x) / bar.w
                self.settings[k2] = round(max(0.0, min(1.0, frac)), 2)
        for i in range(len(ROWS)):
            target = 1.0 if i == self.index else 0.0
            self.hover[i] += (target - self.hover[i]) * min(1.0, dt * 10)

    @staticmethod
    def slider_rect(r):
        return pygame.Rect(r.right - 280, r.centery - 6, 250, 12)

    def draw(self, screen):
        self.backdrop(screen, PURPLE)
        self.header(screen, "SETTINGS", PURPLE, flux=False)
        for i, ((key, label, kind), r) in enumerate(zip(ROWS, self.rects)):
            k = self.hover[i]
            rr = r.inflate(int(10 * k), int(4 * k))
            ui.panel(screen, rr, mix(scale(PURPLE, 0.4), CYAN, k), mix(PANEL, scale(CYAN, 0.1), k), 230, 12,
                     glow=0.7 * k)
            assets.text(screen, label, 24, WHITE if k > 0.5 else mix(GREY, WHITE, 0.5), (rr.x + 22, rr.centery),
                        "midleft", bold=True)
            v = self.settings[key]
            if kind == "slider":
                bar = self.slider_rect(rr)
                ui.bar(screen, bar, v, mix(PURPLE, CYAN, v))
                knob = (int(bar.x + bar.w * v), bar.centery)
                pygame.draw.circle(screen, WHITE, knob, 10)
                pygame.draw.circle(screen, mix(PURPLE, CYAN, v), knob, 7)
                assets.text(screen, f"{int(v * 100)}%", 20, GREY, (bar.x - 16, rr.centery), "midright",
                            shadow=False)
            else:
                sw = pygame.Rect(rr.right - 96, rr.centery - 14, 66, 28)
                pygame.draw.rect(screen, scale(CYAN, 0.5) if v else (40, 40, 62), sw, border_radius=14)
                kx = sw.right - 14 if v else sw.x + 14
                pygame.draw.circle(screen, WHITE if v else GREY, (kx, sw.centery), 11)
                assets.text(screen, "ON" if v else "OFF", 18, CYAN if v else GREY, (sw.x - 14, sw.centery),
                            "midright", bold=True)
        box = pygame.Rect(730, 130, 470, len(ROWS) * 58 - 8)
        ui.panel(screen, box, CYAN, PANEL, 225, 16)
        assets.text(screen, "CONTROLS", 18, CYAN, (box.x + 22, box.y + 16), bold=True)
        for i, (action, keys) in enumerate(CONTROLS):
            y = box.y + 52 + i * 46
            assets.text(screen, action, 20, WHITE, (box.x + 22, y), bold=True)
            assets.text(screen, keys, 19, GREY, (box.right - 22, y + 2), "topright", shadow=False)
            pygame.draw.line(screen, (36, 36, 60), (box.x + 22, y + 34), (box.right - 22, y + 34), 1)
        assets.text(screen, f"Save folder: {self.save.path or '(not saved)'}", 16, GREY,
                    (WIDTH // 2, 640), "center", shadow=False)
        ui.hint(screen, "UP / DOWN choose   LEFT / RIGHT adjust   ENTER toggle   ESC save & back")
