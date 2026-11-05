"""An autopilot that plays SPECTRA. It powers the title-screen demo, --autoplay and the
long simulation tests.

It steers with a potential field: repelled by enemies, bullets and lasers, attracted to
gems and chests, with a slow wander so it explores instead of circling one spot.

created by jullewz
"""

import math

from .util import normalize, point_segment_dist2


class Bot:
    MELEE = ("arc", "orbit", "nova")

    def __init__(self, world):
        self.world = world
        self.wander = world.rng.random() * math.tau
        self.retarget = 0.0

    def move(self, dt):
        w = self.world
        p = w.player
        fx, fy = 0.0, 0.0
        threat = 0
        # pilots with only close-range weapons have to stay nearer to the swarm
        R = 170 if all(x.id in self.MELEE for x in p.weapons) else 300
        for e in w.grid.query(p.x, p.y, R):
            if not e.alive:
                continue
            dx, dy = p.x - e.x, p.y - e.y
            d = math.hypot(dx, dy) - e.radius
            if d < 1:
                d = 1
            if d < R:
                k = (1.0 if not e.boss else 1.6) * (R / d) ** 2 / 9
                fx += dx / (d + e.radius) * k
                fy += dy / (d + e.radius) * k
                if d < 85:
                    threat += 1
        for b in w.bullets:
            dx, dy = p.x - b.x, p.y - b.y
            d2 = dx * dx + dy * dy
            if d2 < 160 * 160:
                d = math.sqrt(d2) or 1
                # dodge sideways relative to the bullet's travel direction
                bx, by = normalize(b.vx, b.vy)
                side = 1 if (dx * -by + dy * bx) > 0 else -1
                k = (160 / d) ** 2 / 6
                fx += (-by * side + dx / d) * k
                fy += (bx * side + dy / d) * k
        for h in w.hazards:
            x0, y0, x1, y1 = h.endpoints()
            if point_segment_dist2(p.x, p.y, x0, y0, x1, y1) < 120 * 120:
                ang = h.angle + math.pi / 2
                nx, ny = math.cos(ang), math.sin(ang)
                side = 1 if ((p.x - x0) * nx + (p.y - y0) * ny) > 0 else -1
                fx += nx * side * 4
                fy += ny * side * 4
        # gems and chests
        # head for the richest nearby patch of gems (value / distance), chests first
        gx = gy = 0.0
        for pk in w.pickups:
            if pk.homing:
                continue
            dx, dy = pk.x - p.x, pk.y - p.y
            d2 = dx * dx + dy * dy
            if d2 > 520 * 520:
                continue
            d = math.sqrt(d2) or 1
            v = 25 if pk.kind == "chest" else (6 if pk.kind == "heart" and p.hp < p.max_hp * 0.6 else
                                               (1 + math.log(1 + pk.value) if pk.kind == "gem" else 2))
            gx += dx / d * v / (d / 100 + 1)
            gy += dy / d * v / (d / 100 + 1)
        if gx or gy:
            dx, dy = normalize(gx, gy)
            k = 1.5 / (1 + threat * 0.4)
            fx += dx * k
            fy += dy * k
        # fight bosses at close-to-mid range so area weapons connect
        if w.boss is not None and w.boss.alive:
            b = w.boss
            dx, dy = b.x - p.x, b.y - p.y
            d = math.hypot(dx, dy) or 1
            if d < 700:
                pull = (d - (b.radius + 150)) / 300
                fx += dx / d * pull * 1.2
                fy += dy / d * pull * 1.2
        # otherwise wander
        self.retarget -= dt
        if self.retarget <= 0:
            self.retarget = 3.0
            self.wander += w.rng.uniform(-1.2, 1.2)
        fx += math.cos(self.wander) * 0.35
        fy += math.sin(self.wander) * 0.35
        if p.hp < p.max_hp * 0.35:
            for pk in w.pickups:
                if pk.kind == "heart":
                    dx, dy = normalize(pk.x - p.x, pk.y - p.y)
                    fx += dx * 2
                    fy += dy * 2
                    break
        mx, my = normalize(fx, fy)
        return mx, my

    @staticmethod
    def choose(world, choices):
        """Pick a level-up card: evolution parts first, then weapons, then passives."""
        p = world.player
        partners = {w.evo_passive for w in p.weapons}

        def score(c):
            s = 0.0
            if c.kind == "weapon":
                s = 3.0 if c.new and len(p.weapons) < 4 else 2.0
                w = p.weapon(c.id)
                if w is not None and w.evo_passive in p.passives:
                    s += 1.5
            elif c.kind == "passive":
                s = 1.5 + (2.0 if c.id in partners else 0)
                if c.id in ("amplifier", "overclock", "multiplexer"):
                    s += 0.5
            return s

        return max(range(len(choices)), key=lambda i: score(choices[i]))
