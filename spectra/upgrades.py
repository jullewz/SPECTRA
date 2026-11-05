"""Level-up offers, chest rewards and weapon evolutions.

created by jullewz
"""

from dataclasses import dataclass

from .config import GOLD, GREEN, PASSIVE_SLOTS, WEAPON_SLOTS
from .data import PASSIVE_BY_ID, PASSIVES
from .weapons import WEAPONS


@dataclass
class Choice:
    kind: str        # "weapon", "passive", "heal" or "flux"
    id: str
    name: str
    desc: str
    color: tuple
    level: int       # the level you will have after taking it
    new: bool
    evolved: bool = False

    @property
    def tag(self):
        if self.kind in ("heal", "flux"):
            return ""
        if self.new:
            return "NEW!"
        return f"LEVEL {self.level}"


def offers(world):
    """Every possible level-up choice with a weight."""
    p = world.player
    out = []
    owned = {w.id for w in p.weapons}
    partners = {w.evo_passive for w in p.weapons if not w.evolved}
    for w in p.weapons:
        if w.level < w.max_level:
            weight = 1.0 + (0.4 if w.evo_passive in p.passives else 0.0)
            out.append((weight, Choice("weapon", w.id, w.title, w.next_text(), w.tint, w.level + 1, False,
                                       w.evolved)))
    if len(p.weapons) < WEAPON_SLOTS:
        early = 1.3 if len(p.weapons) < 3 else 0.7
        for wid, cls in WEAPONS.items():
            if wid not in owned:
                out.append((early, Choice("weapon", wid, cls.name, cls.desc, cls.color, 1, True)))
    for pid, lvl in p.passives.items():
        ps = PASSIVE_BY_ID[pid]
        if lvl < ps.max_level:
            out.append((0.85, Choice("passive", pid, ps.name, ps.desc, ps.color, lvl + 1, False)))
    if len(p.passives) < PASSIVE_SLOTS:
        for ps in PASSIVES:
            if ps.id not in p.passives:
                weight = 1.2 if ps.id in partners else 0.6
                out.append((weight, Choice("passive", ps.id, ps.name, ps.desc, ps.color, 1, True)))
    return out


def _pick(rng, pool):
    total = sum(w for w, _ in pool)
    r = rng.random() * total
    for i, (w, c) in enumerate(pool):
        r -= w
        if r <= 0:
            return pool.pop(i)[1]
    return pool.pop()[1]


def roll(world, n=None):
    """Draw distinct choices for a level-up. Luck can add a fourth card."""
    p = world.player
    if n is None:
        n = 4 if world.rng.random() < 0.08 + max(0.0, p.luck - 1.0) * 0.6 else 3
    pool = offers(world)
    picks = []
    while pool and len(picks) < n:
        picks.append(_pick(world.rng, pool))
    if not picks:
        picks = [Choice("heal", "nanoforge", "Repair Kit", "Restore 40 health.", GREEN, 0, False),
                 Choice("flux", "flux", "Flux Cache", "Gain 25 flux.", GOLD, 0, False)]
    return picks


def apply(world, choice):
    p = world.player
    if choice.kind == "weapon":
        w = p.weapon(choice.id)
        if w is not None:
            w.level = min(w.max_level, w.level + 1)
        else:
            world.add_weapon(choice.id)
    elif choice.kind == "passive":
        p.passives[choice.id] = p.passives.get(choice.id, 0) + 1
        world.seen.add("p:" + choice.id)
        p.recompute()
    elif choice.kind == "heal":
        p.heal(40)
    elif choice.kind == "flux":
        world.flux += 25


def evolvable(player):
    return [w for w in player.weapons
            if not w.evolved and w.level >= w.max_level and w.evo_passive in player.passives]


@dataclass
class Reward:
    headline: str
    name: str
    detail: str
    icon: str
    color: tuple
    evolved: bool = False


def open_chest(world):
    """Apply a chest's contents and describe them for the reveal screen."""
    p = world.player
    rewards = []
    ready = evolvable(p)
    if ready:
        w = ready[0]
        w.evolved = True
        world.on_evolve(w)
        rewards.append(Reward("EVOLUTION", w.evo_name, f"{w.name} evolved: {w.evo_desc}", w.id, w.evo_color, True))
        return rewards
    roll_v = world.rng.random() * p.luck
    count = 5 if roll_v > 1.15 else 3 if roll_v > 0.82 else 1
    for _ in range(count):
        pool = [(w, c) for w, c in offers(world) if not c.new]
        if not pool:
            break
        c = _pick(world.rng, pool)
        apply(world, c)
        rewards.append(Reward("UPGRADE", c.name, f"Level {c.level}", c.id, c.color, c.evolved))
    bonus = 15 + world.rng.randint(0, 15)
    world.flux += bonus
    rewards.append(Reward("FLUX", f"+{bonus} flux", "Spend it in the Workshop.", "flux", GOLD))
    return rewards


def evolution_table():
    """(weapon class, partner passive) pairs for the codex."""
    return [(cls, PASSIVE_BY_ID[cls.evo_passive]) for cls in WEAPONS.values()]
