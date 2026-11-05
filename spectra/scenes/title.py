"""The title screen. A real game plays itself behind the menu.

created by jullewz
"""

import random

from .. import assets, ui, upgrades
from ..bot import Bot
from ..config import AUTHOR, CYAN, GOLD, GREY, MAGENTA, PURPLE, SUBTITLE, TEAL, VERSION, WHITE, WIDTH, YELLOW
from ..data import CHARACTERS, STAGES
from ..world import World
from .base import Scene


class TitleScene(Scene):
    music = "title"

    def __init__(self, app):
        super().__init__(app)
        self.demo = None
        self.bot = None
        self.new_demo()
        labels = [("PLAY", self.play, CYAN), ("WORKSHOP", self.workshop, GOLD), ("CODEX", self.codex, TEAL),
                  ("ACHIEVEMENTS", self.achievements, YELLOW), ("SETTINGS", self.settings, PURPLE),
                  ("QUIT", self.quit, MAGENTA)]
        self.buttons = [ui.Button((WIDTH // 2 - 160, 306 + i * 56, 320, 46), label, action, color, size=28)
                        for i, (label, action, color) in enumerate(labels)]
        self.menu = ui.Menu(self.buttons, audio=app.audio)

    def new_demo(self):
        rng = random.Random()
        chars = [c for c in CHARACTERS if self.save.char_unlocked(c)] or CHARACTERS[:1]
        stages = [s for s in STAGES if self.save.stage_unlocked(s)] or STAGES[:1]
        self.demo = World(rng.choice(chars).id, rng.choice(stages).id, seed=rng.randint(0, 10 ** 6),
                          settings=self.save.settings, demo=True)
        self.demo.time = rng.choice([0, 60, 150])  # start some demos mid-run for variety
        self.bot = Bot(self.demo)
        self.demo_t = 0.0

    # ---------------------------------------------------------------- actions

    def play(self):
        from .select import SelectScene
        self.app.push(SelectScene(self.app))

    def workshop(self):
        from .workshop import WorkshopScene
        self.app.push(WorkshopScene(self.app))

    def codex(self):
        from .codex import CodexScene
        self.app.push(CodexScene(self.app))

    def achievements(self):
        from .achievements import AchievementsScene
        self.app.push(AchievementsScene(self.app))

    def settings(self):
        from .settings import SettingsScene
        self.app.push(SettingsScene(self.app))

    def quit(self):
        self.app.running = False

    # ---------------------------------------------------------------- loop

    def update(self, dt):
        super().update(dt)
        w = self.demo
        w.update(dt, self.bot.move(dt))
        while w.levelups > 0:
            w.levelups -= 1
            choices = upgrades.roll(w)
            upgrades.apply(w, choices[Bot.choose(w, choices)])
        while w.chests > 0:
            w.chests -= 1
            upgrades.open_chest(w)
        self.demo_t += dt
        if self.demo_t > 75 or w.victory:
            self.new_demo()
        self.menu.update(dt)
        self.menu.handle(self.inp)
        if self.inp.hit("back"):
            self.app.running = False

    def draw(self, screen):
        self.demo.draw(screen)
        if self.save.settings["bloom"]:
            self.app.post.bloom(screen)
        ui.dim(screen, 0.55)
        self.app.post.draw_vignette(screen)
        wob = 4 * __import__("math").sin(self.t * 1.3)
        ui.title(screen, "SPECTRA", 128, WHITE, (WIDTH // 2 + 3, 150 + wob), (255, 60, 160), spread=6)
        ui.title(screen, "SPECTRA", 128, WHITE, (WIDTH // 2 - 3, 150 + wob), (60, 200, 255), spread=6)
        assets.text(screen, SUBTITLE.upper(), 26, (190, 200, 255), (WIDTH // 2, 232), "center")
        assets.text(screen, f"created by {AUTHOR}", 24, (255, 140, 220), (WIDTH // 2, 262), "center", bold=True)
        self.menu.draw(screen)
        assets.text(screen, f"v{VERSION}  ·  created by {AUTHOR}", 18, GREY, (16, 700), "bottomleft", shadow=False)
        screen.blit(assets.icon("flux", GOLD, 30, frame=False), (WIDTH - 170, 680))
        assets.text(screen, f"{self.save.flux:,} flux", 22, GOLD, (WIDTH - 136, 695), "midleft")
        ui.hint(screen, "arrows / WASD to move  ·  ENTER to select  ·  works with a gamepad", 712 - 40)
