"""The game world: owns every entity, runs the simulation and renders the scene.

created by jullewz
"""

import math
import random

from .config import (DESPAWN_DISTANCE, GOLD, GREEN, IFRAMES, MAX_ENEMIES, MAX_GEMS, PINK, RED, TEAL, WHITE,
                     YELLOW)
from .data import CHAR_BY_ID, CHARACTERS, STAGE_BY_ID, STAGES
from .director import Director
from .entities import ENEMY_TYPES, Enemy, EnemyBullet, Pickup, Player
from .fx import FX, Background, Camera
from .save import DEFAULT_SETTINGS
from .util import SpatialHash
from .weapons import WEAPONS


class World:
    def __init__(self, char_id="nova", stage_id="grid", seed=None, meta=None, settings=None, audio=None,
                 demo=False):
        self.rng = random.Random(seed)
        self.seed = seed
        self.settings = settings if settings is not None else dict(DEFAULT_SETTINGS)
        self.audio = audio
        self.demo = demo
        self.char = CHAR_BY_ID.get(char_id, CHARACTERS[0])
        self.stage = STAGE_BY_ID.get(stage_id, STAGES[0])
        self.time = 0.0
        self.frame = 0
        self.fx = FX(self.settings)
        self.camera = Camera(self.settings)
        self.background = Background(self.stage, seed=self.rng.randint(0, 10 ** 6))
        self.grid = SpatialHash(90)
        self.enemies = []
        self.projectiles = []
        self.bullets = []
        self.pickups = []
        self.zones = []
        self.hazards = []
        self.player = Player(self, self.char, meta or {})
        self.kills = 0
        self.flux = 0
        self.total_damage = 0.0
        self.damage_taken = 0.0
        self.levelups = 0
        self.chests = 0
        self.boss = None
        self.bosses_killed = []
        self.evolutions = 0
        self.evolved_names = []
        self.victory = False
        self.dead = False
        self.end_timer = 0.0
        self.banner = None
        self.no_hit = 0.0
        self.best_no_hit = 0.0
        self.best_bomb = 0
        self.bomb_count = None
        self.gem_count = 0
        self.gem_combo = 0
        self.gem_combo_t = 0.0
        self.seen = set()
        self.toasts = []
        self.director = Director(self)
        self.add_weapon(self.char.weapon)
        self.camera.snap(0.0, 0.0)

    # ---------------------------------------------------------------- helpers

    def sfx(self, name, vol=1.0):
        if self.audio is not None and not self.demo:
            self.audio.play(name, vol)

    def add_weapon(self, wid):
        w = WEAPONS[wid](self)
        self.player.weapons.append(w)
        self.seen.add("w:" + wid)
        return w

    def show_banner(self, title, sub="", color=WHITE, warn=False, small=False, duration=3.2):
        self.banner = {"title": title, "sub": sub, "color": color, "t": 0.0, "dur": duration, "small": small}
        if warn:
            self.sfx("warn", 0.8)

    def toast(self, text, color=WHITE):
        self.toasts.append([text, color, 3.0])

    def nearest_enemy(self, x, y, maxd=700):
        for r in (240, maxd):
            best, bd = None, r * r
            for e in self.grid.query(x, y, r):
                if e.alive:
                    d = (e.x - x) ** 2 + (e.y - y) ** 2
                    if d < bd:
                        best, bd = e, d
            if best is not None:
                return best
        return None

    def boss_target(self, x, y, maxd=650):
        """The boss, if one is alive, on screen and within range — weapons favor it."""
        b = self.boss
        if b is not None and b.alive and (b.x - x) ** 2 + (b.y - y) ** 2 < maxd * maxd:
            return b
        return None

    def enemies_near(self, x, y, r):
        r2 = r * r
        return [e for e in self.grid.query(x, y, r) if e.alive and (e.x - x) ** 2 + (e.y - y) ** 2 < r2]

    def grid_segment(self, x0, y0, x1, y1, width):
        """Enemies near a line segment (candidates for beam hits)."""
        found = {}
        length = math.hypot(x1 - x0, y1 - y0)
        step = self.grid.cell * 0.8
        n = max(1, int(length / step))
        reach = width + self.grid.cell * 0.6
        for i in range(n + 1):
            t = i / n
            for e in self.grid.query(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, reach):
                if e.alive:
                    found[e.uid] = e
        return list(found.values())

    # ---------------------------------------------------------------- spawning

    def spawn_enemy(self, kind, x, y, elite=False, force=False):
        if len(self.enemies) >= MAX_ENEMIES + (40 if force else 0):
            return None
        hp, dmg = self.director.scales()
        e = Enemy(self, ENEMY_TYPES[kind], x, y, hp, dmg, elite)
        self.enemies.append(e)
        self.seen.add("e:" + kind)
        return e

    def spawn_boss(self, cls):
        x, y = self.director.spawn_point(620)
        hp, dmg = self.director.scales()
        boss = cls(self, x, y, self.stage.difficulty * (1 + self.time / 60 * 0.45), dmg)
        self.enemies.append(boss)
        self.boss = boss
        self.seen.add("b:" + boss.boss_id)
        self.show_banner(boss.title, boss.subtitle, boss.color, duration=3.8)
        self.sfx("boss")
        self.camera.shake(0.5)
        return boss

    def enemy_shot(self, x, y, vx, vy, radius, damage, color):
        if len(self.bullets) < 700:
            self.bullets.append(EnemyBullet(x, y, vx, vy, radius, damage, color))

    def drop_gem(self, x, y, value):
        if value <= 0:
            return
        if self.gem_count >= MAX_GEMS:
            for _ in range(4):
                g = self.pickups[self.rng.randrange(len(self.pickups))]
                if g.kind == "gem" and not g.homing:
                    g.set_value(g.value + value)
                    return
        self.pickups.append(Pickup("gem", x + self.rng.uniform(-6, 6), y + self.rng.uniform(-6, 6), value))
        self.gem_count += 1

    # ---------------------------------------------------------------- combat

    def damage_enemy(self, e, amount, source=None, kx=0.0, ky=0.0, can_crit=True, force_crit=False, quiet=False):
        seg = None
        if e.owner is not None:
            seg, e = e, e.owner
            amount *= 0.3   # body segments are armored; the head takes full damage
        if not e.alive:
            return False
        crit = force_crit or (can_crit and self.rng.random() < self.player.crit)
        if crit:
            amount *= 2.0
        e.hp -= amount
        e.flash = 0.08
        if seg is not None:
            seg.flash = 0.08
        if (kx or ky) and not e.boss:
            e.kx += kx / e.mass
            e.ky += ky / e.mass
        if source is not None:
            source.damage_done += amount
        self.total_damage += amount
        if not quiet or crit:
            at = seg or e
            self.fx.number(at.x, at.y - at.radius, amount, crit)
        if not quiet:
            self.sfx("hit", 0.3)
        if e.hp <= 0:
            self.kill_enemy(e, source)
            return True
        return False

    def kill_enemy(self, e, source=None):
        if not e.alive:
            return
        e.alive = False
        self.kills += 1
        if source is not None:
            source.kills += 1
        if getattr(self, "bomb_count", None) is not None:
            self.bomb_count += 1
        if e.boss:
            self.on_boss_down(e)
            return
        self.fx.burst(e.x, e.y, e.color, (1.6 if e.elite else 0.6) + e.radius / 30)
        self.sfx("kill", 0.4)
        if e.kind == "splitter":
            for k in (-1, 1):
                s = self.spawn_enemy("shardling", e.x + k * 10, e.y - k * 6, force=True)
                if s:
                    s.kx, s.ky = k * 160, -k * 80
        if e.elite:
            self.pickups.append(Pickup("chest", e.x, e.y))
            self.fx.ring(e.x, e.y, GOLD, 10, 140, 0.5, 4)
            self.camera.shake(0.2)
        self.drop_gem(e.x, e.y, max(1, int(round(e.xp * (1 + self.time / 60 * 0.1)))))
        luck = self.player.luck
        r = self.rng.random()
        for kind, chance in (("heart", 0.006), ("coin", 0.022), ("magnet", 0.0025), ("bomb", 0.0018)):
            chance *= luck
            if r < chance:
                p = Pickup(kind, e.x, e.y, 1 + (self.rng.random() < 0.2) * 4 if kind == "coin" else 1)
                self.pickups.append(p)
                break
            r -= chance

    def on_boss_down(self, boss):
        self.bosses_killed.append(boss.boss_id)
        if hasattr(boss, "on_death"):
            boss.on_death(self)
        for i in range(6):
            a = i * math.tau / 6
            self.fx.burst(boss.x + math.cos(a) * 40, boss.y + math.sin(a) * 40, boss.color, 2.0)
        self.fx.ring(boss.x, boss.y, WHITE, 20, 420, 0.8, 8)
        self.fx.ring(boss.x, boss.y, boss.color, 10, 300, 1.0, 5)
        self.fx.screen_flash(0.8, boss.color)
        self.camera.shake(0.9)
        self.sfx("bomb")
        for i in range(14):
            a = i * math.tau / 14
            self.drop_gem(boss.x + math.cos(a) * 50, boss.y + math.sin(a) * 50, 25)
        others = [e for e in self.enemies if e.alive and e.boss]
        self.boss = others[0] if others else None
        if boss.boss_id == "singularity":
            self.victory = True
            self.end_timer = 0.0
            self.sfx("victory")
            self.show_banner("VICTORY", "The swarm is silent", GOLD, duration=6.0)
        else:
            self.pickups.append(Pickup("chest", boss.x, boss.y))
            self.show_banner(boss.title + " DESTROYED", "A chest has dropped", GOLD)

    def explosion(self, x, y, radius, damage, color, source=None, sound="explode", shake=0.1):
        for e in self.grid.query(x, y, radius + 40):
            if not e.alive:
                continue
            dx, dy = e.x - x, e.y - y
            d = math.hypot(dx, dy)
            if d < radius + e.radius:
                nx, ny = (dx / d, dy / d) if d else (0.0, 0.0)
                self.damage_enemy(e, damage, source, nx * 170, ny * 170, quiet=True)
        self.fx.ring(x, y, color, 8, radius, 0.35, 5)
        self.fx.burst(x, y, color, 1.0)
        if shake:
            self.camera.shake(shake)
        if sound:
            self.sfx(sound, 0.5)

    def detonate(self, bomber):
        """A bomber enemy blowing itself up next to the player."""
        bomber.alive = False
        p = self.player
        if (p.x - bomber.x) ** 2 + (p.y - bomber.y) ** 2 < (80 + p.radius) ** 2:
            self.hurt_player(bomber.damage)
        self.fx.ring(bomber.x, bomber.y, bomber.color, 10, 80, 0.4, 5)
        self.fx.burst(bomber.x, bomber.y, bomber.color, 1.5)
        self.camera.shake(0.15)
        self.sfx("explode", 0.7)

    def heal_pulse(self, warden):
        for o in self.grid.query(warden.x, warden.y, 220):
            if o.alive and not o.boss and o.owner is None and o is not warden:
                o.hp = min(o.max_hp, o.hp + o.max_hp * 0.25)
        self.fx.ring(warden.x, warden.y, TEAL, 10, 220, 0.6, 3)

    def hurt_player(self, amount):
        p = self.player
        if p.iframes > 0 or self.dead or self.victory:
            return
        dmg = max(1.0, amount - p.armor)
        p.hp -= dmg
        p.iframes = IFRAMES
        p.hurt = 0.35
        self.damage_taken += dmg
        self.no_hit = 0.0
        self.camera.shake(0.28)
        self.fx.sparks(p.x, p.y, RED, 10, 280, 0.4)
        self.sfx("hurt")
        if p.hp > 0:
            return
        if self.demo:
            p.hp = p.max_hp
            return
        if p.revives > 0:
            p.revives -= 1
            p.hp = p.max_hp * 0.5
            p.iframes = 2.5
            self.bomb(p.x, p.y, revive=True)
            self.show_banner("REVIVED", "Second chance", PINK)
            self.sfx("revive")
            return
        p.hp = 0
        self.dead = True
        self.end_timer = 0.0
        self.fx.burst(p.x, p.y, self.char.color, 4.0)
        self.fx.ring(p.x, p.y, self.char.color, 10, 260, 0.9, 6)
        self.camera.shake(1.0)
        self.sfx("bomb")
        self.sfx("defeat")

    def bomb(self, x, y, revive=False):
        self.bomb_count = 0
        for e in list(self.enemies):
            if not e.alive or e.owner is not None or not self.camera.on_screen(e.x, e.y, 60):
                continue
            if e.boss:
                self.damage_enemy(e, e.max_hp * 0.05, None, can_crit=False, quiet=True)
            else:
                self.damage_enemy(e, e.hp + 1, None, can_crit=False, quiet=True)
        if not revive:
            self.best_bomb = max(self.best_bomb, self.bomb_count)
        self.bomb_count = None
        self.bullets.clear()
        self.fx.screen_flash(0.9, WHITE)
        self.fx.ring(x, y, WHITE, 20, 900, 0.7, 10)
        self.camera.shake(0.7)
        self.sfx("bomb")

    def collect(self, pk):
        p = self.player
        k = pk.kind
        if k == "gem":
            self.gem_count -= 1
            p.add_xp(pk.value)
            self.gem_combo += 1
            self.gem_combo_t = 0.35
            if self.audio is not None and not self.demo:
                self.audio.gem(self.gem_combo // 6)
        elif k == "heart":
            healed = p.heal(30)
            self.fx.label(p.x, p.y - 26, f"+{int(healed)}", GREEN)
            self.sfx("heal")
        elif k == "coin":
            self.flux += pk.value
            self.fx.label(p.x, p.y - 26, f"+{pk.value} flux", GOLD, 20)
            self.sfx("pickup", 0.7)
        elif k == "magnet":
            for g in self.pickups:
                if g.kind == "gem":
                    g.homing = True
            self.fx.ring(p.x, p.y, (255, 70, 200), 10, 500, 0.6, 4)
            self.sfx("pickup")
        elif k == "bomb":
            self.bomb(p.x, p.y)
        elif k == "chest":
            self.chests += 1
            self.sfx("chest")

    def on_level_up(self):
        self.levelups += 1
        p = self.player
        self.fx.ring(p.x, p.y, YELLOW, 10, 120, 0.5, 4)
        self.sfx("levelup")

    def on_evolve(self, weapon):
        self.evolutions += 1
        self.evolved_names.append(weapon.evo_name)
        self.seen.add("x:" + weapon.id)
        self.sfx("evolve")

    # ---------------------------------------------------------------- simulation

    def update(self, dt, move=(0.0, 0.0)):
        if self.dead or self.victory:
            self.end_timer += dt
            self.fx.update(dt)
            self.camera.update(dt)
            for b in self.bullets:
                b.life = min(b.life, 0.3)
            return
        self.time += dt
        self.frame += 1
        p = self.player
        p.update(dt, move[0], move[1])

        grid = self.grid
        grid.clear()
        for e in self.enemies:
            if e.alive:
                grid.insert(e)

        for w in p.weapons:
            w.update(dt)
        self.director.update(dt)

        for e in self.enemies:
            if e.alive:
                e.update(self, dt)
        self.separate()
        self.contact_damage()
        if self.frame % 15 == 0:
            self.recycle()

        for group in (self.projectiles, self.bullets, self.zones, self.hazards, self.pickups):
            for obj in group:
                if obj.alive:
                    obj.update(self, dt)
        self.enemies = [e for e in self.enemies if e.alive]
        self.projectiles = [o for o in self.projectiles if o.alive]
        self.bullets = [o for o in self.bullets if o.alive]
        self.zones = [o for o in self.zones if o.alive]
        self.hazards = [o for o in self.hazards if o.alive]
        self.pickups = [o for o in self.pickups if o.alive]
        if self.boss is not None and not self.boss.alive:
            self.boss = None

        self.no_hit += dt
        self.best_no_hit = max(self.best_no_hit, self.no_hit)
        if self.gem_combo_t > 0:
            self.gem_combo_t -= dt
            if self.gem_combo_t <= 0:
                self.gem_combo = 0
        if self.banner is not None:
            self.banner["t"] += dt
            if self.banner["t"] > self.banner["dur"]:
                self.banner = None
        for t in self.toasts:
            t[2] -= dt
        self.toasts = [t for t in self.toasts if t[2] > 0]

        self.fx.update(dt)
        self.camera.follow(p.x, p.y, dt)
        self.camera.update(dt)

    def separate(self):
        """Keep enemies from stacking on top of each other (half of them per frame)."""
        parity = self.frame & 1
        query = self.grid.query
        sqrt = math.sqrt
        for i, e in enumerate(self.enemies):
            if (i & 1) != parity or not e.alive or e.boss or e.owner is not None:
                continue
            r = e.radius
            ex, ey = e.x, e.y
            for o in query(ex, ey, r + 30):
                if o is e or not o.alive:
                    continue
                dx, dy = ex - o.x, ey - o.y
                rr = r + o.radius
                d2 = dx * dx + dy * dy
                if 1e-6 < d2 < rr * rr:
                    d = sqrt(d2)
                    push = (rr - d) * (0.9 if (o.boss or o.owner is not None) else 0.45)
                    ex += dx / d * push
                    ey += dy / d * push
            e.x, e.y = ex, ey

    def contact_damage(self):
        p = self.player
        if p.iframes > 0:
            return
        for e in self.grid.query(p.x, p.y, 90):
            if not e.alive:
                continue
            rr = e.radius + p.radius * 0.75
            if (e.x - p.x) ** 2 + (e.y - p.y) ** 2 < rr * rr:
                self.hurt_player(e.damage)
                return

    def recycle(self):
        """Enemies left far behind are moved back in front of the player."""
        p = self.player
        lim = DESPAWN_DISTANCE * DESPAWN_DISTANCE
        for e in self.enemies:
            if e.boss or e.owner is not None or not e.alive:
                continue
            if (e.x - p.x) ** 2 + (e.y - p.y) ** 2 > lim:
                e.x, e.y = self.director.spawn_point()
                e.kx = e.ky = 0.0
                if e.type.behavior == "stream":
                    e.state = 1

    # ---------------------------------------------------------------- rendering

    def draw(self, screen):
        cam = self.camera
        self.background.draw(screen, cam, boss=self.boss is not None)
        for z in self.zones:
            z.draw(screen, cam)
        self.fx.draw_under(screen, cam)
        for pk in self.pickups:
            pk.draw(screen, cam)
        for h in self.hazards:
            h.draw(screen, cam)
        for e in self.enemies:
            e.draw_glow(screen, cam)
        for e in self.enemies:
            e.draw(screen, cam)
        for w in self.player.weapons:
            w.draw(screen, cam)
        for pr in self.projectiles:
            pr.draw(screen, cam)
        if not self.dead:
            self.player.draw(screen, cam)
        for b in self.bullets:
            b.draw(screen, cam)
        self.fx.draw_over(screen, cam)

    # ---------------------------------------------------------------- results

    def flux_earned(self):
        """Flux for this run: pickups + kills + time + victory bonus, times greed."""
        base = self.flux + self.kills // 20 + int(self.time / 60 * 8)
        if self.victory:
            base += int(150 * self.stage.difficulty)
        base += 25 * len([b for b in self.bosses_killed if b != "singularity"])
        return int(base * self.player.greed)
