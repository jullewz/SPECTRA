"""Everything on screen is drawn by code: glows, ship sprites, item icons and text.

Sprites are generated on first use and cached, so the per-frame cost is a dictionary
lookup and a blit.

created by jullewz
"""

import math

import pygame

from .config import DARK, GOLD, WHITE
from .util import TAU, mix, scale

_glows = {}
_sprites = {}
_text = {}
_icons = {}
_fonts = {}

# --------------------------------------------------------------------------- glow


def glow(radius, color, strength=1.0):
    """An opaque radial gradient meant to be blitted with BLEND_ADD (black adds nothing)."""
    radius = max(2, int(radius))
    q = max(1, int(strength * 20))
    key = (radius, color, q)
    surf = _glows.get(key)
    if surf is None:
        strength = q / 20
        size = radius * 2
        surf = pygame.Surface((size, size))
        surf.fill((0, 0, 0))
        step = 1 if radius < 48 else radius // 48
        for r in range(radius, 0, -step):
            t = r / radius
            pygame.draw.circle(surf, scale(color, strength * (1 - t) ** 2), (radius, radius), r)
        _glows[key] = surf
    return surf


def blit_glow(surface, x, y, radius, color, strength=1.0):
    g = glow(radius, color, strength)
    r = g.get_width() // 2
    surface.blit(g, (int(x) - r, int(y) - r), special_flags=pygame.BLEND_ADD)


def blit_center(surface, sprite, x, y):
    surface.blit(sprite, (int(x - sprite.get_width() / 2), int(y - sprite.get_height() / 2)))


# --------------------------------------------------------------------------- vector shapes


def _regular(n, rot=0.0):
    return [(math.cos(rot + i * TAU / n), math.sin(rot + i * TAU / n)) for i in range(n)]


def _star(n, inner, rot=0.0):
    pts = []
    for i in range(n * 2):
        a = rot + i * math.pi / n
        r = 1.0 if i % 2 == 0 else inner
        pts.append((math.cos(a) * r, math.sin(a) * r))
    return pts


SHAPES = {
    "ship": [(1.2, 0), (-0.45, 0.78), (-0.15, 0.0), (-0.45, -0.78)],
    "triangle": [(1.0, 0), (-0.62, 0.82), (-0.62, -0.82)],
    "dart": [(1.15, 0), (-0.8, 0.52), (-0.38, 0), (-0.8, -0.52)],
    "hexagon": _regular(6),
    "diamond": [(1.0, 0), (0, 0.66), (-1.0, 0), (0, -0.66)],
    "square": _regular(4, math.pi / 4),
    "chevron": [(1.0, 0), (-0.1, 0.9), (-0.72, 0.9), (0.08, 0), (-0.72, -0.9), (-0.1, -0.9)],
    "spiky": _star(7, 0.52),
    "star": _star(4, 0.42),
    "cross": [(1, 0.32), (0.32, 0.32), (0.32, 1), (-0.32, 1), (-0.32, 0.32), (-1, 0.32), (-1, -0.32),
              (-0.32, -0.32), (-0.32, -1), (0.32, -1), (0.32, -0.32), (1, -0.32)],
    "pentagon": _regular(5, -math.pi / 2),
    "octagon": _regular(8, math.pi / 8),
    "circle": _regular(18),
    "shard": [(1.0, 0), (0.0, 0.42), (-1.0, 0), (0.0, -0.42)],
}

ANGLES = 48


def transform(points, cx, cy, radius, angle):
    ca, sa = math.cos(angle), math.sin(angle)
    return [(cx + (x * ca - y * sa) * radius, cy + (x * sa + y * ca) * radius) for x, y in points]


