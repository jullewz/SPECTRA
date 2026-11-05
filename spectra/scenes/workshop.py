"""The Workshop: spend flux on permanent upgrades.

created by jullewz
"""

import pygame

from .. import assets, ui
from ..config import DIM, GOLD, GREY, MAGENTA, PANEL, WHITE, WIDTH
from ..data import META
from ..util import mix, scale
from .base import Scene

COLS = 4
TILE_W, TILE_H = 270, 112


class WorkshopScene(Scene):
    music = "title"

    def __init__(self, app):
        super().__init__(app)
        x0 = (WIDTH - (COLS * TILE_W + (COLS - 1) * 18)) // 2
        self.tiles = []
        for i, m in enumerate(META):
            r = pygame.Rect(x0 + (i % COLS) * (TILE_W + 18), 118 + (i // COLS) * (TILE_H + 16), TILE_W, TILE_H)
            self.tiles.append(_Tile(r, m, self))
        rows = (len(META) + COLS - 1) // COLS
        self.refund = ui.Button((WIDTH // 2 - 140, 118 + rows * (TILE_H + 16) + 6, 280, 46), "REFUND ALL",
                                self.do_refund, MAGENTA, size=24)
        self.menu = ui.Menu(self.tiles + [self.refund], cols=COLS, audio=app.audio)
        self.flash = {}
        self.confirm_refund = 0.0

    def buy(self, meta):
        if self.save.buy(meta.id):
            self.sfx("levelup", 0.7)
            self.flash[meta.id] = 1.0
            self.save.save()
        else:
            self.sfx("ui_back")

    def do_refund(self):
        if self.confirm_refund <= 0:
            self.confirm_refund = 2.5
            self.sfx("warn", 0.6)
            return
        total = self.save.refund_all()
        self.confirm_refund = 0
        self.save.save()
        self.sfx("chest" if total else "ui_back")

    def update(self, dt):
        super().update(dt)
        self.confirm_refund = max(0.0, self.confirm_refund - dt)
        for k in list(self.flash):
            self.flash[k] -= dt * 2.5
            if self.flash[k] <= 0:
                del self.flash[k]
        if self.inp.hit("back"):
            self.sfx("ui_back")
            self.app.pop()
            return
        self.menu.update(dt)
        self.menu.handle(self.inp)

    def draw(self, screen):
        focus = self.menu.focused
        accent = focus.meta.color if isinstance(focus, _Tile) else MAGENTA
        self.backdrop(screen, accent)
        self.header(screen, "WORKSHOP", GOLD)
        assets.text(screen, "Permanent upgrades for every pilot. Flux is earned in every run, win or lose.", 21, GREY,
                    (WIDTH // 2, 96), "center", shadow=False)
        self.menu.draw(screen)
        if self.confirm_refund > 0:
            self.refund.label = "CONFIRM REFUND?"
        else:
            self.refund.label = "REFUND ALL"
        spent = sum(sum(m.cost(k) for k in range(self.save.rank(m.id))) for m in META)
        assets.text(screen, f"{spent:,} flux invested", 19, GREY, (WIDTH // 2, self.refund.rect.bottom + 22),
                    "center", shadow=False)
        ui.hint(screen, "arrows to browse   ENTER to buy   ESC back")


class _Tile:
    def __init__(self, rect, meta, scene):
        self.rect = rect
        self.meta = meta
        self.scene = scene
        self.hover = 0.0
        self.enabled = True

    def action(self):
        self.scene.buy(self.meta)

    def update(self, dt, focused):
        self.hover += ((1.0 if focused else 0.0) - self.hover) * min(1.0, dt * 10)

    def draw(self, screen, focused):
        save, m = self.scene.save, self.meta
        rank = save.rank(m.id)
        maxed = rank >= m.max_rank
        cost = m.cost(rank)
        afford = save.flux >= cost
        k = self.hover
        flash = self.scene.flash.get(m.id, 0)
        col = m.color if (afford or maxed) else scale(m.color, 0.6)
        r = self.rect.inflate(int(8 * k), int(6 * k))
        ui.panel(screen, r, mix(scale(col, 0.45), mix(col, WHITE, flash), k), mix(PANEL, scale(col, 0.15), k),
                 235, 14, glow=0.9 * k + flash)
        screen.blit(assets.icon(m.icon, col, 54), (r.x + 12, r.y + 12))
        assets.text(screen, m.name, 24, WHITE, (r.x + 78, r.y + 12), bold=True)
        assets.text_block(screen, m.desc, 17, GREY, r.x + 78, r.y + 40, r.w - 90, 2)
        ui.pips(screen, r.x + 14, r.bottom - 20, rank, m.max_rank, col, 6, 4)
        if maxed:
            assets.text(screen, "MAX", 20, GOLD, (r.right - 14, r.bottom - 14), "bottomright", bold=True)
        else:
            c = GOLD if afford else DIM
            assets.text(screen, f"{cost:,}", 22, c, (r.right - 14, r.bottom - 12), "bottomright", bold=True)
            w = assets.text_width(f"{cost:,}", 22, True)
            screen.blit(assets.icon("flux", c, 20, frame=False), (r.right - 38 - w, r.bottom - 34))

