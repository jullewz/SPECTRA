"""Choose a pilot and a stage.

created by jullewz
"""

import math

import pygame

from .. import assets, ui
from ..config import CYAN, DIM, GOLD, GREY, PANEL, WHITE, WIDTH
from ..data import ACH_BY_ID, CHARACTERS, STAGE_BY_ID, STAGES
from ..util import approach, ease_out_cubic, mix, scale
from ..weapons import WEAPONS, weapon_icon
from .base import Scene

CARD_W, CARD_H = 210, 286
STAGE_W, STAGE_H = 360, 112


class SelectScene(Scene):
    music = "title"

    def __init__(self, app):
        super().__init__(app)
        ids = [c.id for c in CHARACTERS]
        sids = [s.id for s in STAGES]
        self.ci = ids.index(self.save.last_char) if self.save.last_char in ids else 0
        self.si = sids.index(self.save.last_stage) if self.save.last_stage in sids else 0
        if not self.save.char_unlocked(CHARACTERS[self.ci]):
            self.ci = 0
        if not self.save.stage_unlocked(STAGES[self.si]):
            self.si = 0
        self.row = 0
        x0 = (WIDTH - (5 * CARD_W + 4 * 20)) // 2
        self.char_rects = [pygame.Rect(x0 + i * (CARD_W + 20), 112, CARD_W, CARD_H) for i in range(len(CHARACTERS))]
        sx0 = (WIDTH - (3 * STAGE_W + 2 * 25)) // 2
        self.stage_rects = [pygame.Rect(sx0 + i * (STAGE_W + 25), 430, STAGE_W, STAGE_H) for i in range(len(STAGES))]
        self.start = ui.Button((WIDTH // 2 - 170, 576, 340, 62), "LAUNCH", self.launch, CYAN, size=34)
        self.hover = [0.0] * 8

    @property
    def char(self):
        return CHARACTERS[self.ci]

    @property
    def stage(self):
        return STAGES[self.si]

    def launch(self):
        if not (self.save.char_unlocked(self.char) and self.save.stage_unlocked(self.stage)):
            self.sfx("ui_back")
            return
        self.save.last_char = self.char.id
        self.save.last_stage = self.stage.id
        self.save.save()
        from .game import GameScene
        self.app.replace(GameScene(self.app, self.char.id, self.stage.id))

    def update(self, dt):
        super().update(dt)
        inp = self.inp
        if inp.hit("back"):
            self.sfx("ui_back")
            self.app.pop()
            return
        if inp.mouse_moved or inp.clicked:
            for i, r in enumerate(self.char_rects):
                if r.collidepoint(inp.mouse_pos):
                    if (self.row, self.ci) != (0, i):
                        self.sfx("ui_move")
                    self.row, self.ci = 0, i
            for i, r in enumerate(self.stage_rects):
                if r.collidepoint(inp.mouse_pos):
                    if (self.row, self.si) != (1, i):
                        self.sfx("ui_move")
                    self.row, self.si = 1, i
            if self.start.rect.collidepoint(inp.mouse_pos):
                self.row = 2
                if inp.clicked:
                    self.sfx("ui_select")
                    self.launch()
                    return
        if inp.hit("up") and self.row > 0:
            self.row -= 1
            self.sfx("ui_move")
        if inp.hit("down") and self.row < 2:
            self.row += 1
            self.sfx("ui_move")
        step = (1 if inp.hit("right") else 0) - (1 if inp.hit("left") else 0)
        if step:
            if self.row == 0:
                self.ci = (self.ci + step) % len(CHARACTERS)
                self.sfx("ui_move")
            elif self.row == 1:
                self.si = (self.si + step) % len(STAGES)
                self.sfx("ui_move")
        if inp.hit("confirm"):
            if self.row < 2:
                self.row += 1
                self.sfx("ui_select")
            else:
                self.sfx("ui_select")
                self.launch()
        self.start.update(dt, self.row == 2)

    # ---------------------------------------------------------------- drawing

    def draw(self, screen):
        self.backdrop(screen, self.char.color)
        self.header(screen, "CHOOSE YOUR PILOT", self.char.color)
        for i, (c, r) in enumerate(zip(CHARACTERS, self.char_rects)):
            focused = i == self.ci
            self.hover[i] = approach(self.hover[i], 1.0 if focused else 0.0, 0.12)
            self.draw_char(screen, c, r, focused, ease_out_cubic(self.hover[i]))
        assets.text(screen, "STAGE", 26, GREY, (WIDTH // 2, 410), "center", bold=True)
        for i, (s, r) in enumerate(zip(STAGES, self.stage_rects)):
            self.draw_stage(screen, s, r, i == self.si)
        ok = self.save.char_unlocked(self.char) and self.save.stage_unlocked(self.stage)
        self.start.enabled = ok
        self.start.color = self.stage.accent if ok else DIM
        self.start.draw(screen, self.row == 2)
        ui.hint(screen, "LEFT / RIGHT choose   UP / DOWN switch row   ENTER confirm   ESC back")

    def draw_char(self, screen, c, r, focused, k):
        unlocked = self.save.char_unlocked(c)
        lift = int(10 * k)
        rr = r.move(0, -lift)
        sel_row = self.row == 0
        border = c.color if unlocked else DIM
        ui.panel(screen, rr, mix(scale(border, 0.45), border, k), mix(PANEL, scale(border, 0.12), k), 235, 16,
                 glow=(1.0 if sel_row else 0.5) * k)
        cx = rr.centerx
        if unlocked:
            assets.blit_glow(screen, cx, rr.y + 78, 70, c.color, 0.35 + 0.25 * k)
            spr = assets.shape_sprite("ship", 34, c.color, -math.pi / 2 + math.sin(self.t * 1.5 + rr.x) * 0.25)
            assets.blit_center(screen, spr, cx, rr.y + 78)
            assets.text(screen, c.name.upper(), 32, WHITE, (cx, rr.y + 142), "center", bold=True)
            assets.text(screen, c.title, 20, c.color, (cx, rr.y + 166), "center", shadow=False)
            y = assets.text_block(screen, c.perk, 18, GREY, rr.x + 14, rr.y + 186, CARD_W - 28, 2)
            wcls = WEAPONS[c.weapon]
            screen.blit(weapon_icon(wcls, 38), (rr.x + 14, rr.bottom - 52))
            assets.text(screen, "starts with", 16, GREY, (rr.x + 60, rr.bottom - 48), shadow=False)
            assets.text(screen, wcls.name, 20, wcls.color, (rr.x + 60, rr.bottom - 32), bold=True)
        else:
            spr = assets.shape_sprite("ship", 34, (60, 60, 80), -math.pi / 2)
            assets.blit_center(screen, spr, cx, rr.y + 78)
            assets.text(screen, "LOCKED", 30, DIM, (cx, rr.y + 142), "center", bold=True)
            ach = ACH_BY_ID.get(c.unlock)
            if ach:
                assets.text(screen, "Unlock:", 18, GREY, (cx, rr.y + 176), "center", shadow=False)
                assets.text_block(screen, ach.desc.split(". Unlocks")[0] + ".", 19, GOLD, rr.x + 16, rr.y + 196,
                                  CARD_W - 32, 2)

    def draw_stage(self, screen, s, r, focused):
        unlocked = self.save.stage_unlocked(s)
        sel = focused and self.row == 1
        border = s.accent if unlocked else DIM
        ui.panel(screen, r, border if focused else scale(border, 0.45), mix(PANEL, scale(s.base, 1.6), 0.6), 235, 14,
                 glow=0.9 if sel else (0.35 if focused else 0))
        if unlocked:
            assets.text(screen, s.name.upper(), 28, WHITE if focused else GREY, (r.x + 18, r.y + 16), bold=True)
            stars = int(round((s.difficulty - 1) / 0.3)) + 1
            for k in range(3):
                col = s.accent if k < stars else (50, 50, 70)
                pts = assets.transform(assets.SHAPES["star"], r.right - 68 + k * 22, r.y + 26, 9, math.pi / 4)
                pygame.draw.polygon(screen, col, pts)
            assets.text_block(screen, s.desc, 19, GREY, r.x + 18, r.y + 50, STAGE_W - 36, 2)
            if s.id in self.save.cleared:
                assets.text(screen, "CLEARED", 16, GOLD, (r.right - 16, r.bottom - 12), "bottomright", bold=True)
        else:
            assets.text(screen, "LOCKED", 28, DIM, (r.x + 18, r.y + 16), bold=True)
            req = STAGE_BY_ID[s.unlock].name
            assets.text(screen, f"Clear {req} to unlock", 20, GOLD, (r.x + 18, r.y + 56), shadow=False)
