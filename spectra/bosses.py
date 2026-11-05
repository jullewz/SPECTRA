"""The four bosses: Hive Queen (3:00), Prism Colossus (6:00), Serpent (9:00) and the
Singularity (12:00), whose destruction wins the run.

created by jullewz
"""

import math

import pygame

from . import assets
from .config import GOLD, GREEN, ORANGE, PURPLE, RAINBOW, TEAL, WHITE
from .entities import ENEMY_TYPES, Enemy, EnemyType, Laser
from .util import TAU, mix, scale, wrap_angle


class Boss(Enemy):
    boss_id = ""
    title = ""
    subtitle = ""
    shape = "hexagon"
    color = GOLD
    size = 46
    base_hp = 2600
    move_speed = 60
    base_damage = 20

    def __init__(self, world, x, y, hp_scale=1.0, dmg_scale=1.0):
        et = EnemyType(self.boss_id, self.title, self.subtitle, self.shape, self.color, self.size, self.base_hp,
                       self.move_speed, self.base_damage, 0, "boss", 60.0, True)
        super().__init__(world, et, x, y, hp_scale, dmg_scale)
        self.boss = True
        self.speed = self.move_speed
        self.mass = 60.0
        self.attack = 2.5
        self.attack2 = 4.0
        self.attack3 = 6.0
        self.spin = 0.0

    @property
    def enraged(self):
        return self.hp < self.max_hp * 0.5

    def move(self, world, dt, keep=220, speed=None):
        p = world.player
        dx, dy = p.x - self.x, p.y - self.y
        d = math.hypot(dx, dy) or 1e-6
        ux, uy = dx / d, dy / d
        spd = self.speed if speed is None else speed
        if d > 1050:   # never let the player simply outrun a boss
            self.x, self.y = world.director.spawn_point(640)
            return ux, uy, d
        if d > 520:
            spd *= 1 + (d - 520) / 180
        if self.slow > 0:
            self.slow -= dt
            spd *= 0.6
        if d > keep:
            vx, vy = ux * spd, uy * spd
        else:
            vx, vy = -uy * spd * 0.55, ux * spd * 0.55
        self.x += (vx + self.kx) * dt
        self.y += (vy + self.ky) * dt
        self.kx *= 0.9
        self.ky *= 0.9
        return ux, uy, d

    def ring(self, world, n, speed, offset=0.0, radius=8, color=None, damage=None):
        for i in range(n):
            a = offset + i * TAU / n
            world.enemy_shot(self.x + math.cos(a) * self.radius, self.y + math.sin(a) * self.radius,
                             math.cos(a) * speed, math.sin(a) * speed, radius, damage or self.damage * 0.7,
                             color or self.color)

    def tick(self, dt):
        self.t += dt
        if self.flash > 0:
            self.flash -= dt

    def draw_glow(self, screen, cam):
        pass

    def body(self, screen, cam, shape=None, angle=None, size=None, color=None):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        spr = assets.shape_sprite(shape or self.shape, size or self.radius, color or self.color,
                                  self.angle if angle is None else angle, self.flash > 0)
        assets.blit_center(screen, spr, sx, sy)
        return sx, sy


# --------------------------------------------------------------------------- hive queen


