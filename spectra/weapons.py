"""The ten weapons. Each has 8 levels and evolves into a stronger form when it is at
max level, you own its partner passive, and you open a chest.

A weapon's stats come from its base table plus every level's deltas plus the evolution
bonus, then the pilot's multipliers (damage, cooldown, area, duration, projectiles).

created by jullewz
"""

import math

import pygame

from . import assets
from .config import BLUE, CYAN, GOLD, GREEN, MAGENTA, ORANGE, PURPLE, RAINBOW, RED, TEAL, WHITE, YELLOW
from .entities import Disc, GravityWell, Mine, Missile, Projectile, on_screen
from .util import TAU, ease_out_cubic, mix, point_segment_dist2, scale

VIOLET = (150, 90, 255)


class Weapon:
    id = ""
    name = ""
    desc = ""
    color = CYAN
    base = {}
    levels = []
    evo_passive = ""
    evo_name = ""
    evo_desc = ""
    evo_color = GOLD
    evo = {}
    max_level = 8

    def __init__(self, world):
        self.world = world
        self.player = world.player
        self.level = 1
        self.evolved = False
        self.timer = 0.4
        self.damage_done = 0.0
        self.kills = 0
        self.t = 0.0
        self.queue = 0
        self.burst_t = 0.0

    # ---------------------------------------------------------------- stats

    @property
    def title(self):
        return self.evo_name if self.evolved else self.name

    @property
    def tint(self):
        return self.evo_color if self.evolved else self.color

    def raw(self, key, default=0.0):
        v = self.base.get(key, default)
        for _, delta in self.levels[: self.level - 1]:
            v += delta.get(key, 0)
        if self.evolved:
            v += self.evo.get(key, 0)
        return v

    def dmg(self):
        return self.raw("damage") * self.player.might

    def cd(self):
        return max(0.06, self.raw("cooldown", 1.0) * self.player.cooldown)

    def count(self):
        return max(1, int(self.raw("amount", 1) + self.player.amount))

    def area(self):
        return self.raw("area", 1.0) * self.player.area

    def dur(self):
        return self.raw("duration", 1.0) * self.player.duration

    def spd(self):
        return self.raw("speed", 400) * self.player.proj_speed

    def next_text(self):
        return self.levels[self.level - 1][0] if self.level < self.max_level else ""

    # ---------------------------------------------------------------- behavior

    def facing_angle(self):
        fx, fy = self.player.facing
        return math.atan2(fy, fx)

    def update(self, dt):
        self.t += dt
        self.timer -= dt
        if self.timer <= 0:
            self.fire()
            self.timer = max(self.timer + self.cd(), 0.02)
        if self.queue > 0:
            self.burst_t -= dt
            while self.queue > 0 and self.burst_t <= 0:
                self.queue -= 1
                self.burst_t += self.burst_gap()
                self.shoot_one(self.count() - self.queue - 1)

    def burst_gap(self):
        return 0.07

    def fire(self):
        self.queue = self.count()
        self.burst_t = 0.0

    def shoot_one(self, index):
        pass

    def draw(self, screen, cam):
        pass

    def sfx(self, name, vol=1.0):
        self.world.sfx(name, vol)


# --------------------------------------------------------------------------- 1. pulse blaster


class PulseBlaster(Weapon):
    id = "pulse"
    name = "Pulse Blaster"
    desc = "Fires plasma bolts at the nearest enemy."
    color = CYAN
    base = dict(damage=11, cooldown=0.8, amount=1, speed=640, pierce=2)
    levels = [
        ("+1 bolt", {"amount": 1}),
        ("+5 damage", {"damage": 5}),
        ("+1 bolt, bolts pierce one more enemy", {"amount": 1, "pierce": 1}),
        ("Fires 20% faster", {"cooldown": -0.19}),
        ("+1 bolt", {"amount": 1}),
        ("+8 damage", {"damage": 8}),
        ("+1 bolt, +1 pierce", {"amount": 1, "pierce": 1}),
    ]
    evo_passive = "overclock"
    evo_name = "Hyper Pulse"
    evo_desc = "A torrent of heavy piercing bolts."
    evo_color = MAGENTA
    evo = dict(cooldown=-0.35, damage=8, pierce=2, amount=1)

    def burst_gap(self):
        return 0.05 if self.evolved else 0.065

    def shoot_one(self, index):
        p = self.player
        target = (index % 2 == 1 and self.world.boss_target(p.x, p.y)) or self.world.nearest_enemy(p.x, p.y, 760)
        ang = math.atan2(target.y - p.y, target.x - p.x) if target else self.facing_angle()
        ang += self.world.rng.uniform(-0.06, 0.06)
        s = self.spd()
        r = 6 if self.evolved else 4
        self.world.projectiles.append(Projectile(self, p.x, p.y, math.cos(ang) * s, math.sin(ang) * s, r * self.area(),
                                                 self.dmg(), int(self.raw("pierce", 1)), 1.4, self.tint, 80))
        self.sfx("shoot", 0.5)


