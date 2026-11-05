"""The things that live in the world: the player ship, enemies, projectiles, enemy
bullets, boss lasers, gravity wells and pickups.

created by jullewz
"""

import math
from dataclasses import dataclass

import pygame

from . import assets
from .config import (BASE_MAGNET, BLUE, CYAN, GEM_TIERS, GOLD, GREEN, HEIGHT, LIME, MAGENTA, ORANGE, PINK,
                     PLAYER_RADIUS, PURPLE, RED, TEAL, WHITE, WIDTH, YELLOW)
from .data import PASSIVE_BY_ID
from .util import TAU, mix, normalize, point_segment_dist2, scale, wrap_angle


def xp_needed(level):
    n = level - 1
    return int(4 + n * 5 + n ** 2.1 * 0.5)


def on_screen(sx, sy, margin=60):
    return -margin < sx < WIDTH + margin and -margin < sy < HEIGHT + margin


# --------------------------------------------------------------------------- player


class Player:
    def __init__(self, world, char, meta):
        self.world = world
        self.char = char
        self.meta = dict(meta)
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.angle = -math.pi / 2
        self.facing = (1.0, 0.0)
        self.radius = PLAYER_RADIUS
        self.level = 1
        self.xp = 0.0
        self.xp_next = xp_needed(1)
        self.weapons = []
        self.passives = {}
        self.iframes = 0.0
        self.hurt = 0.0
        self.rerolls = int(self.meta.get("rerolls", 0))
        self.revives = int(self.meta.get("revives", 0))
        self.trail_t = 0.0
        self.max_hp = 0
        self.recompute()
        self.hp = self.max_hp

    # ---------------------------------------------------------------- stats

    def mods(self):
        m = dict(self.meta)
        for pid, lvl in self.passives.items():
            for k, v in PASSIVE_BY_ID[pid].effect.items():
                m[k] = m.get(k, 0) + v * lvl
        return m

    def recompute(self):
        c = self.char
        m = self.mods()
        old = self.max_hp
        self.max_hp = c.hp * (1 + m.get("max_hp_pct", 0)) + m.get("max_hp_flat", 0)
        if old:
            self.hp = min(self.max_hp, self.hp + max(0, self.max_hp - old))
        self.might = c.might + m.get("might", 0)
        self.cooldown = max(0.35, c.cooldown * (1 + m.get("cooldown", 0)))
        self.speed = 205 * c.speed * (1 + m.get("speed", 0))
        self.magnet = BASE_MAGNET * c.magnet * (1 + m.get("magnet", 0))
        self.armor = c.armor + m.get("armor", 0)
        self.regen = c.regen + m.get("regen", 0)
        self.amount = int(m.get("amount", 0))
        self.area = c.area + m.get("area", 0)
        self.duration = 1 + m.get("duration", 0)
        self.luck = c.luck + m.get("luck", 0)
        self.crit = 0.05 + c.crit + m.get("crit", 0)
        self.proj_speed = 1 + m.get("proj_speed", 0)
        self.growth = c.growth + m.get("growth", 0)
        self.greed = 1 + m.get("greed", 0)

    def stat_lines(self):
        """Readable stat sheet for the pause menu."""
        return [
            ("Health", f"{int(self.hp)} / {int(self.max_hp)}"),
            ("Damage", f"{self.might * 100:.0f}%"),
            ("Cooldown", f"{self.cooldown * 100:.0f}%"),
            ("Area", f"{self.area * 100:.0f}%"),
            ("Duration", f"{self.duration * 100:.0f}%"),
            ("Projectiles", f"+{self.amount}"),
            ("Speed", f"{self.speed / 205 * 100:.0f}%"),
            ("Pickup range", f"{self.magnet / BASE_MAGNET * 100:.0f}%"),
            ("Armor", f"{self.armor:g}"),
            ("Regen", f"{self.regen:.2f}/s"),
            ("Critical", f"{self.crit * 100:.0f}%"),
            ("Luck", f"{self.luck * 100:.0f}%"),
            ("Experience", f"{self.growth * 100:.0f}%"),
            ("Revives", f"{self.revives}"),
        ]

    # ---------------------------------------------------------------- simulation

    def weapon(self, wid):
        for w in self.weapons:
            if w.id == wid:
                return w
        return None

    def heal(self, amount):
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def add_xp(self, amount):
        self.xp += amount * self.growth
        while self.xp >= self.xp_next:
            self.xp -= self.xp_next
            self.level += 1
            self.xp_next = xp_needed(self.level)
            self.world.on_level_up()

    def update(self, dt, mx, my):
        k = 1 - math.exp(-dt * 14)
        self.vx += (mx * self.speed - self.vx) * k
        self.vy += (my * self.speed - self.vy) * k
        self.x += self.vx * dt
        self.y += self.vy * dt
        if mx or my:
            self.facing = normalize(mx, my)
            target = math.atan2(my, mx)
            diff = wrap_angle(target - self.angle)
            self.angle += diff * min(1.0, dt * 14)
        self.iframes = max(0.0, self.iframes - dt)
        self.hurt = max(0.0, self.hurt - dt)
        if self.regen > 0 and self.hp < self.max_hp:
            self.hp = min(self.max_hp, self.hp + self.regen * dt)
        self.trail_t -= dt
        if self.trail_t <= 0:
            self.trail_t = 0.025
            bx = self.x - math.cos(self.angle) * 13
            by = self.y - math.sin(self.angle) * 13
            moving = abs(self.vx) + abs(self.vy) > 20
            self.world.fx.trail(bx, by, mix(self.char.color, WHITE, 0.3) if moving else scale(self.char.color, 0.6),
                                3.2 if moving else 2.0, 0.32 if moving else 0.18)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        col = self.char.color
        blink = self.iframes > 0 and int(self.iframes * 20) % 2 == 0
        assets.blit_glow(screen, sx, sy, 46, col, 0.55)
        # magnet radius hint
        pygame.draw.circle(screen, scale(col, 0.16), (int(sx), int(sy)), int(self.magnet), 1)
        spr = assets.shape_sprite("ship", 17, col, self.angle, flash=blink or self.hurt > 0.2)
        assets.blit_center(screen, spr, sx, sy)
        if self.iframes > 0.6:
            pygame.draw.circle(screen, mix(col, WHITE, 0.5), (int(sx), int(sy)), 26, 2)


