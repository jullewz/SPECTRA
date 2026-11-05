"""Reusable interface pieces: panels, buttons, focus-driven menus, bars and titles.

Menus work the same with keyboard, gamepad and mouse: one item has focus, arrows move it,
confirm activates it, and hovering or clicking with the mouse does the same thing.

created by jullewz
"""

import math

import pygame

from . import assets
from .config import CYAN, DIM, GREY, HEIGHT, PANEL, WHITE, WIDTH
from .util import approach, clamp, ease_out_cubic, mix, scale

_panels = {}


_glows = {}


def _glow_frame(size, color, radius, glow):
    """A soft neon halo around a rounded rectangle, added on top of the scene."""
    key = (size, color, radius, glow)
    g = _glows.get(key)
    if g is None:
        if len(_glows) > 300:
            _glows.clear()
        w, h = size
        g = pygame.Surface((w + 36, h + 36), pygame.SRCALPHA)
        for i in range(8, 0, -1):
            k = glow * 0.22 * (1 - i / 9) ** 1.6
            r = pygame.Rect(18 - i * 2, 18 - i * 2, w + i * 4, h + i * 4)
            pygame.draw.rect(g, scale(color, k), r, 2, border_radius=radius + i * 2)
        _glows[key] = g
    return g


def panel(surface, rect, border=CYAN, fill=PANEL, alpha=228, radius=16, width=2, glow=0.0):
    """A rounded translucent panel with a neon border."""
    rect = pygame.Rect(rect)
    if rect.w <= 0 or rect.h <= 0:
        return rect
    if glow > 0.02:
        g = _glow_frame(rect.size, border, radius, round(min(glow, 1.5) * 8) / 8)
        surface.blit(g, (rect.x - 18, rect.y - 18), special_flags=pygame.BLEND_ADD)
    key = (rect.size, border, fill, alpha, radius, width)
    s = _panels.get(key)
    if s is None:
        if len(_panels) > 400:
            _panels.clear()
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (*fill, alpha), s.get_rect(), border_radius=radius)
        pygame.draw.rect(s, (*border, 255), s.get_rect(), width, border_radius=radius)
        _panels[key] = s
    surface.blit(s, rect.topleft)
    return rect


def dim(surface, amount):
    """Darken everything already drawn (0 = nothing, 1 = black)."""
    k = int(255 * clamp(1 - amount, 0, 1))
    surface.fill((k, k, k), special_flags=pygame.BLEND_MULT)


def bar(surface, rect, frac, color, back=(28, 28, 48), border=None, shine=True):
    rect = pygame.Rect(rect)
    r = rect.h // 2
    pygame.draw.rect(surface, back, rect, border_radius=r)
    w = int(rect.w * clamp(frac, 0.0, 1.0))
    if w > 0:
        pygame.draw.rect(surface, color, (rect.x, rect.y, max(w, rect.h), rect.h), border_radius=r)
        if shine and rect.h >= 6:
            pygame.draw.line(surface, mix(color, WHITE, 0.55), (rect.x + r, rect.y + 2),
                             (rect.x + max(r, w - r), rect.y + 2), 1)
    if border:
        pygame.draw.rect(surface, border, rect, 1, border_radius=r)


def title(surface, string, size, color, center, glow_color=None, spread=5):
    """Big glowing text, added onto whatever is underneath."""
    g = assets.glow_text(string, size, color, glow_color, spread)
    surface.blit(g, (int(center[0] - g.get_width() / 2), int(center[1] - g.get_height() / 2)),
                 special_flags=pygame.BLEND_ADD)


def pips(surface, x, y, filled, total, color, size=5, gap=3):
    for i in range(total):
        c = color if i < filled else (50, 50, 72)
        pygame.draw.rect(surface, c, (x + i * (size + gap), y, size, size), border_radius=1)