class HiveQueen(Boss):
    boss_id = "queen"
    title = "HIVE QUEEN"
    subtitle = "Mother of the swarm"
    shape = "hexagon"
    color = (255, 170, 60)
    size = 46
    base_hp = 1500
    move_speed = 62
    base_damage = 20

    def update(self, world, dt):
        self.tick(dt)
        self.spin += dt * (2.2 if self.enraged else 1.2)
        self.angle = self.spin * 0.4
        self.move(world, dt, 160)
        self.attack -= dt
        self.attack2 -= dt
        if self.attack <= 0:
            self.attack = 1.7 if self.enraged else 2.6
            self.ring(world, 20 if self.enraged else 14, 185, offset=self.t)
            world.sfx("shoot", 0.7)
        if self.attack2 <= 0:
            self.attack2 = 5.5
            for i in range(6):
                a = i * TAU / 6 + self.spin
                world.spawn_enemy("drone", self.x + math.cos(a) * 95, self.y + math.sin(a) * 95)
            if self.enraged:
                for i in range(5):
                    m = world.spawn_enemy("mite", self.x, self.y)
                    if m:
                        p = world.player
                        d = math.hypot(p.x - self.x, p.y - self.y) or 1
                        m.dirx, m.diry = (p.x - self.x) / d, (p.y - self.y) / d
                        m.timer = 1.5
            world.fx.ring(self.x, self.y, self.color, 20, 130, 0.45, 4)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        pulse = 0.55 + 0.15 * math.sin(self.t * 5)
        assets.blit_glow(screen, sx, sy, self.radius * 3.2, self.color, pulse)
        for k in range(6):
            a = self.spin + k * TAU / 6
            ox, oy = sx + math.cos(a) * self.radius * 1.6, sy + math.sin(a) * self.radius * 1.6
            pygame.draw.line(screen, scale(self.color, 0.5), (sx, sy), (ox, oy), 2)
            assets.blit_center(screen, assets.orb_sprite(9, (255, 90, 200)), ox, oy)
        self.body(screen, cam)
        self.body(screen, cam, "hexagon", -self.spin, int(self.radius * 0.55), (255, 90, 200))


# --------------------------------------------------------------------------- prism colossus


class PrismColossus(Boss):
    boss_id = "colossus"
    title = "PRISM COLOSSUS"
    subtitle = "It bends light into blades"
    shape = "triangle"
    color = (160, 120, 255)
    size = 56
    base_hp = 4000
    move_speed = 46
    base_damage = 24

    def __init__(self, world, x, y, hp_scale=1.0, dmg_scale=1.0):
        super().__init__(world, x, y, hp_scale, dmg_scale)
        self.mode = "rest"
        self.mode_t = 2.0
        self.next_mode = "lasers"
        self.emit = 0.0

    def update(self, world, dt):
        self.tick(dt)
        self.angle += dt * (1.3 if self.enraged else 0.7)
        self.move(world, dt, 220)
        self.mode_t -= dt
        p = world.player
        if self.mode == "rest":
            if self.mode_t <= 0:
                self.mode = self.next_mode
                self.next_mode = "spiral" if self.mode == "lasers" else "lasers"
                self.mode_t = 3.2
        elif self.mode == "lasers":
            n = 5 if self.enraged else 3
            base = math.atan2(p.y - self.y, p.x - self.x)
            direction = 1 if world.rng.random() < 0.5 else -1
            for i in range(n):
                world.hazards.append(Laser(self, base + i * TAU / n, 1500, 30, 1.0, 0.9, self.damage * 1.3,
                                           0.45 * direction * (1.5 if self.enraged else 1.0),
                                           RAINBOW[i % len(RAINBOW)]))
            world.sfx("warn", 0.8)
            self.mode, self.mode_t = "rest", 2.6
        elif self.mode == "spiral":
            self.emit -= dt
            arms = 3 if self.enraged else 2
            while self.emit <= 0:
                self.emit += 0.075
                for k in range(arms):
                    a = self.t * 2.1 + k * TAU / arms
                    world.enemy_shot(self.x, self.y, math.cos(a) * 175, math.sin(a) * 175, 7, self.damage * 0.6,
                                     RAINBOW[int(self.t * 6) % len(RAINBOW)])
            if self.mode_t <= 0:
                self.mode, self.mode_t = "rest", 1.6

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        assets.blit_glow(screen, sx, sy, self.radius * 3.0, self.color, 0.55)
        self.body(screen, cam)
        self.body(screen, cam, "triangle", -self.angle * 1.7, int(self.radius * 0.5), WHITE)
        for i in range(3):
            a = self.angle + i * TAU / 3
            vx, vy = sx + math.cos(a) * self.radius, sy + math.sin(a) * self.radius
            assets.blit_glow(screen, vx, vy, 26, RAINBOW[(i * 2 + int(self.t * 3)) % len(RAINBOW)], 0.9)


