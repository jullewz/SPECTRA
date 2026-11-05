"""Persistent progress: flux, workshop ranks, achievements, statistics and settings.

Saved as JSON in the platform's app-data folder, written atomically so a crash can
never leave a half-written save behind.

created by jullewz
"""

import json
import os
import sys

from .data import ACH_BY_ID, ACHIEVEMENTS, CHARACTERS, META_BY_ID

DEFAULT_SETTINGS = {
    "master": 0.8,
    "music": 0.55,
    "sfx": 0.75,
    "bloom": True,
    "shake": True,
    "numbers": True,
    "fullscreen": False,
    "fps": False,
}

DEFAULT_STATS = {
    "runs": 0, "wins": 0, "kills": 0, "time": 0.0, "best_time": 0.0, "best_level": 0, "best_kills": 0,
    "bosses": 0, "flux_earned": 0, "evolutions": 0, "deaths": 0,
}


def data_dir():
    env = os.environ.get("SPECTRA_HOME")
    if env:
        return env
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "SPECTRA")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/SPECTRA")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "spectra")


class SaveData:
    def __init__(self, path=None):
        self.path = path
        self.flux = 0
        self.meta = {}
        self.achievements = set()
        self.stats = dict(DEFAULT_STATS)
        self.settings = dict(DEFAULT_SETTINGS)
        self.seen = set()
        self.cleared = set()
        self.last_char = "nova"
        self.last_stage = "grid"

    # ---------------------------------------------------------------- disk

    @classmethod
    def load(cls, path):
        s = cls(path)
        if not path:
            return s
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return s
        if not isinstance(d, dict):
            return s
        s.flux = max(0, int(d.get("flux", 0)))
        s.meta = {k: max(0, min(META_BY_ID[k].max_rank, int(v)))
                  for k, v in d.get("meta", {}).items() if k in META_BY_ID}
        s.achievements = {a for a in d.get("achievements", []) if a in ACH_BY_ID}
        for k, v in d.get("stats", {}).items():
            if k in s.stats and isinstance(v, (int, float)):
                s.stats[k] = v
        for k, v in d.get("settings", {}).items():
            if k in s.settings and type(v) is type(s.settings[k]):
                s.settings[k] = v
            elif k in s.settings and isinstance(s.settings[k], float) and isinstance(v, int):
                s.settings[k] = float(v)
        s.seen = set(d.get("seen", []))
        s.cleared = set(d.get("cleared", []))
        s.last_char = d.get("last_char", "nova")
        s.last_stage = d.get("last_stage", "grid")
        return s

    def to_dict(self):
        return {
            "version": 1,
            "flux": self.flux,
            "meta": self.meta,
            "achievements": sorted(self.achievements),
            "stats": self.stats,
            "settings": self.settings,
            "seen": sorted(self.seen),
            "cleared": sorted(self.cleared),
            "last_char": self.last_char,
            "last_stage": self.last_stage,
        }

    def save(self):
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # ---------------------------------------------------------------- workshop

    def rank(self, meta_id):
        return self.meta.get(meta_id, 0)

    def bonuses(self):
        """Sum of all workshop effects, e.g. {"might": 0.15, "armor": 2}."""
        out = {}
        for mid, r in self.meta.items():
            m = META_BY_ID.get(mid)
            if not m:
                continue
            for k, v in m.effect.items():
                out[k] = out.get(k, 0) + v * r
        return out

    def can_buy(self, meta_id):
        m = META_BY_ID[meta_id]
        r = self.rank(meta_id)
        return r < m.max_rank and self.flux >= m.cost(r)

    def buy(self, meta_id):
        if not self.can_buy(meta_id):
            return False
        m = META_BY_ID[meta_id]
        self.flux -= m.cost(self.rank(meta_id))
        self.meta[meta_id] = self.rank(meta_id) + 1
        return True

    def refund_all(self):
        total = 0
        for mid, r in self.meta.items():
            m = META_BY_ID[mid]
            total += sum(m.cost(k) for k in range(r))
        self.meta = {}
        self.flux += total
        return total

    # ---------------------------------------------------------------- unlocks

    def char_unlocked(self, char):
        return char.unlock is None or char.unlock in self.achievements

    def stage_unlocked(self, stage):
        return stage.unlock is None or stage.unlock in self.cleared

    def unlock(self, ach_id):
        if ach_id in self.achievements or ach_id not in ACH_BY_ID:
            return False
        self.achievements.add(ach_id)
        self.flux += ACH_BY_ID[ach_id].reward
        return True


# --------------------------------------------------------------------------- achievement rules


def _w(world, attr, default=0):
    return getattr(world, attr, default) if world is not None else default


RULES = {
    "first_blood": lambda s, w: _w(w, "kills") >= 1 or s.stats["kills"] >= 1,
    "survivor": lambda s, w: _w(w, "time") >= 300 or s.stats["best_time"] >= 300,
    "queen": lambda s, w: "queen" in _w(w, "bosses_killed", ()),
    "colossus": lambda s, w: "colossus" in _w(w, "bosses_killed", ()),
    "serpent": lambda s, w: "serpent" in _w(w, "bosses_killed", ()),
    "champion": lambda s, w: "grid" in s.cleared,
    "crimson": lambda s, w: "nebula" in s.cleared,
    "aurora": lambda s, w: "aurora" in s.cleared,
    "evolved": lambda s, w: _w(w, "evolutions") > 0 or s.stats["evolutions"] > 0,
    "arsenal": lambda s, w: w is not None and len(w.player.weapons) >= 6,
    "maxed": lambda s, w: w is not None and any(x.level >= x.max_level for x in w.player.weapons),
    "exterminator": lambda s, w: _w(w, "kills") >= 1000,
    "annihilator": lambda s, w: _w(w, "kills") >= 5000,
    "untouchable": lambda s, w: _w(w, "best_no_hit") >= 180,
    "ascended": lambda s, w: w is not None and w.player.level >= 30,
    "transcendent": lambda s, w: w is not None and w.player.level >= 50,
    "hoarder": lambda s, w: s.flux >= 2000,
    "veteran": lambda s, w: s.stats["runs"] >= 10,
    "roster": lambda s, w: all(s.char_unlocked(c) for c in CHARACTERS),
    "sweep": lambda s, w: _w(w, "best_bomb") >= 100,
}


def check_achievements(save, world=None):
    """Unlock every achievement whose rule now holds. Returns the newly unlocked ones."""
    new = []
    for _ in range(2):  # a second pass catches chains like "roster"
        for ach in ACHIEVEMENTS:
            if ach.id in save.achievements:
                continue
            rule = RULES.get(ach.id)
            try:
                ok = rule is not None and rule(save, world)
            except (AttributeError, KeyError, TypeError):
                ok = False
            if ok and save.unlock(ach.id):
                new.append(ach)
    return new