# --------------------------------------------------------------------------- 2. arc blade


class ArcBlade(Weapon):
    id = "arc"
    name = "Arc Blade"
    desc = "Slashes a wide arc in front of you."
    color = MAGENTA
    base = dict(damage=20, cooldown=1.15, amount=1, range=150)
    levels = [
        ("Also slashes behind you", {"amount": 1}),
        ("+6 damage", {"damage": 6}),
        ("+15% area", {"area": 0.15}),
        ("+6 damage", {"damage": 6}),
        ("Slashes 15% faster", {"cooldown": -0.2}),
        ("+1 slash", {"amount": 1}),
        ("+10 damage, +15% area", {"damage": 10, "area": 0.15}),
    ]
    evo_passive = "amplifier"
    evo_name = "Crescent Reaper"
    evo_desc = "Huge sweeping slashes that heal you for every hit."
    evo_color = (255, 60, 140)
    evo = dict(damage=14, area=0.25)

    def burst_gap(self):
        return 0.12

    def shoot_one(self, index):
        p = self.player
        reach = self.raw("range", 150) * self.area()
        target = self.world.nearest_enemy(p.x, p.y, reach + 70)
        base = math.atan2(target.y - p.y, target.x - p.x) if target is not None else self.facing_angle()
        ang = base + (math.pi if index % 2 else 0.0) + (index // 2) * 0.55
        span = math.radians(300 if self.evolved else 115)
        hits = 0
        for e in self.world.grid.query(p.x, p.y, reach + 40):
            if not e.alive:
                continue
            dx, dy = e.x - p.x, e.y - p.y
            d = math.hypot(dx, dy)
            if d > reach + e.radius:
                continue
            diff = abs((math.atan2(dy, dx) - ang + math.pi) % TAU - math.pi)
            if d < 36 or diff <= span / 2:
                nx, ny = (dx / d, dy / d) if d else (0.0, 0.0)
                self.world.damage_enemy(e, self.dmg(), self, nx * 240, ny * 240)
                hits += 1
        if self.evolved and hits:
            p.heal(min(hits, 4) * 1.0)
        self.world.fx.arc(p.x, p.y, ang, span, reach * 0.5, reach, self.tint, 0.22)
        self.sfx("whoosh", 0.7)


# --------------------------------------------------------------------------- 3. orbit shards


class OrbitShards(Weapon):
    id = "orbit"
    name = "Orbit Shards"
    desc = "Crystal shards circle around you for a few seconds."
    color = ORANGE
    base = dict(damage=13, cooldown=2.6, amount=2, duration=3.5, speed=3.2, radius=92)
    levels = [
        ("+1 shard", {"amount": 1}),
        ("+25% orbit size", {"radius": 23}),
        ("+5 damage", {"damage": 5}),
        ("+1 shard", {"amount": 1}),
        ("Lasts 1 second longer", {"duration": 1.0}),
        ("+1 shard, spins faster", {"amount": 1, "speed": 0.8}),
        ("+8 damage", {"damage": 8}),
    ]
    evo_passive = "chrono"
    evo_name = "Event Horizon"
    evo_desc = "A permanent ring of shards that never stops spinning."
    evo_color = GOLD
    evo = dict(amount=2, damage=8, radius=20)

    def __init__(self, world):
        super().__init__(world)
        self.active = 0.0
        self.phase = 0.0
        self.cooldowns = {}
        self.positions = []

    def update(self, dt):
        self.t += dt
        if self.evolved:
            self.active = 1.0
        elif self.active > 0:
            self.active -= dt
            if self.active <= 0:
                self.timer = self.cd()
        else:
            self.timer -= dt
            if self.timer <= 0:
                self.active = self.dur()
                self.sfx("whoosh", 0.4)
        self.positions = []
        if self.active <= 0:
            return
        p = self.player
        self.phase += self.raw("speed", 3.2) * dt
        n = self.count()
        orbit = self.raw("radius", 92) * self.area()
        size = 10 * self.area()
        now = self.world.time
        for i in range(n):
            a = self.phase + i * TAU / n
            x, y = p.x + math.cos(a) * orbit, p.y + math.sin(a) * orbit
            self.positions.append((x, y, a))
            for e in self.world.grid.query(x, y, size + 40):
                if not e.alive or self.cooldowns.get(e.uid, 0) > now:
                    continue
                rr = size + e.radius
                if (e.x - x) ** 2 + (e.y - y) ** 2 < rr * rr:
                    self.cooldowns[e.uid] = now + 0.45
                    self.world.damage_enemy(e, self.dmg(), self, math.cos(a) * 200, math.sin(a) * 200)
        if len(self.cooldowns) > 600:
            self.cooldowns = {k: v for k, v in self.cooldowns.items() if v > now}

    def draw(self, screen, cam):
        if not self.positions:
            return
        size = 10 * self.area()
        fade = min(1.0, self.active * 3) if not self.evolved else 1.0
        col = scale(self.tint, 0.4 + 0.6 * fade)
        for x, y, a in self.positions:
            sx, sy = x - cam.cx, y - cam.cy
            assets.blit_glow(screen, sx, sy, size * 3, col, 0.6)
            spr = assets.shape_sprite("diamond", int(size * 1.2), col, a + math.pi / 2)
            assets.blit_center(screen, spr, sx, sy)


# --------------------------------------------------------------------------- 4. nova burst


class Shockwave:
    def __init__(self, weapon, x, y, radius, damage, knock, color, delay=0.0, slow=0.0, duration=0.34):
        self.weapon = weapon
        self.x, self.y = x, y
        self.radius = radius
        self.damage = damage
        self.knock = knock
        self.color = color
        self.t = -delay
        self.slow = slow
        self.duration = duration
        self.hit = set()
        self.alive = True
        self.started = False

    def update(self, world, dt):
        self.t += dt
        if self.t < 0:
            return
        if not self.started:
            self.started = True
            world.fx.ring(self.x, self.y, self.color, 12, self.radius, self.duration + 0.18, 7)
            world.fx.ring(self.x, self.y, WHITE, 6, self.radius * 0.7, self.duration, 2)
            world.sfx("explode", 0.5)
        k = min(1.0, self.t / self.duration)
        r = self.radius * ease_out_cubic(k)
        for e in world.grid.query(self.x, self.y, r + 40):
            if not e.alive or e.uid in self.hit:
                continue
            dx, dy = e.x - self.x, e.y - self.y
            d = math.hypot(dx, dy)
            if d <= r + e.radius:
                self.hit.add(e.uid)
                nx, ny = (dx / d, dy / d) if d else (0.0, 0.0)
                world.damage_enemy(e, self.damage, self.weapon, nx * self.knock, ny * self.knock)
                if self.slow:
                    e.slow = max(e.slow, self.slow)
        if k >= 1:
            self.alive = False

    def draw(self, screen, cam):
        pass


class NovaBurst(Weapon):
    id = "nova"
    name = "Nova Burst"
    desc = "Releases a shockwave that blasts enemies away from you."
    color = GREEN
    base = dict(damage=18, cooldown=2.8, radius=135, knock=420)
    levels = [
        ("+20% radius", {"radius": 27}),
        ("+8 damage", {"damage": 8}),
        ("Fires 15% faster", {"cooldown": -0.4}),
        ("+20% radius", {"radius": 27}),
        ("+10 damage", {"damage": 10}),
        ("Fires 15% faster", {"cooldown": -0.4}),
        ("+14 damage, +20% radius", {"damage": 14, "radius": 27}),
    ]
    evo_passive = "lens"
    evo_name = "Supernova"
    evo_desc = "A double shockwave; the second one freezes enemies in place."
    evo_color = (190, 255, 120)
    evo = dict(damage=20, radius=60)

    def fire(self):
        p = self.player
        r = self.raw("radius", 135) * self.area()
        w = self.world
        w.zones.append(Shockwave(self, p.x, p.y, r, self.dmg(), self.raw("knock", 420), self.tint))
        extra = self.count() - 1
        for k in range(extra):
            w.zones.append(Shockwave(self, p.x, p.y, r * (1.15 + 0.1 * k), self.dmg() * 0.6, 200, self.tint,
                                     delay=0.18 * (k + 1)))
        if self.evolved:
            w.zones.append(Shockwave(self, p.x, p.y, r * 1.45, self.dmg(), 120, WHITE, delay=0.3, slow=1.4))
        w.camera.shake(0.08)


# --------------------------------------------------------------------------- 5. prism lance


class PrismLance(Weapon):
    id = "lance"
    name = "Prism Lance"
    desc = "A beam of light that pierces every enemy in a line."
    color = PURPLE
    base = dict(damage=26, cooldown=2.0, amount=1, width=16, length=900)
    levels = [
        ("+10 damage", {"damage": 10}),
        ("+1 beam", {"amount": 1}),
        ("+40% beam width", {"width": 6}),
        ("Fires 15% faster", {"cooldown": -0.35}),
        ("+1 beam", {"amount": 1}),
        ("+16 damage", {"damage": 16}),
        ("+1 beam, +40% width", {"amount": 1, "width": 6}),
    ]
    evo_passive = "fortune"
    evo_name = "Spectrum Ray"
    evo_desc = "Rainbow beams that always land critical hits."
    evo_color = (255, 240, 120)
    evo = dict(damage=20, width=10, amount=1)

    def burst_gap(self):
        return 0.1

    def shoot_one(self, index):
        w = self.world
        p = self.player
        targets = [e for e in w.enemies if e.alive and w.camera.on_screen(e.x, e.y, -20)]
        boss = w.boss_target(p.x, p.y, 900)
        if boss is not None and index == 0:
            ang = math.atan2(boss.y - p.y, boss.x - p.x)
        elif targets:
            t = w.rng.choice(targets[:60]) if index else min(targets, key=lambda e: (e.x - p.x) ** 2 + (e.y - p.y) ** 2)
            ang = math.atan2(t.y - p.y, t.x - p.x)
        else:
            ang = self.facing_angle() + (index * 0.7)
        length = self.raw("length", 900)
        width = self.raw("width", 16) * self.area()
        x1, y1 = p.x + math.cos(ang) * length, p.y + math.sin(ang) * length
        dmg = self.dmg() * (2 if self.evolved else 1)
        for e in w.grid_segment(p.x, p.y, x1, y1, width):
            if point_segment_dist2(e.x, e.y, p.x, p.y, x1, y1) < (width / 2 + e.radius) ** 2:
                w.damage_enemy(e, dmg, self, math.cos(ang) * 90, math.sin(ang) * 90,
                               can_crit=not self.evolved, force_crit=self.evolved)
        if self.evolved:
            nx, ny = -math.sin(ang), math.cos(ang)
            for i, col in enumerate(RAINBOW):
                off = (i - 2.5) * width * 0.22
                w.fx.beam([(p.x + nx * off, p.y + ny * off), (x1 + nx * off, y1 + ny * off)], col,
                          int(width * 0.35) + 2, 0.3)
        else:
            w.fx.beam([(p.x, p.y), (x1, y1)], self.tint, int(width), 0.25)
        self.sfx("laser", 0.6)


# --------------------------------------------------------------------------- 6. seeker swarm


class SeekerSwarm(Weapon):
    id = "seeker"
    name = "Seeker Swarm"
    desc = "Homing micro-missiles that explode on impact."
    color = RED
    base = dict(damage=12, cooldown=1.9, amount=2, speed=330, aoe=46)
    levels = [
        ("+1 missile", {"amount": 1}),
        ("+6 damage", {"damage": 6}),
        ("+30% blast radius", {"aoe": 14}),
        ("+1 missile", {"amount": 1}),
        ("Launches 20% faster", {"cooldown": -0.38}),
        ("+8 damage", {"damage": 8}),
        ("+2 missiles", {"amount": 2}),
    ]
    evo_passive = "rails"
    evo_name = "Hunter Hive"
    evo_desc = "Endless swarms of fast, hungry missiles."
    evo_color = ORANGE
    evo = dict(amount=3, cooldown=-0.6, damage=6, aoe=12)

    def shoot_one(self, index):
        p = self.player
        ang = self.facing_angle() + self.world.rng.uniform(-1.3, 1.3) + (math.pi if index % 2 else 0)
        self.world.projectiles.append(Missile(self, p.x, p.y, ang, self.spd(), self.dmg(),
                                              self.raw("aoe", 46) * self.area(), self.tint))
        self.sfx("shoot", 0.35)


# --------------------------------------------------------------------------- 7. chain spark


class ChainSpark(Weapon):
    id = "chain"
    name = "Chain Spark"
    desc = "Lightning that leaps from enemy to enemy."
    color = BLUE
    base = dict(damage=14, cooldown=2.0, amount=1, chains=3, jump=210)
    levels = [
        ("+2 jumps", {"chains": 2}),
        ("+6 damage", {"damage": 6}),
        ("+1 bolt", {"amount": 1}),
        ("+2 jumps", {"chains": 2}),
        ("Strikes 20% faster", {"cooldown": -0.4}),
        ("+10 damage", {"damage": 10}),
        ("+1 bolt, +2 jumps", {"amount": 1, "chains": 2}),
    ]
    evo_passive = "multiplexer"
    evo_name = "Storm Lattice"
    evo_desc = "Constant storms that stun everything they touch."
    evo_color = (170, 230, 255)
    evo = dict(chains=6, cooldown=-0.6, damage=6)

    def burst_gap(self):
        return 0.09

    def shoot_one(self, index):
        w = self.world
        p = self.player
        near = w.enemies_near(p.x, p.y, 470)
        if not near:
            return
        near.sort(key=lambda e: (e.x - p.x) ** 2 + (e.y - p.y) ** 2)
        cur = w.rng.choice(near[:4])
        struck = set()
        px, py = p.x, p.y
        jump = self.raw("jump", 210) * self.area()
        for _ in range(int(self.raw("chains", 3)) + 1):
            struck.add(cur.uid)
            w.fx.lightning(px, py, cur.x, cur.y, self.tint)
            w.damage_enemy(cur, self.dmg(), self)
            if self.evolved:
                cur.slow = max(cur.slow, 0.8)
            px, py = cur.x, cur.y
            best, bd = None, jump * jump
            for e in w.grid.query(px, py, jump):
                if e.alive and e.uid not in struck:
                    d = (e.x - px) ** 2 + (e.y - py) ** 2
                    if d < bd:
                        best, bd = e, d
            if best is None:
                break
            cur = best
        self.sfx("zap", 0.6)


# --------------------------------------------------------------------------- 8. gravity well


class GravityWellWeapon(Weapon):
    id = "well"
    name = "Gravity Well"
    desc = "Opens a vortex that drags enemies in and grinds them down."
    color = VIOLET
    base = dict(damage=5, cooldown=5.5, amount=1, duration=3.0, radius=105, pull=150)
    levels = [
        ("+25% radius", {"radius": 26}),
        ("+3 damage", {"damage": 3}),
        ("Lasts 1 second longer", {"duration": 1.0}),
        ("+1 vortex", {"amount": 1}),
        ("+25% radius, stronger pull", {"radius": 26, "pull": 60}),
        ("+4 damage", {"damage": 4}),
        ("Opens 20% faster", {"cooldown": -1.1}),
    ]
    evo_passive = "magnetron"
    evo_name = "Black Hole"
    evo_desc = "A crushing singularity that implodes when it closes."
    evo_color = (200, 110, 255)
    evo = dict(radius=70, pull=140, damage=5)

    def fire(self):
        w = self.world
        p = self.player
        near = w.enemies_near(p.x, p.y, 430)
        for i in range(self.count()):
            if near:
                t = w.rng.choice(near)
                x, y = t.x, t.y
            else:
                a = w.rng.random() * TAU
                x, y = p.x + math.cos(a) * 200, p.y + math.sin(a) * 200
            w.zones.append(GravityWell(self, x, y, self.raw("radius", 105) * self.area(), self.raw("pull", 150),
                                       self.dmg(), self.dur(), self.evolved))
        self.sfx("whoosh", 0.8)


# --------------------------------------------------------------------------- 9. mine layer


class MineLayer(Weapon):
    id = "mines"
    name = "Mine Layer"
    desc = "Drops proximity mines behind you."
    color = YELLOW
    base = dict(damage=32, cooldown=1.7, amount=1, aoe=88)
    levels = [
        ("+12 damage", {"damage": 12}),
        ("+1 mine", {"amount": 1}),
        ("+25% blast radius", {"aoe": 22}),
        ("Drops 20% faster", {"cooldown": -0.34}),
        ("+1 mine", {"amount": 1}),
        ("+18 damage", {"damage": 18}),
        ("+2 mines", {"amount": 2}),
    ]
    evo_passive = "plating"
    evo_name = "Minefield"
    evo_desc = "Mines scatter all around you and set each other off."
    evo_color = (255, 140, 60)
    evo = dict(amount=2, aoe=26, damage=12)

    def fire(self):
        w = self.world
        p = self.player
        fx, fy = p.facing
        for i in range(self.count()):
            if self.evolved:
                a = w.rng.random() * TAU
                r = w.rng.uniform(60, 170)
                x, y = p.x + math.cos(a) * r, p.y + math.sin(a) * r
            else:
                x = p.x - fx * 26 + w.rng.uniform(-28, 28)
                y = p.y - fy * 26 + w.rng.uniform(-28, 28)
            w.projectiles.append(Mine(self, x, y, self.dmg(), self.raw("aoe", 88) * self.area(), self.tint,
                                      life=10 * self.dur()))


# --------------------------------------------------------------------------- 10. halo disc


class HaloDisc(Weapon):
    id = "disc"
    name = "Halo Disc"
    desc = "Spinning discs that fly out and come back to you."
    color = TEAL
    base = dict(damage=12, cooldown=1.8, amount=1, speed=470, range=330, size=13)
    levels = [
        ("+1 disc", {"amount": 1}),
        ("+6 damage", {"damage": 6}),
        ("+30% size", {"size": 4}),
        ("+1 disc", {"amount": 1}),
        ("Throws 20% faster", {"cooldown": -0.36}),
        ("+30% range", {"range": 100}),
        ("+10 damage, +1 disc", {"damage": 10, "amount": 1}),
    ]
    evo_passive = "thrusters"
    evo_name = "Ricochet Halo"
    evo_desc = "A storm of huge discs thrown in every direction."
    evo_color = (120, 255, 230)
    evo = dict(amount=2, damage=10, size=6, range=80)

    def fire(self):
        p = self.player
        n = self.count()
        base = self.facing_angle()
        for i in range(n):
            if self.evolved:
                ang = base + i * TAU / n
            else:
                ang = base + (i - (n - 1) / 2) * 0.45
            self.world.projectiles.append(Disc(self, p.x, p.y, ang, self.spd(), self.raw("size", 13) * self.area(),
                                               self.dmg(), self.raw("range", 330) * self.area(), self.tint))
        self.sfx("whoosh", 0.5)


# --------------------------------------------------------------------------- registry

WEAPON_CLASSES = [PulseBlaster, ArcBlade, OrbitShards, NovaBurst, PrismLance, SeekerSwarm, ChainSpark,
                  GravityWellWeapon, MineLayer, HaloDisc]
WEAPONS = {cls.id: cls for cls in WEAPON_CLASSES}


def weapon_icon(cls_or_weapon, size=56, locked=False):
    evolved = getattr(cls_or_weapon, "evolved", False)
    tint = cls_or_weapon.evo_color if evolved else cls_or_weapon.color
    return assets.icon(cls_or_weapon.id, tint, size, locked=locked, evolved=evolved)


def draw_shards(screen, color, x, y, size, t):
    """Tiny helper the codex uses to preview projectiles."""
    for k in range(3):
        a = t + k * TAU / 3
        assets.blit_glow(screen, x + math.cos(a) * size, y + math.sin(a) * size, 10, color, 0.6)
    pygame.draw.circle(screen, mix(color, WHITE, 0.5), (int(x), int(y)), 4)


__all__ = ["Weapon", "WEAPONS", "WEAPON_CLASSES", "Shockwave", "weapon_icon", "on_screen", "CYAN", "GOLD"]