def hint(surface, string, y=HEIGHT - 30, color=GREY):
    assets.text(surface, string, 20, color, (WIDTH // 2, y), "center", shadow=False)


def arrow(surface, x, y, angle, color, size=14):
    pts = [(x + math.cos(angle) * size, y + math.sin(angle) * size),
           (x + math.cos(angle + 2.5) * size * 0.8, y + math.sin(angle + 2.5) * size * 0.8),
           (x + math.cos(angle - 2.5) * size * 0.8, y + math.sin(angle - 2.5) * size * 0.8)]
    pygame.draw.polygon(surface, scale(color, 0.4), [(px + 1, py + 1) for px, py in pts])
    pygame.draw.polygon(surface, color, pts)


# --------------------------------------------------------------------------- buttons and menus


class Button:
    def __init__(self, rect, label, action=None, color=CYAN, sub=None, icon=None, enabled=True, size=28, data=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.color = color
        self.sub = sub
        self.icon = icon
        self.enabled = enabled
        self.size = size
        self.data = data
        self.hover = 0.0

    def update(self, dt, focused):
        self.hover = approach(self.hover, 1.0 if focused else 0.0, dt * 7)

    def draw(self, surface, focused):
        k = ease_out_cubic(self.hover)
        col = self.color if self.enabled else DIM
        r = self.rect.inflate(int(12 * k), int(4 * k))
        panel(surface, r, mix(scale(col, 0.5), col, k), mix(PANEL, scale(col, 0.16), k), 235, 12,
              glow=0.8 * k)
        tc = mix(scale(WHITE, 0.82), WHITE, k) if self.enabled else DIM
        if self.icon is not None:
            surface.blit(self.icon, (r.x + 10, r.centery - self.icon.get_height() // 2))
            x = r.x + 20 + self.icon.get_width()
            if self.sub:
                assets.text(surface, self.label, self.size, tc, (x, r.centery - 2), "bottomleft", bold=True)
                assets.text(surface, self.sub, 19, GREY, (x, r.centery + 3), "topleft", shadow=False)
            else:
                assets.text(surface, self.label, self.size, tc, (x, r.centery), "midleft", bold=True)
        elif self.sub:
            assets.text(surface, self.label, self.size, tc, (r.centerx, r.centery - 2), "midbottom", bold=True)
            assets.text(surface, self.sub, 19, GREY, (r.centerx, r.centery + 3), "midtop", shadow=False)
        else:
            assets.text(surface, self.label, self.size, tc, r.center, "center", bold=True)


class Menu:
    """Keeps track of which item has focus and turns input into activations."""

    def __init__(self, items, cols=1, index=0, audio=None):
        self.items = items
        self.cols = max(1, cols)
        self.index = min(index, max(0, len(items) - 1))
        self.audio = audio

    def _sound(self, name):
        if self.audio is not None:
            self.audio.play(name)

    def move(self, step):
        if not self.items:
            return
        self.index = (self.index + step) % len(self.items)
        self._sound("ui_move")

    def handle(self, inp):
        """Returns the activated item, or None."""
        if not self.items:
            return None
        if inp.mouse_moved or inp.clicked:
            for i, it in enumerate(self.items):
                if it.rect.collidepoint(inp.mouse_pos):
                    if i != self.index:
                        self.index = i
                        self._sound("ui_move")
                    if inp.clicked:
                        return self.activate()
                    break
        if inp.hit("up"):
            self.move(-self.cols)
        if inp.hit("down"):
            self.move(self.cols)
        if self.cols > 1:
            if inp.hit("left"):
                self.move(-1)
            if inp.hit("right"):
                self.move(1)
        if inp.hit("confirm"):
            return self.activate()
        return None

    def activate(self):
        it = self.items[self.index]
        if getattr(it, "enabled", True):
            self._sound("ui_select")
            if getattr(it, "action", None):
                it.action()
            return it
        self._sound("ui_back")
        return None

    @property
    def focused(self):
        return self.items[self.index] if self.items else None

    def update(self, dt):
        for i, it in enumerate(self.items):
            it.update(dt, i == self.index)

    def draw(self, surface):
        for i, it in enumerate(self.items):
            it.draw(surface, i == self.index)