# --------------------------------------------------------------------------- enemies


@dataclass(frozen=True)
class EnemyType:
    id: str
    name: str
    desc: str
    shape: str
    color: tuple
    radius: int
    hp: float
    speed: float
    damage: float
    xp: int
    behavior: str
    mass: float = 1.0
    spin: bool = False


AMBER = (255, 178, 64)
EMBER = (255, 96, 52)
LILAC = (205, 150, 255)

ENEMY_TYPES = {
    "drone": EnemyType("drone", "Drone", "A cheap hunter-killer. It arrives by the thousand.", "triangle", MAGENTA,
                       13, 9, 78, 7, 1, "chase"),
    "dart": EnemyType("dart", "Dart", "A fast interceptor that dives straight at you.", "dart", AMBER,
                      11, 7, 150, 6, 1, "chase", 0.7),
    "mite": EnemyType("mite", "Mite", "Tiny, quick, and always in a stream.", "shard", PINK,
                      9, 4, 128, 4, 1, "stream", 0.5),
    "weaver": EnemyType("weaver", "Weaver", "Slithers left and right so your shots miss.", "star", LIME,
                        14, 16, 96, 8, 2, "weave", 1.0, True),
    "brute": EnemyType("brute", "Brute", "Slow, armored and very hard to push around.", "hexagon", RED,
                       24, 80, 52, 16, 6, "chase", 4.0, True),
    "splitter": EnemyType("splitter", "Splitter", "Breaks into two shardlings when destroyed.", "diamond", PURPLE,
                          18, 32, 66, 9, 3, "chase", 1.6),
    "shardling": EnemyType("shardling", "Shardling", "What is left of a splitter. Still angry.", "diamond", LILAC,
                           10, 8, 118, 5, 1, "chase", 0.6),
    "spitter": EnemyType("spitter", "Spitter", "Keeps its distance and lobs plasma at you.", "square", YELLOW,
                         15, 24, 62, 8, 3, "ranged", 1.2, True),
    "charger": EnemyType("charger", "Charger", "Locks on, flashes, then dashes in a straight line.", "chevron", EMBER,
                         16, 40, 70, 13, 4, "charge", 2.0),
    "bomber": EnemyType("bomber", "Bomber", "Rushes in and detonates. Keep moving.", "spiky", ORANGE,
                        15, 20, 98, 24, 3, "bomber", 1.0, True),
    "warden": EnemyType("warden", "Warden", "Mends nearby enemies with a healing pulse.", "cross", TEAL,
                        22, 110, 46, 10, 8, "healer", 3.0, True),
    "segment": EnemyType("segment", "Serpent Segment", "", "octagon", GREEN, 22, 1, 0, 14, 0, "segment", 99.0, True),
}

