"""The Codex: everything you have discovered so far.

created by jullewz
"""

import math

import pygame

from .. import assets, ui
from ..bosses import BOSSES
from ..config import DIM, GOLD, GREY, PANEL, TEAL, WHITE, WIDTH
from ..data import PASSIVES
from ..entities import CODEX_ENEMIES, ENEMY_TYPES
from ..util import mix, scale
from ..weapons import WEAPONS, weapon_icon
from .base import Scene

TABS = ["WEAPONS", "MODULES", "ENEMIES", "BOSSES"]
ROW_H = 46
LIST_ROWS = 11


class CodexScene(Scene):
    music = "title"

    def __init__(self, app):
        super().__init__(app)
        self.tab = 0
        self.index = 0
        self.scroll = 0.0
        self.tab_rects = [pygame.Rect(WIDTH // 2 - 340 + i * 172, 96, 164, 40) for i in range(len(TABS))]

    def entries(self):
        seen = self.save.seen
        if self.tab == 0:
            return [("w", cls, "w:" + wid in seen) for wid, cls in WEAPONS.items()]
        if self.tab == 1:
            return [("p", ps, "p:" + ps.id in seen) for ps in PASSIVES]
        if self.tab == 2:
            return [("e", ENEMY_TYPES[k], "e:" + k in seen) for k in CODEX_ENEMIES]
        return [("b", cls, "b:" + bid in seen) for bid, cls in BOSSES.items()]

    def update(self, dt):
        super().update(dt)
        inp = self.inp
        if inp.hit("back"):
            self.sfx("ui_back")
            self.app.pop()
            return
        n = len(self.entries())
        old_tab, old_idx = self.tab, self.index
        if inp.hit("left"):
            self.tab = (self.tab - 1) % len(TABS)
        if inp.hit("right"):
            self.tab = (self.tab + 1) % len(TABS)
        if inp.clicked:
            for i, r in enumerate(self.tab_rects):
                if r.collidepoint(inp.mouse_pos):
                    self.tab = i
            for i in range(n):
                if self.row_rect(i).collidepoint(inp.mouse_pos):
                    self.index = i
        if self.tab != old_tab:
            self.index = 0
            self.scroll = 0
        else:
            if inp.hit("down"):
                self.index = (self.index + 1) % n
            if inp.hit("up"):
                self.index = (self.index - 1) % n
            if inp.wheel:
                self.index = max(0, min(n - 1, self.index - inp.wheel))
        if (self.tab, self.index) != (old_tab, old_idx):
            self.sfx("ui_move")
        target = max(0, min(self.index - LIST_ROWS // 2, n - LIST_ROWS))
        self.scroll += (target - self.scroll) * min(1.0, dt * 12)

    def row_rect(self, i):
        return pygame.Rect(60, int(156 + (i - self.scroll) * ROW_H), 380, ROW_H - 6)

    # ---------------------------------------------------------------- drawing

    def draw(self, screen):
        self.backdrop(screen, TEAL)
        self.header(screen, "CODEX", TEAL)
        for i, (name, r) in enumerate(zip(TABS, self.tab_rects)):
            on = i == self.tab
            ui.panel(screen, r, TEAL if on else scale(TEAL, 0.35), scale(TEAL, 0.15) if on else PANEL, 230, 10,
                     glow=0.6 if on else 0)
            assets.text(screen, name, 20, WHITE if on else GREY, r.center, "center", bold=True)
        items = self.entries()
        found = sum(1 for e in items if e[2])
        assets.text(screen, f"{found}/{len(items)} discovered", 18, GREY, (60, 150), "bottomleft", shadow=False)
        area = pygame.Rect(56, 154, 390, LIST_ROWS * ROW_H)
        clip = screen.get_clip()
        screen.set_clip(area)
        for i, (kind, obj, known) in enumerate(items):
            r = self.row_rect(i)
            if r.bottom < area.y or r.y > area.bottom:
                continue
            on = i == self.index
            col = self.color_of(kind, obj) if known else DIM
            ui.panel(screen, r, col if on else scale(col, 0.4), PANEL, 230, 10, glow=0.6 if on else 0)
            self.small_icon(screen, kind, obj, known, r.x + 22, r.centery)
            assets.text(screen, self.name_of(kind, obj) if known else "???", 21, WHITE if known else DIM,
                        (r.x + 48, r.centery), "midleft", bold=on)
        screen.set_clip(clip)
        kind, obj, known = items[self.index]
        self.draw_detail(screen, kind, obj, known)
        ui.hint(screen, "LEFT / RIGHT tabs   UP / DOWN entries   ESC back")

    def color_of(self, kind, obj):
        return obj.color

    def name_of(self, kind, obj):
        if kind == "b":
            return obj.title.title()
        return obj.name

    def small_icon(self, screen, kind, obj, known, x, y):
        if kind == "w":
            screen.blit(weapon_icon(obj, 30, locked=not known), (x - 15, y - 15))
        elif kind == "p":
            screen.blit(assets.icon(obj.id, obj.color, 30, locked=not known), (x - 15, y - 15))
        else:
            col = obj.color if known else (60, 60, 80)
            assets.blit_center(screen, assets.shape_sprite(obj.shape, 11, col, -math.pi / 2), x, y)

    def draw_detail(self, screen, kind, obj, known):
        r = pygame.Rect(470, 154, 750, LIST_ROWS * ROW_H - 6)
        col = obj.color if known else DIM
        ui.panel(screen, r, col, PANEL, 232, 18, glow=0.4)
        if not known:
            assets.text(screen, "UNDISCOVERED", 40, DIM, (r.centerx, r.centery - 20), "center", bold=True)
            hint = {"w": "Pick this weapon during a run to log it.", "p": "Take this module during a run.",
                    "e": "Survive long enough to meet it.", "b": "It is waiting further in."}[kind]
            assets.text(screen, hint, 22, GREY, (r.centerx, r.centery + 24), "center", shadow=False)
            return
        cx, cy = r.x + 120, r.y + 120
        assets.blit_glow(screen, cx, cy, 110, col, 0.4)
        if kind == "w":
            screen.blit(weapon_icon(obj, 120), (cx - 60, cy - 60))
        elif kind == "p":
            screen.blit(assets.icon(obj.id, obj.color, 120), (cx - 60, cy - 60))
        else:
            size = min(70, obj.size if kind == "b" else obj.radius * 3)
            spr = assets.shape_sprite(obj.shape, size, obj.color, self.t * 0.6, elite=kind == "b")
            assets.blit_center(screen, spr, cx, cy)
        x = r.x + 250
        assets.text(screen, self.name_of(kind, obj), 40, WHITE, (x, r.y + 40), bold=True)
        sub = {"w": "WEAPON", "p": "MODULE", "e": "ENEMY", "b": "BOSS"}[kind]
        assets.text(screen, sub, 18, col, (x, r.y + 92), bold=True)
        desc = obj.subtitle if kind == "b" else obj.desc
        y = assets.text_block(screen, desc, 22, mix(GREY, WHITE, 0.4), x, r.y + 124, r.right - x - 30, 4)
        y = max(y, r.y + 250)
        if kind == "w":
            self.weapon_detail(screen, obj, r, y)
        elif kind == "p":
            assets.text(screen, f"Max level {obj.max_level}", 22, GREY, (r.x + 40, y), shadow=False)
            partners = [cls for cls in WEAPONS.values() if cls.evo_passive == obj.id]
            for i, cls in enumerate(partners):
                yy = y + 44 + i * 70
                screen.blit(weapon_icon(cls, 52), (r.x + 40, yy))
                assets.text(screen, f"Evolves {cls.name}", 22, WHITE, (r.x + 106, yy + 4), bold=True)
                known_evo = "x:" + cls.id in self.save.seen
                assets.text(screen, f"into {cls.evo_name}" if known_evo else "into ???", 20, GOLD,
                            (r.x + 106, yy + 30), shadow=False)
        elif kind == "e":
            rows = [("Health", f"{obj.hp:g}"), ("Speed", f"{obj.speed:g}"), ("Contact damage", f"{obj.damage:g}"),
                    ("Experience", str(obj.xp)), ("Behaviour", obj.behavior)]
            self.stat_rows(screen, rows, r, y, col)
        else:
            rows = [("Base health", f"{obj.base_hp:,}"), ("Speed", f"{obj.move_speed:g}"),
                    ("Damage", f"{obj.base_damage:g}")]
            self.stat_rows(screen, rows, r, y, col)

    def stat_rows(self, screen, rows, r, y, col):
        for i, (name, value) in enumerate(rows):
            yy = y + i * 40
            assets.text(screen, name, 21, GREY, (r.x + 40, yy), shadow=False)
            assets.text(screen, value, 22, WHITE, (r.x + 360, yy), "topright", bold=True)
            pygame.draw.line(screen, scale(col, 0.25), (r.x + 40, yy + 31), (r.x + 360, yy + 31), 1)

    def weapon_detail(self, screen, cls, r, y):
        from ..data import PASSIVE_BY_ID
        ps = PASSIVE_BY_ID[cls.evo_passive]
        known_evo = "x:" + cls.id in self.save.seen
        assets.text(screen, "EVOLUTION", 18, GOLD, (r.x + 40, y), bold=True)
        screen.blit(weapon_icon(cls, 52), (r.x + 40, y + 30))
        assets.text(screen, "+", 34, GREY, (r.x + 112, y + 56), "center", bold=True)
        screen.blit(assets.icon(ps.id, ps.color, 52), (r.x + 134, y + 30))
        ui.arrow(screen, r.x + 212, y + 56, 0.0, GREY, 12)
        if known_evo:
            screen.blit(assets.icon(cls.id, cls.evo_color, 52, evolved=True), (r.x + 234, y + 30))
            assets.text(screen, cls.evo_name, 26, GOLD, (r.x + 304, y + 32), bold=True)
            assets.text_block(screen, cls.evo_desc, 19, GREY, r.x + 304, y + 64, r.right - r.x - 340, 2)
        else:
            screen.blit(assets.icon(cls.id, DIM, 52, locked=True), (r.x + 234, y + 30))
            assets.text(screen, "???", 26, DIM, (r.x + 304, y + 32), bold=True)
            assets.text(screen, f"Max out {cls.name}, own {ps.name}, then open a chest.", 19, GREY,
                        (r.x + 304, y + 66), shadow=False)
        assets.text(screen, f"Max level {cls.max_level}", 20, GREY, (r.x + 40, y + 110), shadow=False)
