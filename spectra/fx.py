"""Visual effects: camera shake, particles, shockwaves, beams, lightning, damage numbers,
the parallax background, bloom and vignette.

created by jullewz
"""

import math
import random

import pygame

from . import assets
from .config import HEIGHT, WHITE, WIDTH, YELLOW
from .util import TAU, clamp, mix, scale


# --------------------------------------------------------------------------- camera


class Camera:
    """Follows a point smoothly and shakes with "trauma" that decays over time."""

    def __init__(self, settings=None):
        self.x = 0.0
        self.y = 0.0
        self.trauma = 0.0
        self.t = 0.0
        self.ox = 0.0
        self.oy = 0.0
        self.cx = -WIDTH / 2
        self.cy = -HEIGHT / 2
        self.settings = settings

    def snap(self, x, y):
        self.x, self.y = x, y
        self._apply()

    def follow(self, x, y, dt):
        k = 1 - math.exp(-dt * 9)
        self.x += (x - self.x) * k
        self.y += (y - self.y) * k

    def shake(self, amount):
        self.trauma = min(1.0, self.trauma + amount)

    def update(self, dt):
        self.t += dt
        self.trauma = max(0.0, self.trauma - dt * 1.5)
        enabled = self.settings is None or self.settings.get("shake", True)
        s = (self.trauma ** 2) * 16 if enabled else 0.0
        self.ox = s * (math.sin(self.t * 61.3) + math.sin(self.t * 37.1) * 0.5)
        self.oy = s * (math.cos(self.t * 53.7) + math.sin(self.t * 29.3) * 0.5)
        self._apply()

    def _apply(self):
        self.cx = self.x - WIDTH / 2 - self.ox
        self.cy = self.y - HEIGHT / 2 - self.oy

    def on_screen(self, x, y, margin=60):
        sx, sy = x - self.cx, y - self.cy
        return -margin < sx < WIDTH + margin and -margin < sy < HEIGHT + margin


# --------------------------------------------------------------------------- particle effects