# --------------------------------------------------------------------------- serpent


class Segment(Enemy):
    def __init__(self, world, owner, radius, index):
        super().__init__(world, ENEMY_TYPES["segment"], owner.x, owner.y)
        self.owner = owner
        self.radius = radius
        self.index = index
        self.max_hp = self.hp = 1
        self.damage = owner.damage * 0.75
        self.mass = 99.0
        self.color = mix(GREEN, TEAL, index / 16)

    def update(self, world, dt):
        self.t += dt
        if self.flash > 0:
            self.flash -= dt

    def draw_glow(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        assets.blit_glow(screen, sx, sy, self.radius * 2.2, self.color, 0.4)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if not cam.on_screen(self.x, self.y, 60):
            return
        flash = self.flash > 0 or self.owner.flash > 0
        spr = assets.shape_sprite("octagon", self.radius, self.color, self.angle, flash)
        assets.blit_center(screen, spr, sx, sy)


class Serpent(Boss):
    boss_id = "serpent"
    title = "THE SERPENT"
    subtitle = "Sixteen segments, one appetite"
    shape = "pentagon"
    color = GREEN
    size = 30
    base_hp = 8500
    move_speed = 175
    base_damage = 26
    SEGMENTS = 16
    SPACING = 7       # path points between segments (points are ~4 px apart)

    def __init__(self, world, x, y, hp_scale=1.0, dmg_scale=1.0):
        super().__init__(world, x, y, hp_scale, dmg_scale)
        self.heading = math.atan2(world.player.y - y, world.player.x - x)
        self.path = [(x, y)]
        self.segments = []
        for i in range(self.SEGMENTS):
            seg = Segment(world, self, int(24 - i * 0.6), i)
            self.segments.append(seg)
            world.enemies.append(seg)

    def update(self, world, dt):
        self.tick(dt)
        p = world.player
        want = math.atan2(p.y - self.y, p.x - self.x) + math.sin(self.t * 2.4) * 0.7
        turn = (2.6 if self.enraged else 1.8) * dt
        self.heading += max(-turn, min(turn, wrap_angle(want - self.heading)))
        spd = self.speed * (1.3 if self.enraged else 1.0) * (0.6 if self.slow > 0 else 1.0)
        far = math.hypot(p.x - self.x, p.y - self.y)
        if far > 600:
            spd *= 1 + (far - 600) / 250
        if self.slow > 0:
            self.slow -= dt
        self.x += math.cos(self.heading) * spd * dt
        self.y += math.sin(self.heading) * spd * dt
        self.angle = self.heading
        lx, ly = self.path[-1]
        while (self.x - lx) ** 2 + (self.y - ly) ** 2 >= 16:
            d = math.hypot(self.x - lx, self.y - ly)
            lx, ly = lx + (self.x - lx) / d * 4, ly + (self.y - ly) / d * 4
            self.path.append((lx, ly))
        keep = (self.SEGMENTS + 2) * self.SPACING
        if len(self.path) > keep:
            del self.path[: len(self.path) - keep]
        for i, seg in enumerate(self.segments):
            idx = max(0, len(self.path) - 1 - (i + 1) * self.SPACING)
            nx, ny = self.path[idx]
            seg.angle = math.atan2(ny - seg.y, nx - seg.x) if (nx, ny) != (seg.x, seg.y) else seg.angle
            seg.x, seg.y = nx, ny
        self.attack -= dt
        if self.attack <= 0:
            self.attack = 1.7 if self.enraged else 2.8
            for seg in world.rng.sample(self.segments, 5):
                d = math.hypot(p.x - seg.x, p.y - seg.y) or 1
                world.enemy_shot(seg.x, seg.y, (p.x - seg.x) / d * 210, (p.y - seg.y) / d * 210, 7,
                                 self.damage * 0.6, TEAL)
            world.sfx("shoot", 0.6)

    def on_death(self, world):
        for seg in self.segments:
            seg.alive = False
            world.fx.burst(seg.x, seg.y, seg.color, 1.0)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        assets.blit_glow(screen, sx, sy, self.radius * 3.4, self.color, 0.6)
        self.body(screen, cam)
        for side in (-1, 1):
            a = self.heading + side * 0.55
            ex, ey = sx + math.cos(a) * self.radius * 0.6, sy + math.sin(a) * self.radius * 0.6
            pygame.draw.circle(screen, (255, 60, 80), (int(ex), int(ey)), 5)
            pygame.draw.circle(screen, WHITE, (int(ex), int(ey)), 2)


# --------------------------------------------------------------------------- singularity


class Singularity(Boss):
    boss_id = "singularity"
    title = "THE SINGULARITY"
    subtitle = "Everything falls in"
    shape = "circle"
    color = (180, 90, 255)
    size = 62
    base_hp = 11000
    move_speed = 38
    base_damage = 28

    def __init__(self, world, x, y, hp_scale=1.0, dmg_scale=1.0):
        super().__init__(world, x, y, hp_scale, dmg_scale)
        self.fire_t = 1.0
        self.attack = 6.0
        self.attack2 = 9.0
        self.attack3 = 6.0

    def update(self, world, dt):
        self.tick(dt)
        ux, uy, d = self.move(world, dt, 0)
        p = world.player
        if d < 900 and not world.dead:
            f = 80 * (1 - d / 900)
            p.x -= ux * f * dt
            p.y -= uy * f * dt
        self.fire_t -= dt
        arms = 5 if self.enraged else 3
        while self.fire_t <= 0:
            self.fire_t += 0.12
            for k in range(arms):
                a = self.t * 1.25 + k * TAU / arms
                world.enemy_shot(self.x + math.cos(a) * self.radius, self.y + math.sin(a) * self.radius,
                                 math.cos(a) * 165, math.sin(a) * 165, 7, self.damage * 0.55, ORANGE)
        self.attack -= dt
        if self.attack <= 0:
            self.attack = 7.0
            for i in range(12):
                a = i * TAU / 12
                world.spawn_enemy("weaver" if i % 2 else "drone", p.x + math.cos(a) * 430, p.y + math.sin(a) * 430)
        self.attack2 -= dt
        if self.attack2 <= 0:
            self.attack2 = 9.0
            self.ring(world, 30, 230, self.t, 8, PURPLE)
            world.camera.shake(0.2)
            world.sfx("explode", 0.8)
        if self.hp < self.max_hp * 0.3:
            self.attack3 -= dt
            if self.attack3 <= 0:
                self.attack3 = 6.0
                base = world.rng.random() * TAU
                for i in range(4):
                    world.hazards.append(Laser(self, base + i * TAU / 4, 1500, 26, 1.1, 1.4, self.damage, 0.5,
                                               (255, 120, 60)))
                world.sfx("warn")

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        r = self.radius
        assets.blit_glow(screen, sx, sy, r * 4.2, self.color, 0.6)
        assets.blit_glow(screen, sx, sy, r * 2.2, ORANGE, 0.35)
        back, front = [], []
        for i in range(36):
            a = self.t * 1.6 + i * TAU / 36
            rr = r * (1.45 + 0.12 * math.sin(i * 1.7 + self.t * 3))
            x, y = sx + math.cos(a) * rr, sy + math.sin(a) * rr * 0.42
            (front if math.sin(a) > 0 else back).append((x, y, mix(ORANGE, self.color, i / 36)))
        for x, y, c in back:
            pygame.draw.circle(screen, c, (int(x), int(y)), 4)
        pygame.draw.circle(screen, (0, 0, 0), (int(sx), int(sy)), int(r))
        pygame.draw.circle(screen, WHITE if self.flash > 0 else mix(self.color, WHITE, 0.4), (int(sx), int(sy)),
                           int(r * 1.04), 3)
        for x, y, c in front:
            pygame.draw.circle(screen, mix(c, WHITE, 0.3), (int(x), int(y)), 5)


BOSSES = {cls.boss_id: cls for cls in (HiveQueen, PrismColossus, Serpent, Singularity)}
