"""SPECTRA test suite. Runs without a window or sound card.

    python -m unittest discover tests

created by jullewz
"""

import os
import sys
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from spectra import upgrades, util  # noqa: E402
from spectra.bosses import BOSSES  # noqa: E402
from spectra.bot import Bot  # noqa: E402
from spectra.config import RUN_LENGTH, WEAPON_SLOTS  # noqa: E402
from spectra.data import ACHIEVEMENTS, CHARACTERS, META, PASSIVES, STAGES  # noqa: E402
from spectra.entities import ENEMY_TYPES, xp_needed  # noqa: E402
from spectra.save import RULES, SaveData, check_achievements  # noqa: E402
from spectra.weapons import WEAPONS  # noqa: E402
from spectra.world import World  # noqa: E402


def setUpModule():
    pygame.init()
    pygame.display.set_mode((1280, 720))


def play(world, seconds, dt=1 / 30):
    """Let the autopilot play, taking level-ups and chests as they come."""
    bot = Bot(world)
    end = world.time + seconds
    while world.time < end and not world.dead and not world.victory:
        world.update(dt, bot.move(dt))
        while world.levelups > 0:
            world.levelups -= 1
            choices = upgrades.roll(world)
            upgrades.apply(world, choices[Bot.choose(world, choices)])
        while world.chests > 0:
            world.chests -= 1
            upgrades.open_chest(world)
    return world


class UtilTests(unittest.TestCase):
    def test_clamp_and_lerp(self):
        self.assertEqual(util.clamp(5, 0, 3), 3)
        self.assertEqual(util.clamp(-1, 0, 3), 0)
        self.assertAlmostEqual(util.lerp(0, 10, 0.25), 2.5)

    def test_wrap_angle(self):
        for a in (-10, -3.5, 0, 3.5, 10):
            w = util.wrap_angle(a)
            self.assertTrue(-3.15 < w <= 3.15)

    def test_fmt_time(self):
        self.assertEqual(util.fmt_time(0), "00:00")
        self.assertEqual(util.fmt_time(754), "12:34")

    def test_spatial_hash(self):
        class P:
            def __init__(self, x, y):
                self.x, self.y = x, y
        h = util.SpatialHash(50)
        near, far = P(10, 10), P(900, 900)
        h.insert(near)
        h.insert(far)
        found = list(h.query(0, 0, 60))
        self.assertIn(near, found)
        self.assertNotIn(far, found)

    def test_xp_curve_grows(self):
        values = [xp_needed(n) for n in range(1, 80)]
        self.assertTrue(all(b > a for a, b in zip(values, values[1:])))


class DataTests(unittest.TestCase):
    def test_ids_unique(self):
        for group in (CHARACTERS, STAGES, PASSIVES, META, ACHIEVEMENTS):
            ids = [x.id for x in group]
            self.assertEqual(len(ids), len(set(ids)))

    def test_every_achievement_has_a_rule(self):
        for a in ACHIEVEMENTS:
            self.assertIn(a.id, RULES)

    def test_characters_start_with_real_weapons(self):
        for c in CHARACTERS:
            self.assertIn(c.weapon, WEAPONS)

    def test_weapon_evolutions_point_to_passives(self):
        pids = {p.id for p in PASSIVES}
        for cls in WEAPONS.values():
            self.assertIn(cls.evo_passive, pids)
            self.assertEqual(len(cls.levels), cls.max_level - 1)
            self.assertTrue(cls.evo_name)


class SaveTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "save.json")
            s = SaveData(path)
            s.flux = 999
            s.meta = {"hull": 2}
            s.achievements = {"first_blood"}
            s.cleared = {"grid"}
            s.save()
            t = SaveData.load(path)
            self.assertEqual(t.flux, 999)
            self.assertEqual(t.meta, {"hull": 2})
            self.assertEqual(t.achievements, {"first_blood"})
            self.assertEqual(t.cleared, {"grid"})

    def test_corrupt_file_gives_fresh_save(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "save.json")
            with open(path, "w") as f:
                f.write("{ not json")
            s = SaveData.load(path)
            self.assertEqual(s.flux, 0)

    def test_buy_and_refund(self):
        s = SaveData()
        s.flux = 10_000
        start = s.flux
        self.assertTrue(s.buy("hull"))
        self.assertTrue(s.buy("hull"))
        self.assertEqual(s.rank("hull"), 2)
        self.assertLess(s.flux, start)
        s.refund_all()
        self.assertEqual(s.flux, start)
        self.assertEqual(s.rank("hull"), 0)

    def test_cannot_overbuy(self):
        s = SaveData()
        s.flux = 10 ** 7
        m = META[0]
        for _ in range(m.max_rank + 3):
            s.buy(m.id)
        self.assertEqual(s.rank(m.id), m.max_rank)

    def test_unlocks(self):
        s = SaveData()
        vex = next(c for c in CHARACTERS if c.id == "vex")
        self.assertFalse(s.char_unlocked(vex))
        s.stats["best_time"] = 400
        new = {a.id for a in check_achievements(s)}
        self.assertIn("survivor", new)
        self.assertTrue(s.char_unlocked(vex))