class FX:
    MAX_PARTICLES = 1400

    def __init__(self, settings=None):
        self.settings = settings or {}
        self.parts = []    # [x, y, vx, vy, life, max_life, size, color, kind, drag]
        self.rings = []    # [x, y, r0, r1, life, max_life, color, width]
        self.texts = []    # [x, y, vy, life, max_life, surface]
        self.beams = []    # [points, color, width, life, max_life]
        self.arcs = []     # [x, y, angle, span, r_in, r_out, color, life, max_life]
        self.flash = 0.0
        self.flash_color = WHITE
        self.rng = random.Random()

    # ---------------------------------------------------------------- emitters

    def sparks(self, x, y, color, n=8, speed=240, life=0.45, size=2, spread=TAU, angle=0.0, drag=3.5):
        if len(self.parts) > self.MAX_PARTICLES:
            n = min(n, 2)
        r = self.rng.random
        for _ in range(n):
            a = angle + (r() - 0.5) * spread
            s = speed * (0.35 + r() * 0.75)
            lf = life * (0.6 + r() * 0.6)
            self.parts.append([x, y, math.cos(a) * s, math.sin(a) * s, lf, lf, size, color, 0, drag])

    def dots(self, x, y, color, n=6, speed=90, life=0.7, size=3, drag=2.0):
        if len(self.parts) > self.MAX_PARTICLES:
            n = min(n, 1)
        r = self.rng.random
        for _ in range(n):
            a = r() * TAU
            s = speed * (0.2 + r() * 0.8)
            lf = life * (0.6 + r() * 0.6)
            self.parts.append([x, y, math.cos(a) * s, math.sin(a) * s, lf, lf, size * (0.6 + r() * 0.6), color, 1,
                               drag])

    def trail(self, x, y, color, size=3, life=0.3):
        if len(self.parts) < self.MAX_PARTICLES:
            self.parts.append([x, y, 0.0, 0.0, life, life, size, color, 1, 0.0])

    def burst(self, x, y, color, power=1.0):
        self.sparks(x, y, color, int(8 * power) + 2, 260 * min(2.0, 0.6 + power * 0.5), 0.45)
        self.dots(x, y, mix(color, WHITE, 0.3), int(4 * power) + 1, 110, 0.6, 3)

    def ring(self, x, y, color, r0=10, r1=80, life=0.35, width=3):
        self.rings.append([x, y, r0, r1, life, life, color, width])

    def number(self, x, y, value, crit=False):
        if not self.settings.get("numbers", True) or len(self.texts) > 120:
            return
        v = int(round(value))
        if v <= 0:
            return
        surf = assets.render(str(v), 30 if crit else 22, YELLOW if crit else WHITE, bold=crit)
        life = 0.7 if crit else 0.5
        self.texts.append([x + self.rng.uniform(-8, 8), y, -70.0, life, life, surf])

    def label(self, x, y, string, color, size=24, life=1.1):
        surf = assets.render(string, size, color, bold=True)
        self.texts.append([x, y, -45.0, life, life, surf])

    def beam(self, points, color, width=8, life=0.25):
        self.beams.append([points, color, width, life, life])

    def lightning(self, x0, y0, x1, y1, color, life=0.22, jitter=18):
        pts = [(x0, y0)]
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        n = max(2, int(dist / 22))
        nx, ny = (-dy / dist, dx / dist) if dist > 0 else (0, 0)
        for i in range(1, n):
            t = i / n
            off = self.rng.uniform(-jitter, jitter)
            pts.append((x0 + dx * t + nx * off, y0 + dy * t + ny * off))
        pts.append((x1, y1))
        self.beams.append([pts, color, 3, life, life])

    def arc(self, x, y, angle, span, r_in, r_out, color, life=0.22):
        self.arcs.append([x, y, angle, span, r_in, r_out, color, life, life])

    def screen_flash(self, amount=0.6, color=WHITE):
        self.flash = max(self.flash, amount)
        self.flash_color = color

    # ---------------------------------------------------------------- simulation

    def update(self, dt):
        alive = []
        for p in self.parts:
            p[4] -= dt
            if p[4] <= 0:
                continue
            k = math.exp(-p[9] * dt) if p[9] else 1.0
            p[2] *= k
            p[3] *= k
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            alive.append(p)
        self.parts = alive
        self.rings = [r for r in self.rings if self._tick(r, 4, dt)]
        self.beams = [b for b in self.beams if self._tick(b, 3, dt)]
        self.arcs = [a for a in self.arcs if self._tick(a, 7, dt)]
        texts = []
        for t in self.texts:
            t[3] -= dt
            if t[3] > 0:
                t[1] += t[2] * dt
                t[2] *= math.exp(-3 * dt)
                texts.append(t)
        self.texts = texts
        self.flash = max(0.0, self.flash - dt * 2.5)

    @staticmethod
    def _tick(item, idx, dt):
        item[idx] -= dt
        return item[idx] > 0

    # ---------------------------------------------------------------- drawing

    def draw_under(self, screen, cam):
        """Shockwave rings and slash arcs sit under the sprites."""
        cx, cy = cam.cx, cam.cy
        for x, y, r0, r1, life, mx, color, width in self.rings:
            t = 1 - life / mx
            r = r0 + (r1 - r0) * (1 - (1 - t) ** 2)
            c = scale(color, 0.25 + 0.75 * (life / mx))
            w = max(1, int(width * (life / mx) + 1))
            if r > w:
                pygame.draw.circle(screen, c, (int(x - cx), int(y - cy)), int(r), w)
        for x, y, ang, span, r_in, r_out, color, life, mx in self.arcs:
            k = life / mx
            grow = 0.75 + 0.25 * (1 - k)
            steps = 14
            outer, inner = [], []
            for i in range(steps + 1):
                a = ang - span / 2 + span * i / steps
                bulge = math.sin(math.pi * i / steps)
                ro = r_out * grow * (0.82 + 0.18 * bulge)
                ri = r_in * grow + (r_out - r_in) * 0.45 * (1 - bulge)
                outer.append((x - cx + math.cos(a) * ro, y - cy + math.sin(a) * ro))
                inner.append((x - cx + math.cos(a) * ri, y - cy + math.sin(a) * ri))
            pts = outer + inner[::-1]
            pygame.draw.polygon(screen, scale(color, 0.55 * k + 0.1), pts)
            pygame.draw.lines(screen, mix(color, WHITE, 0.5 * k), False, outer, 2)

    def draw_over(self, screen, cam):
        cx, cy = cam.cx, cam.cy
        line = pygame.draw.line
        circle = pygame.draw.circle
        for x, y, vx, vy, life, mx, size, color, kind, _ in self.parts:
            k = life / mx
            sx, sy = x - cx, y - cy
            if sx < -20 or sy < -20 or sx > WIDTH + 20 or sy > HEIGHT + 20:
                continue
            c = scale(color, 0.3 + 0.7 * k)
            if kind == 0:
                line(screen, c, (sx, sy), (sx - vx * 0.035, sy - vy * 0.035), max(1, int(size)))
            else:
                circle(screen, c, (int(sx), int(sy)), max(1, int(size * (0.4 + 0.6 * k))))
        for pts, color, width, life, mx in self.beams:
            k = life / mx
            sp = [(px - cx, py - cy) for px, py in pts]
            w = max(1, int(width * k))
            if len(sp) >= 2:
                pygame.draw.lines(screen, scale(color, 0.6 + 0.4 * k), False, sp, w + 4)
                pygame.draw.lines(screen, mix(color, WHITE, 0.75), False, sp, max(1, w // 2))
        for x, y, vy, life, mx, surf in self.texts:
            k = life / mx
            if k < 0.35:
                surf = surf.copy()
                surf.set_alpha(int(255 * k / 0.35))
            screen.blit(surf, (int(x - cx - surf.get_width() / 2), int(y - cy - surf.get_height() / 2)))


# --------------------------------------------------------------------------- background


class Background:
    """Parallax nebula + two star layers + a world-locked grid, all procedural."""

    TILE = 1024

    def __init__(self, stage, seed=1):
        self.stage = stage
        rng = random.Random(seed)
        self.tile = self._nebula_tile(stage, rng)
        self.stars = []
        for layer, (count, par, bright) in enumerate(((140, 0.35, 0.55), (70, 0.6, 0.9))):
            for _ in range(count):
                col = mix(stage.star, WHITE, rng.random())
                self.stars.append((rng.random() * 1600, rng.random() * 1000, par, scale(col, bright * rng.uniform(0.5, 1)),
                                   1 + (layer and rng.random() < 0.3)))
        self.pulse = 0.0

    def _nebula_tile(self, stage, rng):
        T = self.TILE
        surf = pygame.Surface((T, T))
        surf.fill(stage.base)
        for _ in range(9):
            col = rng.choice(stage.nebula)
            r = rng.randint(140, 330)
            x, y = rng.randint(0, T), rng.randint(0, T)
            g = assets.glow(r, col, rng.uniform(0.25, 0.5))
            for ox in (-T, 0, T):          # wrap so the tile is seamless
                for oy in (-T, 0, T):
                    surf.blit(g, (x - r + ox, y - r + oy), special_flags=pygame.BLEND_ADD)
        for _ in range(500):
            v = rng.randint(30, 90)
            surf.set_at((rng.randrange(T), rng.randrange(T)), mix(stage.base, (v, v, v + 20), 0.9))
        return surf

    def draw(self, screen, cam, boss=False):
        T = self.TILE
        px, py = cam.cx * 0.15, cam.cy * 0.15
        ox, oy = -int(px % T), -int(py % T)
        for x in range(ox, WIDTH, T):
            for y in range(oy, HEIGHT, T):
                screen.blit(self.tile, (x, y))
        for sx, sy, par, col, size in self.stars:
            x = (sx - cam.cx * par) % 1600 - 160
            y = (sy - cam.cy * par) % 1000 - 140
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                if size > 1:
                    pygame.draw.circle(screen, col, (int(x), int(y)), 2)
                else:
                    screen.set_at((int(x), int(y)), col)
        # grid
        self.pulse = self.pulse * 0.95 + (0.05 if boss else 0.0)
        g = 120
        minor = scale(self.stage.grid, 0.55 + self.pulse * 2)
        major = scale(self.stage.grid, 1.0 + self.pulse * 2)
        x0 = int(-(cam.cx % g))
        i0 = int(cam.cx // g)
        for k, x in enumerate(range(x0, WIDTH + 1, g)):
            pygame.draw.line(screen, major if (i0 + k) % 4 == 0 else minor, (x, 0), (x, HEIGHT), 1)
        y0 = int(-(cam.cy % g))
        j0 = int(cam.cy // g)
        for k, y in enumerate(range(y0, HEIGHT + 1, g)):
            pygame.draw.line(screen, major if (j0 + k) % 4 == 0 else minor, (0, y), (WIDTH, y), 1)


# --------------------------------------------------------------------------- post-processing


def _radial(color, inner, power, max_alpha):
    """A full-screen radial alpha mask, computed small and smoothly scaled up."""
    w, h = 160, 90
    small = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        for x in range(w):
            dx = (x + 0.5) / w * 2 - 1
            dy = (y + 0.5) / h * 2 - 1
            d = math.sqrt(dx * dx * 0.85 + dy * dy)
            a = clamp((d - inner) / (1.25 - inner), 0.0, 1.0) ** power * max_alpha
            small.set_at((x, y), (*color, int(a)))
    return pygame.transform.smoothscale(small, (WIDTH, HEIGHT))


class PostFX:
    def __init__(self):
        self.vignette = _radial((0, 0, 0), 0.45, 1.6, 200)
        self.hurt = _radial((255, 20, 50), 0.35, 1.4, 210)
        self.bloom_size = (WIDTH // 5, HEIGHT // 5)
        self.bloom_small = (WIDTH // 10, HEIGHT // 10)

    def bloom(self, screen, threshold=46, gain=170):
        """Cheap bloom: shrink, cut the dark parts, blur by scaling up and add back."""
        small = pygame.transform.smoothscale(screen, self.bloom_size)
        small.fill((threshold, threshold, threshold), special_flags=pygame.BLEND_SUB)
        tiny = pygame.transform.smoothscale(small, self.bloom_small)
        big = pygame.transform.smoothscale(tiny, (WIDTH, HEIGHT))
        big.fill((gain, gain, gain), special_flags=pygame.BLEND_MULT)
        screen.blit(big, (0, 0), special_flags=pygame.BLEND_ADD)
        mid = pygame.transform.smoothscale(small, (WIDTH, HEIGHT))
        mid.fill((gain // 2, gain // 2, gain // 2), special_flags=pygame.BLEND_MULT)
        screen.blit(mid, (0, 0), special_flags=pygame.BLEND_ADD)

    def draw_vignette(self, screen):
        screen.blit(self.vignette, (0, 0))

    def draw_hurt(self, screen, amount):
        if amount <= 0.01:
            return
        self.hurt.set_alpha(int(255 * clamp(amount, 0, 1)))
        screen.blit(self.hurt, (0, 0))

    @staticmethod
    def flash(screen, amount, color):
        if amount <= 0.01:
            return
        v = scale(color, clamp(amount, 0, 1) * 0.8)
        screen.fill(v, special_flags=pygame.BLEND_ADD)
