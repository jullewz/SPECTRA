"""The spawn director: decides what attacks you, how many, and when.

Pressure ramps up continuously, the enemy mix changes every minute or two, and a script
of events (swarms, encirclements, elites and bosses) punctuates the run.

created by jullewz
"""

import math

from .bosses import HiveQueen, PrismColossus, Serpent, Singularity
from .config import GOLD, MAX_ENEMIES, ORANGE, RED, SPAWN_DISTANCE, YELLOW
from .util import TAU, weighted_choice

POOLS = [
    (0, {"drone": 10}),
    (40, {"drone": 8, "dart": 3}),
    (90, {"drone": 7, "dart": 3, "weaver": 3}),
    (150, {"drone": 6, "dart": 3, "weaver": 3, "splitter": 2, "spitter": 1}),
    (210, {"drone": 5, "dart": 3, "weaver": 3, "splitter": 3, "spitter": 2, "brute": 1}),
    (270, {"drone": 4, "dart": 3, "weaver": 3, "splitter": 3, "spitter": 2, "brute": 2, "charger": 2}),
    (360, {"drone": 3, "dart": 3, "weaver": 3, "splitter": 3, "spitter": 2, "brute": 2, "charger": 2,
           "bomber": 2, "warden": 1}),
    (480, {"drone": 2, "dart": 3, "weaver": 3, "splitter": 3, "spitter": 3, "brute": 3, "charger": 3,
           "bomber": 3, "warden": 1}),
    (600, {"dart": 3, "weaver": 3, "splitter": 3, "spitter": 3, "brute": 4, "charger": 3, "bomber": 3,
           "warden": 2}),
]

ELITE_KINDS = ["brute", "splitter", "charger", "weaver", "warden", "spitter"]

SCRIPT = [
    (60, "swarm", "mite", 34),
    (90, "elite", None, 1),
    (150, "elite", None, 1),
    (180, "boss", HiveQueen, 0),
    (240, "encircle", "drone", 32),
    (270, "elite", None, 1),
    (300, "swarm", "mite", 50),
    (330, "elite", None, 2),
    (360, "boss", PrismColossus, 0),
    (420, "encircle", "brute", 16),
    (450, "elite", None, 2),
    (480, "swarm", "dart", 60),
    (510, "elite", None, 2),
    (540, "boss", Serpent, 0),
    (600, "encircle", "weaver", 40),
    (630, "elite", None, 3),
    (660, "swarm", "mite", 80),
    (690, "elite", None, 3),
    (720, "final", Singularity, 0),
]


class Director:
    def __init__(self, world):
        self.world = world
        self.acc = 0.0
        self.script = list(SCRIPT)
        self.final = False
        self.diff = world.stage.difficulty

    # ---------------------------------------------------------------- scaling

    def scales(self):
        m = self.world.time / 60
        hp = (1 + m * 0.2 + m * m * 0.035) * self.diff
        dmg = (1 + m * 0.06) * (0.85 + 0.15 * self.diff)
        return hp, dmg

    def pool(self):
        t = self.world.time
        weights = POOLS[0][1]
        for start, w in POOLS:
            if t >= start:
                weights = w
        return weights

    def spawn_point(self, distance=None):
        w = self.world
        p = w.player
        rng = w.rng
        fx, fy = p.facing
        moving = abs(p.vx) + abs(p.vy) > 40
        if moving and rng.random() < 0.55:
            a = math.atan2(fy, fx) + rng.uniform(-1.0, 1.0)
        else:
            a = rng.random() * TAU
        d = (distance or SPAWN_DISTANCE) + rng.random() * 90
        return p.x + math.cos(a) * d, p.y + math.sin(a) * d

    # ---------------------------------------------------------------- per frame

    def update(self, dt):
        w = self.world
        t = w.time
        while self.script and self.script[0][0] <= t:
            _, kind, arg, n = self.script.pop(0)
            self.event(kind, arg, n)
        if self.final:
            return
        boss = w.boss is not None
        m = t / 60
        rate = (1.0 + m * 0.7 + m * m * 0.05) * math.sqrt(self.diff) * (0.35 if boss else 1.0)
        target = (8 + t * 0.22) * (0.5 if boss else 1.0)
        self.acc += rate * dt
        alive = len(w.enemies)
        burst = 0
        while alive < MAX_ENEMIES and (self.acc >= 1 or (alive < target and burst < 3)):
            if self.acc >= 1:
                self.acc -= 1
            else:
                burst += 1
            kind = weighted_choice(w.rng, self.pool())
            x, y = self.spawn_point()
            w.spawn_enemy(kind, x, y)
            alive += 1
        if self.acc > 5:
            self.acc = 5

    # ---------------------------------------------------------------- scripted events

    def event(self, kind, arg, n):
        w = self.world
        p = w.player
        rng = w.rng
        if kind == "swarm":
            a = rng.random() * TAU
            dirx, diry = -math.cos(a), -math.sin(a)
            cx, cy = p.x + math.cos(a) * 820, p.y + math.sin(a) * 820
            nx, ny = -diry, dirx
            for i in range(n):
                off = (i % 12 - 5.5) * 30
                back = (i // 12) * 40
                e = w.spawn_enemy(arg, cx + nx * off - dirx * back, cy + ny * off - diry * back, force=True)
                if e:
                    e.dirx, e.diry = dirx, diry
                    e.timer = 4.0
            w.show_banner("INCOMING SWARM", "Something is coming from the dark", ORANGE, warn=True)
        elif kind == "encircle":
            for i in range(n):
                a = i * TAU / n
                w.spawn_enemy(arg, p.x + math.cos(a) * 560, p.y + math.sin(a) * 560, force=True)
            w.show_banner("SURROUNDED", "Break the ring", RED, warn=True)
        elif kind == "elite":
            for _ in range(n):
                x, y = self.spawn_point()
                w.spawn_enemy(rng.choice(ELITE_KINDS), x, y, elite=True, force=True)
            w.show_banner("ELITE SIGHTED", "Destroy it for a chest", GOLD, small=True)
        elif kind == "boss":
            w.spawn_boss(arg)
        elif kind == "final":
            self.final = True
            w.show_banner("12:00", "The swarm falls silent...", YELLOW, warn=True)
            w.spawn_boss(arg)