class WorldTests(unittest.TestCase):
    def test_every_pilot_survives_the_opening(self):
        for c in CHARACTERS:
            w = play(World(c.id, "grid", seed=1), 45)
            self.assertGreater(w.kills, 0, c.id)
            self.assertFalse(w.dead, c.id)

    def test_every_stage_runs(self):
        for s in STAGES:
            w = play(World("nova", s.id, seed=2), 30)
            self.assertGreater(w.time, 29)

    def test_level_up_choices_are_valid(self):
        w = World("nova", "grid", seed=3)
        for _ in range(40):
            choices = upgrades.roll(w)
            self.assertTrue(1 <= len(choices) <= 4)
            self.assertEqual(len({(c.kind, c.id) for c in choices}), len(choices))
            upgrades.apply(w, choices[0])
        self.assertLessEqual(len(w.player.weapons), WEAPON_SLOTS)

    def test_every_weapon_fires_and_evolves(self):
        for wid, cls in WEAPONS.items():
            w = World("nova", "grid", seed=4)
            w.player.weapons.clear()
            w.add_weapon(wid)
            weapon = w.player.weapons[0]
            weapon.level = weapon.max_level
            w.player.passives[cls.evo_passive] = 1
            w.player.recompute()
            rewards = upgrades.open_chest(w)
            self.assertTrue(rewards[0].evolved, wid)
            for i in range(12):
                w.spawn_enemy("brute", w.player.x + 60 + i * 15, w.player.y + 40, force=True)
            play(w, 6)
            self.assertGreater(weapon.damage_done, 0, wid)

    def test_every_boss_can_be_beaten(self):
        for bid, cls in BOSSES.items():
            w = World("nova", "grid", seed=5)
            w.time = 100
            w.spawn_boss(cls)
            boss = w.boss
            self.assertIsNotNone(boss)
            for _ in range(30):
                w.update(1 / 30, (0.0, 0.0))
            w.damage_enemy(boss, boss.hp + 1, force_crit=False, can_crit=False)
            self.assertFalse(boss.alive, bid)
            self.assertIn(bid, w.bosses_killed)
            if bid == "singularity":
                self.assertTrue(w.victory)

    def test_every_enemy_type_spawns(self):
        w = World("nova", "grid", seed=6)
        for kind in ENEMY_TYPES:
            if kind == "segment":
                continue
            w.spawn_enemy(kind, w.player.x + 300, w.player.y, force=True)
        play(w, 5)

    def test_same_seed_same_spawns(self):
        a = World("nova", "grid", seed=42)
        b = World("nova", "grid", seed=42)
        for _ in range(300):
            a.update(1 / 60, (0.3, 0.0))
            b.update(1 / 60, (0.3, 0.0))
        self.assertEqual(len(a.enemies), len(b.enemies))
        self.assertEqual(a.kills, b.kills)

    def test_rendering(self):
        screen = pygame.display.get_surface()
        w = play(World("echo", "nebula", seed=7), 20)
        w.draw(screen)


class SceneTests(unittest.TestCase):
    def test_every_screen_draws(self):
        from spectra.app import App, parse_args
        with tempfile.TemporaryDirectory() as d:
            app = App(parse_args(["--headless", "--save", os.path.join(d, "s.json")]))
            from spectra.scenes.achievements import AchievementsScene
            from spectra.scenes.codex import CodexScene
            from spectra.scenes.game import GameScene
            from spectra.scenes.select import SelectScene
            from spectra.scenes.settings import SettingsScene
            from spectra.scenes.workshop import WorkshopScene
            for cls in (SelectScene, WorkshopScene, CodexScene, AchievementsScene, SettingsScene):
                scene = cls(app)
                for _ in range(3):
                    app.inp.begin_frame()
                    scene.update(1 / 60)
                    scene.draw(app.screen)
            g = GameScene(app, "nova", "grid", seed=1)
            app.scenes = [app.scenes[0], g]
            for _ in range(30):
                app.inp.begin_frame()
                g.update(1 / 60)
                g.draw(app.screen)
            g.world.levelups = 1
            g.open_levelup()
            g.draw(app.screen)
            g.pick(0)
            g.open_pause()
            g.draw(app.screen)
            g.abandon()
            g.draw(app.screen)
            self.assertEqual(app.save.stats["runs"], 1)
            self.assertTrue(os.path.exists(os.path.join(d, "s.json")))
            pygame.quit()
            pygame.init()
            pygame.display.set_mode((1280, 720))


class LongRunTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SPECTRA_LONG"), "set SPECTRA_LONG=1 for the full 12-minute simulation")
    def test_full_run(self):
        w = play(World("nova", "grid", seed=0), RUN_LENGTH + 120)
        self.assertTrue(w.victory or w.dead)


if __name__ == "__main__":
    unittest.main()