def shape_sprite(shape, radius, color, angle=0.0, flash=False, elite=False):
    """A neon outline sprite: dark translucent body, bright rim, inner rim and a hot core."""
    idx = int(round(angle / TAU * ANGLES)) % ANGLES
    radius = max(2, int(radius))
    key = (shape, radius, color, idx, flash, elite)
    surf = _sprites.get(key)
    if surf is not None:
        return surf
    size = int(radius * (3.0 if elite else 2.5)) + 6
    c = size / 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    a = idx * TAU / ANGLES
    pts = transform(SHAPES[shape], c, c, radius, a)
    edge = WHITE if flash else color
    if elite:
        pygame.draw.polygon(surf, GOLD, transform(SHAPES[shape], c, c, radius * 1.32, a), 2)
    pygame.draw.polygon(surf, (255, 255, 255, 230) if flash else (*scale(color, 0.2), 225), pts)
    pygame.draw.polygon(surf, edge, pts, 2)
    pygame.draw.polygon(surf, scale(edge, 0.7), transform(SHAPES[shape], c, c, radius * 0.5, a), 1)
    pygame.draw.circle(surf, mix(edge, WHITE, 0.55), (int(c), int(c)), max(2, radius // 5))
    _sprites[key] = surf
    return surf


def orb_sprite(radius, color):
    """A small bright ball with a white core, used for bullets and orbiting shards."""
    radius = max(2, int(radius))
    key = ("orb", radius, color)
    surf = _sprites.get(key)
    if surf is None:
        size = radius * 2 + 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        pygame.draw.circle(surf, color, (c, c), radius)
        pygame.draw.circle(surf, mix(color, WHITE, 0.55), (c, c), max(1, int(radius * 0.62)))
        pygame.draw.circle(surf, WHITE, (c, c), max(1, int(radius * 0.3)))
        _sprites[key] = surf
    return surf


# --------------------------------------------------------------------------- text


def font(size, bold=False):
    key = (size, bold)
    f = _fonts.get(key)
    if f is None:
        f = pygame.font.Font(None, size)
        if bold:
            f.set_bold(True)
        _fonts[key] = f
    return f


def render(string, size, color, bold=False):
    key = (string, size, color, bold)
    surf = _text.get(key)
    if surf is None:
        if len(_text) > 3000:
            _text.clear()
        surf = font(size, bold).render(string, True, color)
        _text[key] = surf
    return surf


def text(surface, string, size, color, pos, anchor="topleft", bold=False, shadow=True):
    """Draw text anchored at pos ("center", "midtop", "topright", ...). Returns its rect."""
    string = str(string)
    surf = render(string, size, color, bold)
    rect = surf.get_rect()
    setattr(rect, anchor, (int(pos[0]), int(pos[1])))
    if shadow:
        surface.blit(render(string, size, (0, 0, 0), bold), (rect.x + 2, rect.y + 2))
    surface.blit(surf, rect)
    return rect


def text_width(string, size, bold=False):
    return font(size, bold).size(str(string))[0]


def wrap(string, size, width, bold=False):
    """Break a string into lines no wider than width pixels."""
    f = font(size, bold)
    lines = []
    for para in str(string).split("\n"):
        line = ""
        for word in para.split(" "):
            trial = word if not line else line + " " + word
            if f.size(trial)[0] <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def text_block(surface, string, size, color, x, y, width, line_gap=4, bold=False):
    """Draw wrapped text; returns the y below the last line."""
    h = font(size, bold).get_linesize()
    for line in wrap(string, size, width, bold):
        text(surface, line, size, color, (x, y), bold=bold, shadow=False)
        y += h + line_gap
    return y


def glow_text(string, size, color, glow_color=None, spread=5):
    """Big title text with a soft halo. Returns an opaque surface for BLEND_ADD blitting."""
    key = ("glow", string, size, color, glow_color, spread)
    surf = _text.get(key)
    if surf is not None:
        return surf
    f = font(size, True)
    base = f.render(string, True, color)
    pad = size // 2
    w, h = base.get_width() + pad * 2, base.get_height() + pad * 2
    halo = pygame.Surface((w, h))
    halo.fill((0, 0, 0))
    halo.blit(f.render(string, True, glow_color or color), (pad, pad))
    small = pygame.transform.smoothscale(halo, (max(1, w // spread), max(1, h // spread)))
    blurred = pygame.transform.smoothscale(small, (w, h))
    surf = pygame.Surface((w, h))
    surf.fill((0, 0, 0))
    surf.blit(blurred, (0, 0), special_flags=pygame.BLEND_ADD)
    surf.blit(blurred, (0, 0), special_flags=pygame.BLEND_ADD)
    surf.blit(base, (pad, pad))
    _text[key] = surf
    return surf


# --------------------------------------------------------------------------- icons


def _arc_points(cx, cy, r, a0, a1, steps=18):
    return [(cx + math.cos(a0 + (a1 - a0) * i / steps) * r, cy + math.sin(a0 + (a1 - a0) * i / steps) * r)
            for i in range(steps + 1)]


def _stroke(s, c, pts, width=3, closed=False):
    pygame.draw.lines(s, scale(c, 0.4), closed, pts, width + 4)
    pygame.draw.lines(s, c, closed, pts, width)


def _ring(s, c, center, r, width=3):
    center = (int(center[0]), int(center[1]))
    pygame.draw.circle(s, scale(c, 0.4), center, int(r) + 2, width + 4)
    pygame.draw.circle(s, c, center, int(r), width)


def _dot(s, c, center, r):
    center = (int(center[0]), int(center[1]))
    pygame.draw.circle(s, scale(c, 0.45), center, int(r) + 3)
    pygame.draw.circle(s, mix(c, WHITE, 0.5), center, int(r))


def _poly(s, c, pts, fill=0.25):
    pygame.draw.polygon(s, scale(c, fill), pts)
    pygame.draw.polygon(s, c, pts, 2)


def _paint(item_id, s, c, n):
    m = n / 2
    if item_id == "pulse":
        for off in (-0.17, 0.0, 0.17):
            y = (0.5 + off) * n
            _stroke(s, c, [(0.24 * n, y + 0.06 * n), (0.7 * n, y - 0.06 * n)], 3)
            _dot(s, c, (0.72 * n, y - 0.06 * n), 3)
    elif item_id == "arc":
        _stroke(s, c, _arc_points(m - 0.08 * n, m, 0.3 * n, -1.9, 1.9), 4)
        _stroke(s, c, _arc_points(m - 0.08 * n, m, 0.19 * n, -1.4, 1.4), 2)
    elif item_id == "orbit":
        _ring(s, scale(c, 0.7), (m, m), 0.3 * n, 1)
        _dot(s, c, (m, m), 4)
        for k in range(3):
            a = k * TAU / 3 - 0.5
            _dot(s, c, (m + math.cos(a) * 0.3 * n, m + math.sin(a) * 0.3 * n), 4)
    elif item_id == "nova":
        _ring(s, c, (m, m), 0.16 * n, 2)
        for k in range(8):
            a = k * TAU / 8
            _stroke(s, c, [(m + math.cos(a) * 0.25 * n, m + math.sin(a) * 0.25 * n),
                           (m + math.cos(a) * 0.38 * n, m + math.sin(a) * 0.38 * n)], 2)
    elif item_id == "lance":
        cols = [(255, 90, 120), (255, 220, 90), (90, 230, 255)]
        for i, col in enumerate(cols):
            o = (i - 1) * 0.07 * n
            _stroke(s, col, [(0.18 * n + o, 0.82 * n + o), (0.82 * n + o, 0.18 * n + o)], 2)
        pygame.draw.line(s, WHITE, (0.2 * n, 0.8 * n), (0.8 * n, 0.2 * n), 2)
    elif item_id == "seeker":
        _stroke(s, scale(c, 0.8), _arc_points(0.2 * n, 0.95 * n, 0.55 * n, -1.4, -0.35, 10), 2)
        for (x, y, a) in ((0.62 * n, 0.32 * n, -0.6), (0.38 * n, 0.55 * n, -0.9)):
            _poly(s, c, transform(SHAPES["dart"], x, y, 0.13 * n, a), 0.5)
    elif item_id == "chain":
        _stroke(s, c, [(0.2 * n, 0.2 * n), (0.5 * n, 0.42 * n), (0.36 * n, 0.55 * n), (0.8 * n, 0.82 * n)], 3)
        for p in ((0.2 * n, 0.2 * n), (0.8 * n, 0.82 * n)):
            _dot(s, c, p, 4)
    elif item_id == "well":
        pts = []
        for i in range(60):
            a = i * 0.32
            r = 0.04 * n + i * 0.0058 * n
            pts.append((m + math.cos(a) * r, m + math.sin(a) * r))
        _stroke(s, c, pts, 2)
        _dot(s, (20, 20, 30), (m, m), 3)
    elif item_id == "mines":
        _poly(s, c, transform(SHAPES["spiky"], m, m, 0.3 * n, 0.2), 0.3)
        _dot(s, (255, 90, 90), (m, m), 4)
    elif item_id == "disc":
        _ring(s, c, (m + 0.06 * n, m), 0.2 * n, 4)
        for k in range(3):
            y = m + (k - 1) * 0.13 * n
            _stroke(s, scale(c, 0.8), [(0.12 * n, y), (0.3 * n, y)], 2)
    elif item_id == "overclock":
        _ring(s, c, (m, m), 0.3 * n, 3)
        _stroke(s, c, [(m, m), (m, m - 0.2 * n)], 3)
        _stroke(s, c, [(m, m), (m + 0.15 * n, m + 0.06 * n)], 3)
    elif item_id == "amplifier":
        for i in range(3):
            h = (0.18 + i * 0.14) * n
            x = (0.26 + i * 0.2) * n
            _poly(s, c, [(x, 0.8 * n), (x + 0.12 * n, 0.8 * n), (x + 0.12 * n, 0.8 * n - h), (x, 0.8 * n - h)], 0.35)
    elif item_id == "thrusters":
        _poly(s, c, [(m, 0.16 * n), (0.7 * n, 0.6 * n), (m, 0.86 * n), (0.3 * n, 0.6 * n)], 0.3)
        _poly(s, (255, 240, 160), [(m, 0.42 * n), (0.6 * n, 0.64 * n), (m, 0.78 * n), (0.4 * n, 0.64 * n)], 0.6)
    elif item_id == "plating":
        _poly(s, c, [(m, 0.14 * n), (0.8 * n, 0.26 * n), (0.74 * n, 0.62 * n), (m, 0.86 * n),
                     (0.26 * n, 0.62 * n), (0.2 * n, 0.26 * n)], 0.3)
        _stroke(s, c, [(m, 0.3 * n), (m, 0.7 * n)], 2)
    elif item_id == "magnetron":
        _stroke(s, c, _arc_points(m, 0.48 * n, 0.24 * n, 0, math.pi) + [], 5)
        for x in (m - 0.24 * n, m + 0.24 * n):
            _stroke(s, c, [(x, 0.48 * n), (x, 0.26 * n)], 5)
            pygame.draw.line(s, WHITE, (x - 5, 0.24 * n), (x + 5, 0.24 * n), 4)
    elif item_id == "multiplexer":
        for y in (0.38 * n, 0.62 * n):
            _stroke(s, c, [(0.2 * n, y), (0.72 * n, y)], 3)
            _stroke(s, c, [(0.6 * n, y - 0.09 * n), (0.74 * n, y), (0.6 * n, y + 0.09 * n)], 3)
    elif item_id == "lens":
        _ring(s, c, (m, m), 0.3 * n, 3)
        _ring(s, scale(c, 0.8), (m, m), 0.16 * n, 2)
        _dot(s, WHITE, (m - 0.12 * n, m - 0.12 * n), 2)
    elif item_id == "chrono":
        _poly(s, c, [(0.28 * n, 0.18 * n), (0.72 * n, 0.18 * n), (m, m)], 0.3)
        _poly(s, c, [(m, m), (0.72 * n, 0.82 * n), (0.28 * n, 0.82 * n)], 0.55)
    elif item_id == "nanoforge":
        _poly(s, c, transform(SHAPES["cross"], m, m, 0.3 * n, 0), 0.35)
    elif item_id == "fortune":
        _poly(s, c, transform(SHAPES["star"], m, m, 0.34 * n, math.pi / 4), 0.35)
        _dot(s, c, (m, m), 3)
    elif item_id == "rails":
        for y in (0.34 * n, 0.66 * n):
            _stroke(s, c, [(0.16 * n, y), (0.84 * n, y)], 2)
        _stroke(s, c, [(0.4 * n, 0.24 * n), (0.62 * n, m), (0.4 * n, 0.76 * n)], 3)
    elif item_id == "chest":
        _poly(s, c, [(0.18 * n, 0.4 * n), (0.82 * n, 0.4 * n), (0.82 * n, 0.8 * n), (0.18 * n, 0.8 * n)], 0.3)
        _poly(s, c, [(0.18 * n, 0.4 * n), (0.26 * n, 0.22 * n), (0.74 * n, 0.22 * n), (0.82 * n, 0.4 * n)], 0.45)
        _dot(s, WHITE, (m, 0.52 * n), 4)
    elif item_id == "flux":
        _poly(s, c, transform(SHAPES["hexagon"], m, m, 0.3 * n, math.pi / 6), 0.35)
        _poly(s, mix(c, WHITE, 0.4), transform(SHAPES["diamond"], m, m, 0.15 * n, math.pi / 2), 0.6)
    elif item_id in SHAPES:
        _poly(s, c, transform(SHAPES[item_id], m, m, 0.3 * n, 0), 0.25)
    else:
        _ring(s, c, (m, m), 0.25 * n, 3)


def icon(item_id, color, size=56, locked=False, evolved=False, frame=True):
    """A rounded tile with a vector pictogram for weapons, passives and upgrades."""
    key = (item_id, color, size, locked, evolved, frame)
    surf = _icons.get(key)
    if surf is not None:
        return surf
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    rad = max(4, size // 5)
    if frame:
        pygame.draw.rect(surf, (*DARK, 255), surf.get_rect(), border_radius=rad)
        pygame.draw.rect(surf, GOLD if evolved else scale(color, 0.55), surf.get_rect(), 3 if evolved else 2,
                         border_radius=rad)
    if locked:
        f = font(int(size * 0.7), True)
        q = f.render("?", True, (90, 90, 120))
        surf.blit(q, (size // 2 - q.get_width() // 2, size // 2 - q.get_height() // 2))
    else:
        _paint(item_id, surf, GOLD if evolved and item_id not in ("lance",) else color, size)
        if evolved:
            _dot(surf, WHITE, (size * 0.82, size * 0.18), 2)
    _icons[key] = surf
    return surf


def clear_caches():
    for c in (_glows, _sprites, _text, _icons):
        c.clear()
