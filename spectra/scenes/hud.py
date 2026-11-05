"""The in-run heads-up display: XP, health, timer, loadout, boss bar, banners, toasts and
off-screen markers.

created by jullewz
"""

import math

import pygame

from .. import assets, ui
from ..config import (CYAN, GOLD, GREEN, GREY, HEIGHT, PASSIVE_SLOTS, RED, RUN_LENGTH, WEAPON_SLOTS, WHITE, WIDTH,
                      YELLOW)
from ..data import PASSIVE_BY_ID
from ..util import clamp, fmt_time, mix, scale
from ..weapons import weapon_icon


def draw_hud(screen, world, t, show_fps=None, overlay=False):
    p = world.player
    # ---- experience bar across the top
    frac = p.xp / p.xp_next if p.xp_next else 0
    pygame.draw.rect(screen, (10, 10, 24), (0, 0, WIDTH, 14))
    ui.bar(screen, (4, 3, WIDTH - 8, 9), frac, mix((80, 160, 255), (120, 255, 220), frac), back=(24, 24, 48))
    lvl = f"LV {p.level}"
    w = assets.text_width(lvl, 24, True) + 20
    ui.panel(screen, (WIDTH - w - 10, 18, w, 28), CYAN, (10, 14, 30), 230, 10)
    assets.text(screen, lvl, 24, WHITE, (WIDTH - 10 - w // 2, 32), "center", bold=True)

    # ---- health
    hp_frac = clamp(p.hp / p.max_hp, 0, 1)
    low = hp_frac < 0.3
    col = mix(YELLOW, GREEN, (hp_frac - 0.3) / 0.7) if not low else mix(RED, WHITE, 0.4 + 0.4 * math.sin(t * 10))
    ui.bar(screen, (16, 22, 250, 16), hp_frac, col, back=(36, 14, 26), border=scale(col, 0.6))
    assets.text(screen, f"{int(math.ceil(p.hp))} / {int(p.max_hp)}", 19, WHITE, (141, 30), "center", bold=True)

    # ---- loadout
    x, y = 16, 48
    for i in range(WEAPON_SLOTS):
        if i < len(p.weapons):
            wpn = p.weapons[i]
            screen.blit(weapon_icon(wpn, 38), (x + i * 42, y))
            ui.pips(screen, x + i * 42 + 2, y + 40, wpn.level, wpn.max_level, GOLD if wpn.evolved else wpn.tint, 3, 1)
        else:
            pygame.draw.rect(screen, (28, 28, 46), (x + i * 42, y, 38, 38), 1, border_radius=8)
    y += 50
    items = list(p.passives.items())
    for i in range(PASSIVE_SLOTS):
        if i < len(items):
            pid, lv = items[i]
            ps = PASSIVE_BY_ID[pid]
            screen.blit(assets.icon(pid, ps.color, 30), (x + i * 42 + 4, y))
            ui.pips(screen, x + i * 42 + 6, y + 32, lv, ps.max_level, ps.color, 3, 1)
        else:
            pygame.draw.rect(screen, (24, 24, 40), (x + i * 42 + 4, y, 30, 30), 1, border_radius=6)

    # ---- timer, kills, flux
    remaining = RUN_LENGTH - world.time
    tcol = WHITE if remaining > 30 or world.director.final else mix(WHITE, RED, 0.5 + 0.5 * math.sin(t * 8))
    assets.text(screen, fmt_time(world.time), 44, tcol, (WIDTH // 2, 38), "center", bold=True)
    assets.text(screen, world.stage.name.upper(), 16, scale(world.stage.accent, 0.9), (WIDTH // 2, 64), "center",
                shadow=False)
    rx = WIDTH - 20
    assets.text(screen, f"{world.kills:,}", 26, WHITE, (rx, 58), "topright", bold=True)
    kw = assets.text_width(f"{world.kills:,}", 26, True)
    sk = assets.shape_sprite("triangle", 8, RED, -math.pi / 2)
    assets.blit_center(screen, sk, rx - kw - 14, 68)
    assets.text(screen, f"{world.flux:,}", 26, GOLD, (rx, 86), "topright", bold=True)
    fw = assets.text_width(f"{world.flux:,}", 26, True)
    screen.blit(assets.icon("flux", GOLD, 22, frame=False), (rx - fw - 26, 86))

    # ---- boss bar
    boss = world.boss
    if boss is not None and boss.alive and not overlay:
        bw = 640
        bx = WIDTH // 2 - bw // 2
        by = HEIGHT - 52
        assets.text(screen, boss.title, 24, mix(boss.color, WHITE, 0.4), (WIDTH // 2, by - 14), "center", bold=True)
        ui.bar(screen, (bx, by, bw, 16), boss.hp / boss.max_hp, boss.color, back=(30, 12, 26),
               border=scale(boss.color, 0.7))
        if boss.enraged:
            assets.text(screen, "ENRAGED", 16, RED, (bx + bw, by - 14), "midright", bold=True)

    # ---- off-screen markers: chests and the boss
    cam = world.camera
    marks = [(pk.x, pk.y, GOLD) for pk in world.pickups if pk.kind == "chest"]
    if boss is not None and boss.alive:
        marks.append((boss.x, boss.y, boss.color))
    for mx, my, col in marks:
        if cam.on_screen(mx, my, -10):
            continue
        sx, sy = mx - cam.cx, my - cam.cy
        cx, cy = WIDTH / 2, HEIGHT / 2
        ang = math.atan2(sy - cy, sx - cx)
        ex = clamp(cx + math.cos(ang) * 2000, 30, WIDTH - 30)
        ey = clamp(cy + math.sin(ang) * 2000, 130, HEIGHT - 80)
        pulse = 0.6 + 0.4 * math.sin(t * 6)
        ui.arrow(screen, ex, ey, ang, mix(col, WHITE, 0.3 * pulse), 14)

    # ---- banner
    b = world.banner
    if b is not None and not overlay:
        k = b["t"]
        a = clamp(min(k / 0.3, (b["dur"] - k) / 0.6), 0, 1)
        if a > 0.02:
            y = 200 if not b["small"] else 170
            size = 46 if b["small"] else 76
            ui.title(screen, b["title"], size, scale(b["color"], a), (WIDTH // 2, y), scale(b["color"], a * 0.9))
            if b["sub"]:
                assets.text(screen, b["sub"], 24, scale(WHITE, 0.4 + 0.6 * a), (WIDTH // 2, y + size * 0.62), "center")

    # ---- toasts (achievements etc.)
    for i, (txt, col, life) in enumerate(world.toasts):
        slide = clamp(min(life * 3, (3.0 - life) * 4), 0, 1)
        w = assets.text_width(txt, 22, True) + 64
        x = WIDTH - (w + 16) * slide
        r = pygame.Rect(int(x), 128 + i * 52, w, 44)
        ui.panel(screen, r, col, (12, 12, 26), 235, 12, glow=0.6)
        screen.blit(assets.icon("fortune", GOLD, 30, frame=False), (r.x + 10, r.y + 7))
        assets.text(screen, txt, 22, WHITE, (r.x + 48, r.centery), "midleft", bold=True)

    if show_fps is not None:
        assets.text(screen, f"{show_fps:.0f} fps · {len(world.enemies)} enemies", 18, GREY, (16, HEIGHT - 12),
                    "bottomleft", shadow=False)
    if world.gem_combo >= 12:
        assets.text(screen, f"x{world.gem_combo}", 22, YELLOW, (int(p.x - cam.cx), int(p.y - cam.cy) - 38), "center",
                    bold=True)
