"""Window, main loop, scene stack and command line.

created by jullewz
"""

import argparse
import os
import sys
import time

from .config import AUTHOR, FPS, HEIGHT, MAX_DT, TITLE, VERSION, WIDTH


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="spectra", description=f"{TITLE} {VERSION} - a neon survival roguelite. "
                                                             f"created by {AUTHOR}")
    p.add_argument("--fullscreen", action="store_true", help="start in fullscreen")
    p.add_argument("--windowed", action="store_true", help="start in a window even if the save says fullscreen")
    p.add_argument("--mute", action="store_true", help="disable all audio")
    p.add_argument("--autoplay", action="store_true", help="let the built-in pilot AI play your runs")
    p.add_argument("--scene", default="title",
                   choices=["title", "select", "game", "workshop", "codex", "achievements", "settings"],
                   help="screen to open first")
    p.add_argument("--char", default=None, help="pilot for --scene game (nova, vex, titan, echo, kira)")
    p.add_argument("--stage", default=None, help="stage for --scene game (grid, nebula, aurora)")
    p.add_argument("--seed", type=int, default=None, help="random seed for --scene game")
    p.add_argument("--save", default=None, help="path of the save file to use")
    p.add_argument("--seconds", type=float, default=0, help="quit after this many seconds of game time")
    p.add_argument("--shots", default=None, help="folder to write a screenshot into every --shot-every seconds")
    p.add_argument("--shot-every", type=float, default=10.0)
    p.add_argument("--headless", action="store_true", help="no window, no sound, fixed time step (for testing)")
    p.add_argument("--bench", action="store_true", help="print frame-time statistics at exit")
    return p.parse_args(argv)


class App:
    def __init__(self, args):
        self.args = args
        if args.headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        self.pg = pygame
        pygame.init()

        from .audio import Audio
        from .fx import PostFX
        from .inputs import Input
        from .save import SaveData, data_dir
        from .scenes.base import MenuBackground

        self.dir = data_dir()
        path = args.save or os.path.join(self.dir, "save.json")
        self.save = SaveData.load(path)
        if args.fullscreen:
            self.save.settings["fullscreen"] = True
        if args.windowed:
            self.save.settings["fullscreen"] = False
        self.screen = None
        self.set_fullscreen(self.save.settings["fullscreen"] and not args.headless)
        pygame.display.set_caption(f"{TITLE}  -  created by {AUTHOR}")
        self.set_icon()
        self.clock = pygame.time.Clock()
        self.audio = Audio(self.save.settings, self.dir, enabled=not (args.mute or args.headless))
        self.inp = Input()
        self.post = PostFX()
        self.menu_bg = MenuBackground()
        self.scenes = []
        self.running = True
        self.fps_value = 0.0
        self.game_time = 0.0
        self.frame_times = []
        self.push(self.first_scene())

    # ---------------------------------------------------------------- window

    def set_fullscreen(self, on):
        pg = self.pg
        flags = pg.SCALED if hasattr(pg, "SCALED") else 0
        if on:
            flags |= pg.FULLSCREEN
        try:
            self.screen = pg.display.set_mode((WIDTH, HEIGHT), flags)
        except pg.error:
            self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        self.save.settings["fullscreen"] = bool(on)

    def set_icon(self):
        import math
        from . import assets
        from .config import CYAN
        pg = self.pg
        surf = pg.Surface((64, 64), pg.SRCALPHA)
        assets.blit_glow(surf, 32, 32, 30, CYAN, 0.7)
        assets.blit_center(surf, assets.shape_sprite("ship", 20, CYAN, -math.pi / 2), 32, 32)
        try:
            pg.display.set_icon(surf)
        except (pg.error, AttributeError):
            pass

    def screenshot(self, path=None):
        if path is None:
            folder = os.path.join(self.dir, "screenshots")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, time.strftime("spectra-%Y%m%d-%H%M%S.png"))
        self.pg.image.save(self.screen, path)
        return path

    # ---------------------------------------------------------------- scenes

    def first_scene(self):
        a = self.args
        from .scenes.title import TitleScene
        name = a.scene
        if name == "title":
            return TitleScene(self)
        self.scenes.append(TitleScene(self))  # so ESC leads back to the title
        if name == "game":
            from .scenes.game import GameScene
            return GameScene(self, a.char or self.save.last_char, a.stage or self.save.last_stage, seed=a.seed)
        module = __import__(f"spectra.scenes.{name}", fromlist=["x"])
        cls = getattr(module, name.capitalize() + "Scene")
        return cls(self)

    @property
    def scene(self):
        return self.scenes[-1] if self.scenes else None

    def push(self, scene):
        self.scenes.append(scene)
        scene.enter()

    def pop(self):
        if self.scenes:
            self.scenes.pop()
        if self.scenes:
            self.scenes[-1].resume()
        else:
            self.running = False

    def replace(self, scene):
        if self.scenes:
            self.scenes.pop()
        self.push(scene)

    # ---------------------------------------------------------------- loop

    def run(self):
        pg = self.pg
        a = self.args
        fixed = a.headless
        next_shot = a.shot_every if a.shots else None
        if a.shots:
            os.makedirs(a.shots, exist_ok=True)
        try:
            while self.running:
                if fixed:
                    self.clock.tick()
                    dt = 1.0 / FPS
                else:
                    dt = min(MAX_DT, self.clock.tick(FPS) / 1000.0)
                self.fps_value = self.clock.get_fps()
                t0 = time.perf_counter()
                self.inp.begin_frame()
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        self.running = False
                    self.inp.handle(event)
                if self.inp.hit("fullscreen"):
                    self.set_fullscreen(not self.save.settings["fullscreen"])
                if self.inp.hit("fps"):
                    self.save.settings["fps"] = not self.save.settings["fps"]
                if self.inp.hit("screenshot"):
                    self.screenshot()
                    self.audio.play("pickup", 0.6)
                scene = self.scene
                if scene is None:
                    break
                scene.update(dt)
                if self.scene is not None:
                    self.scene.draw(self.screen)
                pg.display.flip()
                self.audio.update()
                self.frame_times.append(time.perf_counter() - t0)
                self.game_time += dt
                if next_shot is not None and self.game_time >= next_shot:
                    self.screenshot(os.path.join(a.shots, f"shot-{int(self.game_time):05d}.png"))
                    next_shot += a.shot_every
                if a.seconds and self.game_time >= a.seconds:
                    self.running = False
        finally:
            self.save.save()
            if a.bench and self.frame_times:
                ft = sorted(self.frame_times)
                avg = sum(ft) / len(ft)
                print(f"frames {len(ft)}  avg {avg * 1000:.2f} ms  p95 {ft[int(len(ft) * 0.95)] * 1000:.2f} ms  "
                      f"max {ft[-1] * 1000:.2f} ms")
            pg.quit()


def main(argv=None):
    args = parse_args(argv)
    if sys.version_info < (3, 8):
        print("SPECTRA needs Python 3.8 or newer.")
        return 1
    try:
        import pygame  # noqa: F401
    except ImportError:
        print("SPECTRA needs pygame. Install it with:  pip install pygame-ce")
        return 1
    App(args).run()
    return 0