CODEX_ENEMIES = ["drone", "dart", "mite", "weaver", "brute", "splitter", "shardling", "spitter", "charger",
                 "bomber", "warden"]


class Enemy:
    _uid = 0

    def __init__(self, world, etype, x, y, hp_scale=1.0, dmg_scale=1.0, elite=False):
        Enemy._uid += 1
        self.uid = Enemy._uid
        self.type = etype
        self.kind = etype.id
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.kx = self.ky = 0.0
        self.elite = elite
        self.radius = etype.radius * (1.4 if elite else 1.0)
        self.max_hp = etype.hp * hp_scale * (9 if elite else 1)
        self.hp = self.max_hp
        self.speed = etype.speed * (0.92 if elite else 1.0) * world.rng.uniform(0.92, 1.08)
        self.damage = etype.damage * dmg_scale * (1.4 if elite else 1.0)
        self.xp = etype.xp * (12 if elite else 1)
        self.mass = etype.mass * (4 if elite else 1)
        self.color = etype.color
        self.angle = world.rng.random() * TAU
        self.flash = 0.0
        self.alive = True
        self.t = world.rng.random() * 5
        self.state = 0
        self.timer = world.rng.uniform(0.8, 2.4)
        self.slow = 0.0
        self.owner = None
        self.boss = False
        self.dirx = self.diry = 0.0
        self.hit_by = None

    # ---------------------------------------------------------------- behavior

    def update(self, world, dt):
        self.t += dt
        if self.flash > 0:
            self.flash -= dt
        p = world.player
        dx, dy = p.x - self.x, p.y - self.y
        d = math.hypot(dx, dy) or 1e-6
        ux, uy = dx / d, dy / d
        spd = self.speed
        if self.slow > 0:
            self.slow -= dt
            spd *= 0.4
        vx, vy = ux * spd, uy * spd
        b = self.type.behavior
        if b == "weave":
            w = math.sin(self.t * 3.1 + self.uid) * 0.95
            vx += -uy * spd * w
            vy += ux * spd * w
        elif b == "stream":
            if self.state == 0:
                vx, vy = self.dirx * spd * 1.2, self.diry * spd * 1.2
                self.timer -= dt
                if self.timer <= 0:
                    self.state = 1
        elif b == "ranged":
            if d < 230:
                vx, vy = -ux * spd, -uy * spd
            elif d < 340:
                side = 1 if self.uid % 2 else -1
                vx, vy = -uy * spd * 0.6 * side, ux * spd * 0.6 * side
            self.timer -= dt
            if self.timer <= 0 and d < 560:
                self.timer = world.rng.uniform(2.4, 3.3)
                world.enemy_shot(self.x + ux * self.radius, self.y + uy * self.radius, ux * 235, uy * 235, 7,
                                 self.damage * 1.1, self.color)
        elif b == "charge":
            if self.state == 0:
                self.timer -= dt
                if d < 360 and self.timer <= 0:
                    self.state, self.timer = 1, 0.7
                    self.dirx, self.diry = ux, uy
            elif self.state == 1:
                vx = vy = 0.0
                self.timer -= dt
                self.angle = math.atan2(self.diry, self.dirx)
                if self.timer <= 0:
                    self.state, self.timer = 2, 0.5
                    world.sfx("whoosh", 0.5)
            else:
                vx, vy = self.dirx * spd * 6.2, self.diry * spd * 6.2
                self.timer -= dt
                if world.rng.random() < 0.5:
                    world.fx.trail(self.x, self.y, self.color, 4, 0.25)
                if self.timer <= 0:
                    self.state, self.timer = 0, world.rng.uniform(2.0, 2.8)
        elif b == "bomber":
            if self.state == 0 and d < 66:
                self.state, self.timer = 1, 0.55
            if self.state == 1:
                vx *= 0.2
                vy *= 0.2
                self.timer -= dt
                if self.timer <= 0:
                    world.detonate(self)
                    return
        elif b == "healer":
            if d < 210:
                vx, vy = -ux * spd * 0.6, -uy * spd * 0.6
            self.timer -= dt
            if self.timer <= 0:
                self.timer = 3.6
                world.heal_pulse(self)
        self.vx, self.vy = vx, vy
        self.x += (vx + self.kx) * dt
        self.y += (vy + self.ky) * dt
        if self.kx or self.ky:
            k = math.exp(-dt * 7)
            self.kx *= k
            self.ky *= k
            if abs(self.kx) + abs(self.ky) < 2:
                self.kx = self.ky = 0.0
        if self.type.spin:
            self.angle += dt * (1.6 if self.kind != "brute" else 0.7)
        elif b != "charge" or self.state != 1:
            self.angle = math.atan2(vy, vx)

    # ---------------------------------------------------------------- drawing

    def draw_glow(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if on_screen(sx, sy, self.radius * 2):
            assets.blit_glow(screen, sx, sy, self.radius * (2.6 if self.elite else 1.9),
                             GOLD if self.elite else self.color, 0.7 if self.elite else 0.42)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if not on_screen(sx, sy, self.radius * 2):
            return
        warn = self.state == 1 and self.type.behavior in ("charge", "bomber") and int(self.t * 14) % 2 == 0
        spr = assets.shape_sprite(self.type.shape, self.radius, self.color, self.angle, self.flash > 0 or warn,
                                  self.elite)
        assets.blit_center(screen, spr, sx, sy)
        if self.type.behavior == "charge" and self.state == 1:
            ex, ey = sx + self.dirx * 260, sy + self.diry * 260
            pygame.draw.line(screen, scale(self.color, 0.55), (sx, sy), (ex, ey), 2)
        if self.type.behavior == "bomber" and self.state == 1:
            pygame.draw.circle(screen, scale(ORANGE, 0.7), (int(sx), int(sy)), 80, 1)
        if (self.elite or self.max_hp >= 60) and self.hp < self.max_hp:
            w = int(self.radius * 2)
            x0, y0 = int(sx - w / 2), int(sy - self.radius - 10)
            pygame.draw.rect(screen, (20, 10, 20), (x0, y0, w, 4))
            pygame.draw.rect(screen, GOLD if self.elite else RED, (x0, y0, int(w * max(0, self.hp) / self.max_hp), 4))


# --------------------------------------------------------------------------- player projectiles


class Projectile:
    __slots__ = ("weapon", "x", "y", "vx", "vy", "radius", "damage", "pierce", "life", "color", "hit", "alive",
                 "knock", "age")

    def __init__(self, weapon, x, y, vx, vy, radius, damage, pierce=1, life=1.5, color=CYAN, knock=90):
        self.weapon = weapon
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.radius = radius
        self.damage = damage
        self.pierce = pierce
        self.life = life
        self.color = color
        self.hit = set()
        self.alive = True
        self.knock = knock
        self.age = 0.0

    def update(self, world, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            self.on_expire(world)
            return
        self.collide(world)

    def collide(self, world):
        r = self.radius
        for e in world.grid.query(self.x, self.y, r + 48):
            if not e.alive or e.uid in self.hit:
                continue
            rr = r + e.radius
            dx, dy = e.x - self.x, e.y - self.y
            if dx * dx + dy * dy < rr * rr:
                self.hit.add(e.uid)
                self.on_hit(world, e)
                self.pierce -= 1
                if self.pierce <= 0:
                    self.alive = False
                    self.on_expire(world)
                    return

    def on_hit(self, world, e):
        nx, ny = normalize(self.vx, self.vy)
        world.damage_enemy(e, self.damage, self.weapon, nx * self.knock, ny * self.knock)
        world.fx.sparks(self.x, self.y, self.color, 3, 220, 0.25, angle=math.atan2(-self.vy, -self.vx), spread=1.8)

    def on_expire(self, world):
        pass

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if not on_screen(sx, sy):
            return
        assets.blit_glow(screen, sx, sy, self.radius * 3.2, self.color, 0.6)
        tail = 0.028
        w = int(self.radius * 1.4) + 1
        pygame.draw.line(screen, self.color, (sx, sy), (sx - self.vx * tail, sy - self.vy * tail), w)
        pygame.draw.line(screen, WHITE, (sx, sy), (sx - self.vx * tail * 0.6, sy - self.vy * tail * 0.6),
                         max(1, w // 2))


class Missile(Projectile):
    __slots__ = ("target", "turn", "aoe", "speed", "retarget")

    def __init__(self, weapon, x, y, angle, speed, damage, aoe, color, life=3.0):
        super().__init__(weapon, x, y, math.cos(angle) * speed, math.sin(angle) * speed, 6, damage, 1, life, color, 60)
        self.target = None
        self.turn = 5.5
        self.aoe = aoe
        self.speed = speed
        self.retarget = 0.0

    def update(self, world, dt):
        self.retarget -= dt
        if self.target is None or not self.target.alive or self.retarget <= 0:
            self.target = (world.rng.random() < 0.5 and world.boss_target(self.x, self.y, 520)) or \
                world.nearest_enemy(self.x, self.y, 520)
            self.retarget = 0.3
        ang = math.atan2(self.vy, self.vx)
        if self.target is not None:
            want = math.atan2(self.target.y - self.y, self.target.x - self.x)
            ang += max(-self.turn * dt, min(self.turn * dt, wrap_angle(want - ang)))
        spd = self.speed * min(1.6, 0.6 + self.age * 1.4)
        self.vx, self.vy = math.cos(ang) * spd, math.sin(ang) * spd
        world.fx.trail(self.x, self.y, scale(self.color, 0.7), 3, 0.25)
        super().update(world, dt)

    def on_hit(self, world, e):
        pass

    def on_expire(self, world):
        world.explosion(self.x, self.y, self.aoe, self.damage, self.color, self.weapon, sound="explode", shake=0.0)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if not on_screen(sx, sy):
            return
        assets.blit_glow(screen, sx, sy, 18, self.color, 0.7)
        spr = assets.shape_sprite("dart", 8, self.color, math.atan2(self.vy, self.vx))
        assets.blit_center(screen, spr, sx, sy)


class Disc(Projectile):
    __slots__ = ("travel", "range", "returning", "cooldowns", "spin", "speed")

    def __init__(self, weapon, x, y, angle, speed, radius, damage, rng, color, life=6.0):
        super().__init__(weapon, x, y, math.cos(angle) * speed, math.sin(angle) * speed, radius, damage, 10 ** 6,
                         life, color, 140)
        self.travel = 0.0
        self.range = rng
        self.returning = False
        self.cooldowns = {}
        self.spin = 0.0
        self.speed = speed

    def update(self, world, dt):
        self.spin += dt * 14
        p = world.player
        if not self.returning:
            self.travel += self.speed * dt
            if self.travel >= self.range:
                self.returning = True
        else:
            dx, dy = p.x - self.x, p.y - self.y
            d = math.hypot(dx, dy) or 1e-6
            spd = self.speed * 1.25 + self.age * 60
            self.vx += (dx / d * spd - self.vx) * min(1.0, dt * 6)
            self.vy += (dy / d * spd - self.vy) * min(1.0, dt * 6)
            if d < 28:
                self.alive = False
                return
        super().update(world, dt)

    def collide(self, world):
        now = world.time
        r = self.radius
        for e in world.grid.query(self.x, self.y, r + 48):
            if not e.alive or self.cooldowns.get(e.uid, 0) > now:
                continue
            rr = r + e.radius
            dx, dy = e.x - self.x, e.y - self.y
            if dx * dx + dy * dy < rr * rr:
                self.cooldowns[e.uid] = now + 0.35
                self.on_hit(world, e)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if not on_screen(sx, sy):
            return
        r = int(self.radius)
        assets.blit_glow(screen, sx, sy, r * 2.6, self.color, 0.6)
        pygame.draw.circle(screen, scale(self.color, 0.35), (int(sx), int(sy)), r)
        pygame.draw.circle(screen, self.color, (int(sx), int(sy)), r, 3)
        for k in range(3):
            a = self.spin + k * TAU / 3
            pygame.draw.line(screen, WHITE, (sx + math.cos(a) * r * 0.3, sy + math.sin(a) * r * 0.3),
                             (sx + math.cos(a) * r * 0.85, sy + math.sin(a) * r * 0.85), 2)


class Mine(Projectile):
    __slots__ = ("arm", "trigger", "aoe")

    def __init__(self, weapon, x, y, damage, aoe, color, life=10.0, arm=0.6):
        super().__init__(weapon, x, y, 0.0, 0.0, 9, damage, 1, life, color, 0)
        self.arm = arm
        self.trigger = 42
        self.aoe = aoe

    def update(self, world, dt):
        self.age += dt
        self.arm -= dt
        self.life -= dt
        if self.life <= 0:
            self.detonate(world)
            return
        if self.arm <= 0:
            for e in world.grid.query(self.x, self.y, self.trigger + 30):
                if e.alive and (e.x - self.x) ** 2 + (e.y - self.y) ** 2 < (self.trigger + e.radius) ** 2:
                    self.detonate(world)
                    return

    def detonate(self, world):
        if not self.alive:
            return
        self.alive = False
        world.explosion(self.x, self.y, self.aoe, self.damage, self.color, self.weapon, sound="explode", shake=0.06)
        if self.weapon is not None and self.weapon.evolved:   # minefield: chain reaction
            for m in world.projectiles:
                if isinstance(m, Mine) and m.alive and m.arm <= 0 and (m.x - self.x) ** 2 + (m.y - self.y) ** 2 < \
                        (self.aoe * 0.9) ** 2:
                    m.life = min(m.life, 0.12)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if not on_screen(sx, sy):
            return
        armed = self.arm <= 0
        blink = armed and int(self.age * (8 if self.life > 2 else 18)) % 2 == 0
        assets.blit_glow(screen, sx, sy, 22, RED if blink else self.color, 0.5)
        spr = assets.shape_sprite("spiky", 9, self.color, self.age * 0.8)
        assets.blit_center(screen, spr, sx, sy)
        pygame.draw.circle(screen, RED if blink else scale(self.color, 0.5), (int(sx), int(sy)), 3)


# --------------------------------------------------------------------------- zones and hazards


class GravityWell:
    def __init__(self, weapon, x, y, radius, pull, damage, life, evolved=False):
        self.weapon = weapon
        self.x, self.y = x, y
        self.radius = radius
        self.pull = pull
        self.damage = damage
        self.life = self.max_life = life
        self.evolved = evolved
        self.tick = 0.0
        self.alive = True
        self.t = 0.0

    def update(self, world, dt):
        self.t += dt
        self.life -= dt
        self.tick -= dt
        hits = self.tick <= 0
        if hits:
            self.tick = 0.25
        for e in world.grid.query(self.x, self.y, self.radius + 30):
            if not e.alive:
                continue
            dx, dy = self.x - e.x, self.y - e.y
            d = math.hypot(dx, dy) or 1e-6
            if d > self.radius + e.radius:
                continue
            if not e.boss and e.owner is None and d > 8:
                f = self.pull * (1.1 - d / self.radius * 0.6) / max(0.6, e.mass ** 0.5)
                e.x += dx / d * f * dt
                e.y += dy / d * f * dt
            if hits:
                world.damage_enemy(e, self.damage, self.weapon, can_crit=False, quiet=True)
        if self.life <= 0:
            self.alive = False
            if self.evolved:
                world.explosion(self.x, self.y, self.radius * 1.25, self.damage * 6, PURPLE, self.weapon,
                                sound="explode", shake=0.15)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if not on_screen(sx, sy, self.radius):
            return
        k = min(1.0, (self.max_life - self.life) * 4, self.life * 3)
        r = self.radius * k
        col = (150, 80, 255) if not self.evolved else (190, 90, 255)
        assets.blit_glow(screen, sx, sy, r * 1.05, col, 0.35)
        pygame.draw.circle(screen, (4, 0, 10), (int(sx), int(sy)), max(2, int(r * 0.22)))
        pygame.draw.circle(screen, scale(col, 0.8), (int(sx), int(sy)), max(3, int(r)), 2)
        for arm in range(4):
            pts = []
            for i in range(14):
                a = -self.t * 4 + arm * TAU / 4 + i * 0.22
                rr = r * (1 - i / 14) * 0.95
                pts.append((sx + math.cos(a) * rr, sy + math.sin(a) * rr))
            pygame.draw.lines(screen, mix(col, WHITE, 0.25), False, pts, 2)


class Laser:
    """A boss beam: a thin warning line first, then a deadly beam."""

    def __init__(self, owner, angle, length=1400, width=34, warn=0.9, active=0.7, damage=24, spin=0.0,
                 color=(255, 80, 120), offset=(0.0, 0.0)):
        self.owner = owner
        self.angle = angle
        self.length = length
        self.width = width
        self.warn = warn
        self.active = active
        self.damage = damage
        self.spin = spin
        self.color = color
        self.offset = offset
        self.t = 0.0
        self.alive = True
        self.fired = False

    def endpoints(self):
        ox = self.owner.x + self.offset[0]
        oy = self.owner.y + self.offset[1]
        return ox, oy, ox + math.cos(self.angle) * self.length, oy + math.sin(self.angle) * self.length

    def update(self, world, dt):
        self.t += dt
        if not self.owner.alive or self.t > self.warn + self.active:
            self.alive = False
            return
        if self.t > self.warn:
            if not self.fired:
                self.fired = True
                world.sfx("laser")
                world.camera.shake(0.12)
            self.angle += self.spin * dt
            p = world.player
            x0, y0, x1, y1 = self.endpoints()
            if point_segment_dist2(p.x, p.y, x0, y0, x1, y1) < (self.width / 2 + p.radius * 0.6) ** 2:
                world.hurt_player(self.damage)

    def draw(self, screen, cam):
        x0, y0, x1, y1 = self.endpoints()
        a = (x0 - cam.cx, y0 - cam.cy)
        b = (x1 - cam.cx, y1 - cam.cy)
        if self.t < self.warn:
            k = self.t / self.warn
            col = scale(self.color, 0.35 + 0.5 * (int(self.t * 12) % 2))
            pygame.draw.line(screen, col, a, b, 1 + int(k * 3))
        else:
            k = 1 - (self.t - self.warn) / self.active
            w = max(2, int(self.width * (0.6 + 0.4 * k)))
            pygame.draw.line(screen, scale(self.color, 0.5), a, b, w + 14)
            pygame.draw.line(screen, self.color, a, b, w)
            pygame.draw.line(screen, WHITE, a, b, max(2, w // 3))


class EnemyBullet:
    __slots__ = ("x", "y", "vx", "vy", "radius", "damage", "color", "life", "alive")

    def __init__(self, x, y, vx, vy, radius, damage, color, life=6.0):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.radius = radius
        self.damage = damage
        self.color = color
        self.life = life
        self.alive = True

    def update(self, world, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return
        p = world.player
        rr = self.radius + p.radius * 0.6
        if (p.x - self.x) ** 2 + (p.y - self.y) ** 2 < rr * rr:
            self.alive = False
            world.hurt_player(self.damage)
            world.fx.sparks(self.x, self.y, self.color, 6, 200, 0.3)

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if not on_screen(sx, sy, 30):
            return
        assets.blit_glow(screen, sx, sy, self.radius * 3, self.color, 0.7)
        assets.blit_center(screen, assets.orb_sprite(self.radius, self.color), sx, sy)


# --------------------------------------------------------------------------- pickups


def gem_color(value):
    color = GEM_TIERS[0][1]
    for threshold, c in GEM_TIERS:
        if value >= threshold:
            color = c
    return color


class Pickup:
    __slots__ = ("kind", "x", "y", "value", "homing", "alive", "t", "color", "speed")

    COLORS = {"heart": (255, 80, 120), "coin": GOLD, "magnet": MAGENTA, "bomb": RED, "chest": GOLD}

    def __init__(self, kind, x, y, value=1):
        self.kind = kind
        self.x, self.y = x, y
        self.value = value
        self.homing = False
        self.alive = True
        self.t = 0.0
        self.speed = 0.0
        self.color = gem_color(value) if kind == "gem" else self.COLORS.get(kind, WHITE)

    def set_value(self, value):
        self.value = value
        self.color = gem_color(value)

    def update(self, world, dt):
        self.t += dt
        p = world.player
        dx, dy = p.x - self.x, p.y - self.y
        d2 = dx * dx + dy * dy
        if self.homing:
            d = math.sqrt(d2) or 1e-6
            self.speed = min(1400, self.speed + dt * 1500)
            step = min(d, (self.speed + p.speed) * dt)
            self.x += dx / d * step
            self.y += dy / d * step
            if d < p.radius + 10:
                self.alive = False
                world.collect(self)
        elif self.kind == "chest":
            if d2 < (p.radius + 24) ** 2:
                self.alive = False
                world.collect(self)
        elif d2 < p.magnet * p.magnet:
            self.homing = True
            self.speed = -180   # a little hop away first, like it's being yanked

    def draw(self, screen, cam):
        sx, sy = self.x - cam.cx, self.y - cam.cy
        if not on_screen(sx, sy, 30):
            return
        k = self.kind
        if k == "gem":
            r = 5 if self.value < 5 else 6 if self.value < 25 else 8 if self.value < 100 else 10
            assets.blit_glow(screen, sx, sy, r * 3, self.color, 0.5)
            assets.blit_center(screen, assets.shape_sprite("diamond", r, self.color, math.pi / 2), sx, sy)
            return
        bob = math.sin(self.t * 4) * 3
        sy += bob
        if k == "chest":
            assets.blit_glow(screen, sx, sy, 60, GOLD, 0.55)
            pygame.draw.polygon(screen, (40, 30, 10), [(sx - 18, sy - 4), (sx + 18, sy - 4), (sx + 18, sy + 14),
                                                       (sx - 18, sy + 14)])
            pygame.draw.polygon(screen, GOLD, [(sx - 18, sy - 4), (sx + 18, sy - 4), (sx + 18, sy + 14),
                                               (sx - 18, sy + 14)], 2)
            pygame.draw.polygon(screen, (90, 66, 16), [(sx - 18, sy - 4), (sx - 13, sy - 15), (sx + 13, sy - 15),
                                                       (sx + 18, sy - 4)])
            pygame.draw.polygon(screen, GOLD, [(sx - 18, sy - 4), (sx - 13, sy - 15), (sx + 13, sy - 15),
                                               (sx + 18, sy - 4)], 2)
            pygame.draw.circle(screen, WHITE, (int(sx), int(sy + 3)), 3)
            for i in range(3):
                a = self.t * 1.5 + i * TAU / 3
                pygame.draw.line(screen, scale(GOLD, 0.5), (sx, sy), (sx + math.cos(a) * 40, sy + math.sin(a) * 40), 1)
            return
        assets.blit_glow(screen, sx, sy, 30, self.color, 0.6)
        if k == "heart":
            c = self.color
            pygame.draw.circle(screen, c, (int(sx - 5), int(sy - 3)), 6)
            pygame.draw.circle(screen, c, (int(sx + 5), int(sy - 3)), 6)
            pygame.draw.polygon(screen, c, [(sx - 11, sy - 1), (sx + 11, sy - 1), (sx, sy + 11)])
            pygame.draw.circle(screen, WHITE, (int(sx - 6), int(sy - 5)), 2)
        elif k == "coin":
            w = abs(math.cos(self.t * 3)) * 0.8 + 0.2
            pts = [(sx + math.cos(i * TAU / 6) * 8 * w, sy + math.sin(i * TAU / 6) * 8) for i in range(6)]
            pygame.draw.polygon(screen, scale(GOLD, 0.45), pts)
            pygame.draw.polygon(screen, GOLD, pts, 2)
        elif k == "magnet":
            screen.blit(assets.icon("magnetron", MAGENTA, 30, frame=False), (int(sx - 15), int(sy - 15)))
        elif k == "bomb":
            assets.blit_center(screen, assets.shape_sprite("spiky", 11, RED, self.t * 2,
                                                          flash=int(self.t * 6) % 2 == 0), sx, sy)


# convenient colors re-exported for weapons and bosses
__all__ = ["Player", "Enemy", "EnemyType", "ENEMY_TYPES", "CODEX_ENEMIES", "Projectile", "Missile", "Disc", "Mine",
           "GravityWell", "Laser", "EnemyBullet", "Pickup", "gem_color", "xp_needed", "on_screen",
           "BLUE", "GREEN", "CYAN"]
