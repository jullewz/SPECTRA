"""A single run: the arena plus its overlays (level-up, chest, pause and results).

created by jullewz
"""

import math
import random

import pygame

from .. import assets, ui, upgrades
from ..bot import Bot
from ..config import (CYAN, DIM, GOLD, GREEN, GREY, HEIGHT, MAGENTA, PANEL, PURPLE, RED, WHITE, WIDTH, YELLOW)
from ..data import PASSIVE_BY_ID
from ..save import check_achievements
from ..util import clamp, ease_out_back, ease_out_cubic, fmt_int, fmt_time, mix, scale
from ..weapons import weapon_icon
from ..world import World
from .base import Scene
from .hud import draw_hud

CARD_W, CARD_H = 270, 340


class GameScene(Scene):
    music = "run"

    def __init__(self, app, char_id, stage_id, seed=None):
        super().__init__(app)
        self.char_id = char_id
        self.stage_id = stage_id
        self.seed = seed if seed is not None else random.randrange(10 ** 9)
        self.world = World(char_id, stage_id, seed=self.seed, meta=self.save.bonuses(),
                           settings=self.save.settings, audio=app.audio)
        self.autoplay = bool(getattr(app.args, "autoplay", False))
        self.bot = Bot(self.world) if self.autoplay else None
        self.mode = "play"
        self.mode_t = 0.0
        self.choices = []
        self.card_index = 0
        self.card_hover = []
        self.rewards = []
        self.reveal = 0
        self.ach_timer = 0.0
        self.new_achievements = []
        self.summary = None
        self.hurt = 0.0
        self.last_hp = self.world.player.hp
        self.pause_menu = None
        self.was_cleared = stage_id in self.save.cleared
        self.result_menu = None
        self.world.show_banner(self.world.stage.name.upper(), "Survive for 12 minutes.", self.world.stage.accent,
                               duration=3.2)

    # ---------------------------------------------------------------- mode switching

    def set_mode(self, mode):
        self.mode = mode
        self.mode_t = 0.0

    def open_levelup(self):
        w = self.world
        w.levelups -= 1
        self.choices = upgrades.roll(w)
        self.card_index = 0
        self.card_hover = [0.0] * len(self.choices)
        self.set_mode("levelup")
        self.sfx("levelup")

    def open_chest(self):
        w = self.world
        w.chests -= 1
        self.rewards = upgrades.open_chest(w)
        self.reveal = 0
        self.set_mode("chest")
        self.sfx("chest")

    def open_pause(self):
        items = [ui.Button((WIDTH // 2 - 150, 0, 300, 50), "RESUME", self.resume_play, CYAN, size=26),
                 ui.Button((WIDTH // 2 - 150, 0, 300, 50), "RESTART", self.restart, YELLOW, size=26),
                 ui.Button((WIDTH // 2 - 150, 0, 300, 50), "ABANDON RUN", self.abandon, MAGENTA, size=26)]
        for i, b in enumerate(items):
            b.rect.topleft = (90, 470 + i * 60)
        self.pause_menu = ui.Menu(items, audio=self.app.audio)
        self.set_mode("pause")
        self.sfx("ui_back")

    def resume_play(self):
        self.set_mode("play")

    def restart(self):
        self.app.replace(GameScene(self.app, self.char_id, self.stage_id))

    def abandon(self):
        self.world.dead = True
        self.world.end_timer = 99
        self.finish()

    def to_menu(self):
        self.app.pop()

    # ---------------------------------------------------------------- end of run

    def finish(self):
        """Fold the run into the save file exactly once."""
        if self.summary is not None:
            return
        w, s = self.world, self.save
        st = s.stats
        earned = w.flux_earned()
        st["runs"] += 1
        st["kills"] += w.kills
        st["time"] += w.time
        st["best_time"] = max(st["best_time"], w.time)
        st["best_level"] = max(st["best_level"], w.player.level)
        st["best_kills"] = max(st["best_kills"], w.kills)
        st["bosses"] += len(w.bosses_killed)
        st["flux_earned"] += earned
        st["evolutions"] += w.evolutions
        if w.victory:
            st["wins"] += 1
            s.cleared.add(w.stage.id)
        else:
            st["deaths"] += 1
        s.flux += earned
        s.seen |= w.seen
        self.new_achievements += check_achievements(s, w)
        s.save()
        self.summary = {
            "victory": w.victory,
            "flux": earned,
            "rows": [
                ("Time survived", fmt_time(w.time)),
                ("Level reached", str(w.player.level)),
                ("Enemies destroyed", fmt_int(w.kills)),
                ("Damage dealt", fmt_int(w.total_damage)),
                ("Damage taken", fmt_int(w.damage_taken)),
                ("Bosses defeated", str(len(w.bosses_killed))),
                ("Evolutions", str(w.evolutions)),
                ("Longest no-hit streak", fmt_time(w.best_no_hit)),
            ],
        }
        items = [ui.Button((0, 0, 260, 56), "RUN AGAIN", self.restart, CYAN, size=28),
                 ui.Button((0, 0, 260, 56), "MAIN MENU", self.to_menu, PURPLE, size=28)]
        items[0].rect.topleft = (WIDTH // 2 - 275, 600)
        items[1].rect.topleft = (WIDTH // 2 + 15, 600)
        self.result_menu = ui.Menu(items, cols=2, audio=self.app.audio)
        self.set_mode("results")

    # ---------------------------------------------------------------- update

    def update(self, dt):
        super().update(dt)
        self.mode_t += dt
        self.hurt = max(0.0, self.hurt - dt * 1.8)
        handler = getattr(self, "update_" + self.mode)
        handler(dt)

    def update_play(self, dt):
        w, inp = self.world, self.inp
        if inp.hit("pause") or inp.hit("back"):
            if not (w.dead or w.victory):
                self.open_pause()
                return
        move = self.bot.move(dt) if self.bot is not None else inp.move()
        w.update(dt, move)
        hp = w.player.hp
        if hp < self.last_hp - 0.5:
            self.hurt = min(1.0, self.hurt + 0.35 + (self.last_hp - hp) / w.player.max_hp * 2)
        self.last_hp = hp

        self.ach_timer += dt
        if self.ach_timer > 2.0:
            self.ach_timer = 0.0
            new = check_achievements(self.save, w)
            if new:
                self.new_achievements += new
                for a in new:
                    w.toast(f"Achievement: {a.name}", GOLD)
                self.sfx("pickup")
                self.save.save()

        if w.dead or w.victory:
            if w.end_timer > 2.6:
                self.finish()
            return
        if w.chests > 0:
            self.open_chest()
        elif w.levelups > 0:
            self.open_levelup()

    def pick(self, index):
        c = self.choices[index]
        upgrades.apply(self.world, c)
        self.sfx("ui_select")
        self.after_overlay()

    def after_overlay(self):
        w = self.world
        if w.chests > 0:
            self.open_chest()
        elif w.levelups > 0:
            self.open_levelup()
        else:
            self.set_mode("play")

    def update_levelup(self, dt):
        inp, p = self.inp, self.world.player
        for i in range(len(self.card_hover)):
            self.card_hover[i] = clamp(self.card_hover[i] + (dt * 6 if i == self.card_index else -dt * 6), 0, 1)
        if self.mode_t < 0.35:
            return
        if self.bot is not None and self.mode_t > 0.5:
            self.pick(Bot.choose(self.world, self.choices))
            return
        rects = self.card_rects()
        if inp.mouse_moved or inp.clicked:
            for i, r in enumerate(rects):
                if r.collidepoint(inp.mouse_pos):
                    if i != self.card_index:
                        self.card_index = i
                        self.sfx("ui_move")
                    if inp.clicked:
                        self.pick(i)
                        return
        if inp.hit("left"):
            self.card_index = (self.card_index - 1) % len(self.choices)
            self.sfx("ui_move")
        if inp.hit("right"):
            self.card_index = (self.card_index + 1) % len(self.choices)
            self.sfx("ui_move")
        if inp.hit("confirm"):
            self.pick(self.card_index)
            return
        if inp.hit("reroll"):
            if p.rerolls > 0:
                p.rerolls -= 1
                self.choices = upgrades.roll(self.world, len(self.choices))
                self.card_hover = [0.0] * len(self.choices)
                self.card_index = min(self.card_index, len(self.choices) - 1)
                self.mode_t = 0.2
                self.sfx("whoosh")
            else:
                self.sfx("ui_back")
        if inp.hit("skip"):
            self.world.flux += 5
            self.sfx("ui_back")
            self.after_overlay()

    def update_chest(self, dt):
        if self.reveal < len(self.rewards):
            if self.mode_t > 0.9 + self.reveal * 0.45:
                self.reveal += 1
                r = self.rewards[self.reveal - 1]
                self.sfx("evolve" if r.evolved else "pickup")
            if self.inp.hit("confirm") and self.mode_t > 0.5:
                self.reveal = len(self.rewards)
            return
        done = self.inp.hit("confirm") or self.inp.clicked or self.inp.hit("back")
        if done or (self.bot is not None and self.mode_t > 2.2 + len(self.rewards) * 0.45):
            self.sfx("ui_select")
            self.after_overlay()

    def update_pause(self, dt):
        self.pause_menu.update(dt)
        if self.inp.hit("pause") or self.inp.hit("back"):
            self.resume_play()
            return
        self.pause_menu.handle(self.inp)

    def update_results(self, dt):
        w = self.world
        w.fx.update(dt)
        w.camera.update(dt)
        self.result_menu.update(dt)
        if self.mode_t > 0.8:
            self.result_menu.handle(self.inp)

    # ---------------------------------------------------------------- drawing

    def draw(self, screen):
        w = self.world
        w.draw(screen)
        if self.save.settings["bloom"]:
            self.app.post.bloom(screen)
        self.app.post.draw_vignette(screen)
        p = w.player
        low = clamp(1 - p.hp / max(1, p.max_hp) / 0.3, 0, 1) if not w.dead else 0
        amount = max(self.hurt, low * (0.35 + 0.15 * math.sin(self.t * 5)))
        if amount > 0.02:
            self.app.post.draw_hurt(screen, amount)
        if self.mode != "results":
            draw_hud(screen, w, self.t, self.app.fps_value if self.save.settings.get("fps") else None,
                     overlay=self.mode != "play")
        if w.victory and self.mode == "play":
            k = clamp(w.end_timer / 1.2, 0, 1)
            ui.title(screen, "VICTORY", 110, scale(GOLD, k), (WIDTH // 2, HEIGHT // 2 - 40), GOLD)
        elif w.dead and self.mode == "play":
            k = clamp(w.end_timer / 1.2, 0, 1)
            ui.dim(screen, 0.5 * k)
            ui.title(screen, "SIGNAL LOST", 100, scale(RED, k), (WIDTH // 2, HEIGHT // 2 - 40), RED)
        getattr(self, "draw_" + self.mode)(screen)
        if self.autoplay and self.mode != "results":
            assets.text(screen, "AUTOPLAY", 18, GREY, (WIDTH - 16, HEIGHT - 12), "bottomright", shadow=False)

    def draw_play(self, screen):
        pass

    # ---- level up

    def card_rects(self):
        n = len(self.choices)
        gap = 26
        total = n * CARD_W + (n - 1) * gap
        x0 = (WIDTH - total) // 2
        return [pygame.Rect(x0 + i * (CARD_W + gap), 210, CARD_W, CARD_H) for i in range(n)]

    def draw_levelup(self, screen):
        k = ease_out_cubic(clamp(self.mode_t / 0.3, 0, 1))
        ui.dim(screen, 0.62 * k)
        ui.title(screen, "LEVEL UP", 82, mix(CYAN, WHITE, 0.2), (WIDTH // 2, 110 - (1 - k) * 30), CYAN)
        assets.text(screen, f"Level {self.world.player.level}  ·  choose an upgrade", 24, GREY, (WIDTH // 2, 162),
                    "center")
        for i, (c, r) in enumerate(zip(self.choices, self.card_rects())):
            appear = ease_out_back(clamp((self.mode_t - 0.06 * i) / 0.35, 0, 1))
            if appear <= 0.01:
                continue
            h = ease_out_cubic(self.card_hover[i]) if i < len(self.card_hover) else 0
            rr = r.move(0, int((1 - appear) * 120 - h * 14))
            self.draw_card(screen, c, rr, h, appear)
        p = self.world.player
        tips = ["LEFT / RIGHT choose", "ENTER take"]
        tips.append(f"R reroll ({p.rerolls})" if p.rerolls > 0 else "no rerolls")
        tips.append("X skip (+5 flux)")
        ui.hint(screen, "    ".join(tips), 588)

    def draw_card(self, screen, c, r, h, appear):
        col = GOLD if c.evolved else c.color
        ui.panel(screen, r, mix(scale(col, 0.5), col, h), mix(PANEL, scale(col, 0.14), h), int(235 * min(1, appear)),
                 18, glow=0.4 + 0.8 * h)
        cx = r.centerx
        assets.blit_glow(screen, cx, r.y + 82, 70, col, 0.25 + 0.3 * h)
        ic = assets.icon(c.id, col, 88, evolved=c.evolved)
        screen.blit(ic, (cx - 44, r.y + 38))
        if c.tag:
            tag_col = YELLOW if c.new else GREY
            assets.text(screen, c.tag, 20, tag_col, (cx, r.y + 26), "center", bold=True)
        kind = {"weapon": "WEAPON", "passive": "MODULE", "heal": "SUPPLY", "flux": "SUPPLY"}[c.kind]
        assets.text(screen, kind, 16, scale(col, 0.9), (cx, r.y + 144), "center", bold=True, shadow=False)
        assets.text(screen, c.name, 30 if assets.text_width(c.name, 30, True) < CARD_W - 24 else 24, WHITE,
                    (cx, r.y + 172), "center", bold=True)
        lines = assets.wrap(c.desc, 20, CARD_W - 36)
        y = r.y + 202
        for line in lines[:5]:
            assets.text(screen, line, 20, mix(GREY, WHITE, 0.4), (cx, y), "midtop", shadow=False)
            y += 24
        if c.kind == "weapon" and not c.new:
            wpn = self.world.player.weapon(c.id)
            if wpn is not None:
                n = wpn.max_level
                pw = n * 14
                ui.pips(screen, cx - pw // 2, r.bottom - 28, c.level, n, col, 5, 4)
        elif c.kind == "passive":
            n = PASSIVE_BY_ID[c.id].max_level
            ui.pips(screen, cx - n * 7, r.bottom - 28, c.level, n, col, 5, 4)
        if c.kind == "passive" and self.partner_of(c.id):
            assets.text(screen, f"evolves {self.partner_of(c.id)}", 17, GOLD, (cx, r.bottom - 46), "center",
                        shadow=False)

    def partner_of(self, pid):
        for w in self.world.player.weapons:
            if w.evo_passive == pid and not w.evolved:
                return w.name
        return None

    # ---- chest

    def draw_chest(self, screen):
        k = ease_out_cubic(clamp(self.mode_t / 0.3, 0, 1))
        ui.dim(screen, 0.7 * k)
        evo = any(r.evolved for r in self.rewards)
        col = GOLD if not evo else mix(GOLD, MAGENTA, 0.5 + 0.5 * math.sin(self.t * 3))
        cx, cy = WIDTH // 2, 200
        open_k = clamp((self.mode_t - 0.25) / 0.6, 0, 1)
        for i in range(12):
            a = self.t * 0.6 + i * math.tau / 12
            ln = 140 + 60 * open_k
            pygame.draw.line(screen, scale(col, 0.25 * open_k), (cx, cy),
                             (cx + math.cos(a) * ln, cy + math.sin(a) * ln), 6)
        assets.blit_glow(screen, cx, cy, 110 + 40 * open_k, col, 0.45 + 0.4 * open_k)
        size = int(110 + 16 * math.sin(self.t * 4) * (1 - open_k))
        screen.blit(assets.icon("chest", col, size, frame=False), (cx - size // 2, cy - size // 2))
        ui.title(screen, "EVOLUTION!" if evo else "SUPPLY CACHE", 60, mix(col, WHITE, 0.2), (cx, 330), col)
        n = len(self.rewards)
        rw, gap = 220, 18
        total = n * rw + (n - 1) * gap
        x0 = (WIDTH - total) // 2
        for i, rew in enumerate(self.rewards[:self.reveal]):
            r = pygame.Rect(x0 + i * (rw + gap), 390, rw, 200)
            ui.panel(screen, r, rew.color, mix(PANEL, scale(rew.color, 0.12), 0.6), 235, 16, glow=0.8)
            ic = assets.icon(rew.icon, rew.color, 64, evolved=rew.evolved)
            screen.blit(ic, (r.centerx - 32, r.y + 16))
            assets.text(screen, rew.headline, 16, scale(rew.color, 0.9), (r.centerx, r.y + 98), "center", bold=True)
            nm = rew.name
            size = 24 if assets.text_width(nm, 24, True) < rw - 16 else 19
            assets.text(screen, nm, size, WHITE, (r.centerx, r.y + 124), "center", bold=True)
            assets.text_block(screen, rew.detail, 17, GREY, r.x + 14, r.y + 146, rw - 28, 2)
        if self.reveal >= n:
            ui.hint(screen, "ENTER to continue", 618)

    # ---- pause

    def draw_pause(self, screen):
        ui.dim(screen, 0.72)
        w, p = self.world, self.world.player
        ui.title(screen, "PAUSED", 80, WHITE, (WIDTH // 2, 80), PURPLE)
        assets.text(screen, f"{w.char.name} · {w.stage.name} · {fmt_time(w.time)} · level {p.level}", 22, GREY,
                    (WIDTH // 2, 132), "center")
        # build
        box = pygame.Rect(70, 170, 540, 280)
        ui.panel(screen, box, CYAN, PANEL, 225, 16)
        assets.text(screen, "WEAPONS", 18, CYAN, (box.x + 20, box.y + 14), bold=True)
        for i, wpn in enumerate(p.weapons):
            x = box.x + 20 + (i % 2) * 260
            y = box.y + 44 + (i // 2) * 52
            screen.blit(weapon_icon(wpn, 42), (x, y))
            assets.text(screen, wpn.title, 20, GOLD if wpn.evolved else WHITE, (x + 52, y + 2), bold=True)
            ui.pips(screen, x + 53, y + 30, wpn.level, wpn.max_level, wpn.tint, 4, 3)
        assets.text(screen, "MODULES", 18, CYAN, (box.x + 20, box.y + 208), bold=True)
        for i, (pid, lv) in enumerate(p.passives.items()):
            ps = PASSIVE_BY_ID[pid]
            x = box.x + 20 + i * 84
            screen.blit(assets.icon(pid, ps.color, 34), (x, box.y + 232))
            assets.text(screen, str(lv), 18, ps.color, (x + 40, box.y + 248), "midleft", bold=True)
        # stats
        sbox = pygame.Rect(650, 170, 560, 470)
        ui.panel(screen, sbox, PURPLE, PANEL, 225, 16)
        assets.text(screen, "PILOT STATS", 18, PURPLE, (sbox.x + 20, sbox.y + 14), bold=True)
        for i, (name, value) in enumerate(p.stat_lines()):
            col_x = sbox.x + 24 + (i % 2) * 272
            y = sbox.y + 50 + (i // 2) * 44
            assets.text(screen, name, 19, GREY, (col_x, y), shadow=False)
            assets.text(screen, value, 22, WHITE, (col_x + 246, y), "topright", bold=True)
            pygame.draw.line(screen, (36, 36, 60), (col_x, y + 32), (col_x + 246, y + 32), 1)
        self.pause_menu.draw(screen)
        ui.hint(screen, "ESC to resume", HEIGHT - 40)

    # ---- results

    def draw_results(self, screen):
        k = ease_out_cubic(clamp(self.mode_t / 0.6, 0, 1))
        ui.dim(screen, 0.78 * k)
        s = self.summary
        col = GOLD if s["victory"] else RED
        word = "VICTORY" if s["victory"] else "SIGNAL LOST"
        ui.title(screen, word, 92, mix(col, WHITE, 0.15), (WIDTH // 2, 86 - (1 - k) * 30), col)
        w = self.world
        sub = (f"{w.stage.name} cleared with {w.char.name}" if s["victory"]
               else f"{w.char.name} fell on {w.stage.name}")
        assets.text(screen, sub, 24, GREY, (WIDTH // 2, 142), "center")
        box = pygame.Rect(WIDTH // 2 - 470, 178, 560, 390)
        ui.panel(screen, box, col, PANEL, 230, 18)
        for i, (name, value) in enumerate(s["rows"]):
            appear = clamp((self.mode_t - 0.3 - i * 0.07) / 0.25, 0, 1)
            if appear <= 0:
                continue
            y = box.y + 24 + i * 38
            assets.text(screen, name, 22, scale(GREY, appear), (box.x + 30, y), shadow=False)
            assets.text(screen, value, 26, scale(WHITE, appear), (box.right - 30, y - 2), "topright", bold=True)
            pygame.draw.line(screen, (36, 36, 60), (box.x + 30, y + 31), (box.right - 30, y + 31), 1)
        y = box.bottom - 40
        screen.blit(assets.icon("flux", GOLD, 34, frame=False), (box.x + 28, y - 4))
        shown = int(s["flux"] * clamp((self.mode_t - 0.9) / 1.0, 0, 1))
        assets.text(screen, f"+{shown:,} flux", 30, GOLD, (box.x + 72, y + 13), "midleft", bold=True)
        assets.text(screen, f"total {self.save.flux:,}", 20, GREY, (box.right - 30, y + 13), "midright",
                    shadow=False)
        # side: build + achievements
        side = pygame.Rect(box.right + 20, 178, 360, 390)
        ui.panel(screen, side, CYAN, PANEL, 230, 18)
        assets.text(screen, "FINAL BUILD", 18, CYAN, (side.x + 20, side.y + 16), bold=True)
        for i, wpn in enumerate(w.player.weapons):
            screen.blit(weapon_icon(wpn, 46), (side.x + 20 + (i % 3) * 110, side.y + 46 + (i // 3) * 64))
            assets.text(screen, str(wpn.level) if not wpn.evolved else "EVO", 18,
                        GOLD if wpn.evolved else WHITE, (side.x + 72 + (i % 3) * 110, side.y + 70 + (i // 3) * 64),
                        "midleft", bold=True)
        assets.text(screen, "ACHIEVEMENTS", 18, GOLD, (side.x + 20, side.y + 188), bold=True)
        if self.new_achievements:
            for i, a in enumerate(self.new_achievements[:5]):
                star = assets.transform(assets.SHAPES["star"], side.x + 28, side.y + 231 + i * 30, 8, -1.5708)
                pygame.draw.polygon(screen, GOLD, star)
                assets.text(screen, a.name, 21, WHITE, (side.x + 44, side.y + 218 + i * 30), bold=True)
                assets.text(screen, f"+{a.reward}", 19, GOLD, (side.right - 20, side.y + 220 + i * 30),
                            "topright", shadow=False)
            if len(self.new_achievements) > 5:
                assets.text(screen, f"and {len(self.new_achievements) - 5} more", 18, GREY,
                            (side.x + 20, side.y + 370), shadow=False)
        else:
            assets.text(screen, "None this run.", 20, DIM, (side.x + 20, side.y + 218), shadow=False)
        if self.mode_t > 0.6:
            self.result_menu.draw(screen)
        unlocked_txt = self.unlock_line()
        if unlocked_txt:
            assets.text(screen, unlocked_txt, 22, GREEN, (WIDTH // 2, 680), "center", bold=True)

    def unlock_line(self):
        from ..data import CHARACTERS, STAGES
        names = [c.name for c in CHARACTERS if c.unlock in {a.id for a in self.new_achievements}]
        if self.summary and self.summary["victory"] and not self.was_cleared:
            names += [s.name for s in STAGES if s.unlock == self.world.stage.id]
        return ("Unlocked: " + ", ".join(names)) if names else ""
