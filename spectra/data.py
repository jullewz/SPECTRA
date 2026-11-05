"""Game content tables: pilots, stages, passive items, workshop upgrades, achievements.

created by jullewz
"""

from dataclasses import dataclass, field

from .config import BLUE, CYAN, GOLD, GREEN, GREY, MAGENTA, ORANGE, PINK, PURPLE, RED, TEAL, YELLOW


# --------------------------------------------------------------------------- pilots


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    title: str
    desc: str
    weapon: str
    color: tuple
    perk: str = ""
    hp: float = 100
    speed: float = 1.0
    might: float = 1.0
    armor: float = 0
    magnet: float = 1.0
    luck: float = 1.0
    crit: float = 0.0
    cooldown: float = 1.0
    growth: float = 1.0
    area: float = 1.0
    regen: float = 0.0
    unlock: str = None


CHARACTERS = [
    Character("nova", "Nova", "The Pathfinder", "A balanced pilot who always hits the closest threat first.",
              "pulse", CYAN, "+10% experience", growth=1.1),
    Character("vex", "Vex", "The Blade Dancer", "Fast and fragile. Lives on the edge of the Arc Blade.",
              "arc", MAGENTA, "+20% speed, +8% critical chance", hp=80, speed=1.2, crit=0.08, unlock="survivor"),
    Character("titan", "Titan", "The Bulwark", "A flying fortress wrapped in Orbit Shards.",
              "orbit", ORANGE, "+50% health, +2 armor, slower", hp=150, speed=0.86, armor=2, unlock="queen"),
    Character("echo", "Echo", "The Collector", "Everything drifts toward Echo: experience, luck and trouble.",
              "nova", GREEN, "+60% pickup range, +25% luck", magnet=1.6, luck=1.25, unlock="evolved"),
    Character("kira", "Kira", "The Prism", "A precision ace who splits light into weapons.",
              "lance", PURPLE, "+15% damage, weapons 8% faster", hp=90, might=1.15, cooldown=0.92,
              unlock="champion"),
]
CHAR_BY_ID = {c.id: c for c in CHARACTERS}


# --------------------------------------------------------------------------- stages


@dataclass(frozen=True)
class Stage:
    id: str
    name: str
    desc: str
    difficulty: float
    base: tuple
    grid: tuple
    nebula: tuple
    star: tuple
    accent: tuple
    unlock: str = None


STAGES = [
    Stage("grid", "Neon Grid", "Where every pilot starts. The swarm is only waking up.", 1.0,
          (6, 8, 22), (20, 36, 74), ((30, 80, 170), (90, 40, 170), (20, 120, 150)), (170, 200, 255), CYAN),
    Stage("nebula", "Crimson Nebula", "Burning gas clouds. Enemies are 30% tougher and hit harder.", 1.3,
          (16, 5, 14), (66, 20, 42), ((180, 30, 60), (200, 80, 30), (130, 20, 110)), (255, 190, 190), RED,
          unlock="grid"),
    Stage("aurora", "Aurora Rift", "The edge of the map. Green light and endless swarms.", 1.6,
          (3, 14, 15), (18, 60, 56), ((30, 170, 110), (60, 90, 210), (140, 60, 190)), (190, 255, 230), GREEN,
          unlock="nebula"),
]
STAGE_BY_ID = {s.id: s for s in STAGES}


# --------------------------------------------------------------------------- passive items


@dataclass(frozen=True)
class Passive:
    id: str
    name: str
    desc: str
    color: tuple
    max_level: int
    effect: dict = field(default_factory=dict)


PASSIVES = [
    Passive("overclock", "Overclock", "Weapons recharge 8% faster.", CYAN, 5, {"cooldown": -0.08}),
    Passive("amplifier", "Amplifier", "Deal 10% more damage.", RED, 5, {"might": 0.10}),
    Passive("thrusters", "Thrusters", "Move 10% faster.", ORANGE, 5, {"speed": 0.10}),
    Passive("plating", "Plating", "+1 armor and +10 max health.", BLUE, 5, {"armor": 1, "max_hp_flat": 10}),
    Passive("magnetron", "Magnetron", "Pick things up from 30% farther away.", MAGENTA, 5, {"magnet": 0.30}),
    Passive("multiplexer", "Multiplexer", "Every weapon fires one extra projectile.", YELLOW, 2, {"amount": 1}),
    Passive("lens", "Focus Lens", "Weapon areas are 10% larger.", TEAL, 5, {"area": 0.10}),
    Passive("chrono", "Chrono Coil", "Weapon effects last 12% longer.", PURPLE, 5, {"duration": 0.12}),
    Passive("nanoforge", "Nanoforge", "Regenerate 0.3 health per second.", GREEN, 5, {"regen": 0.3}),
    Passive("fortune", "Fortune Chip", "+10% luck and +3% critical chance.", GOLD, 5, {"luck": 0.10, "crit": 0.03}),
    Passive("rails", "Velocity Rails", "Projectiles fly 12% faster.", PINK, 5, {"proj_speed": 0.12}),
]
PASSIVE_BY_ID = {p.id: p for p in PASSIVES}


# --------------------------------------------------------------------------- workshop (permanent upgrades)


@dataclass(frozen=True)
class MetaUpgrade:
    id: str
    name: str
    desc: str
    icon: str
    color: tuple
    max_rank: int
    base_cost: int
    step: int
    effect: dict = field(default_factory=dict)

    def cost(self, rank):
        return self.base_cost + self.step * rank


META = [
    MetaUpgrade("hull", "Hull", "+10% max health per rank.", "plating", BLUE, 5, 60, 60, {"max_hp_pct": 0.10}),
    MetaUpgrade("firepower", "Firepower", "+5% damage per rank.", "amplifier", RED, 5, 80, 80, {"might": 0.05}),
    MetaUpgrade("engines", "Engines", "+4% speed per rank.", "thrusters", ORANGE, 5, 50, 50, {"speed": 0.04}),
    MetaUpgrade("recovery", "Recovery", "+0.15 health per second.", "nanoforge", GREEN, 5, 60, 60, {"regen": 0.15}),
    MetaUpgrade("armor", "Armor", "+1 armor per rank.", "plating", GREY, 3, 120, 120, {"armor": 1}),
    MetaUpgrade("attraction", "Attraction", "+12% pickup range per rank.", "magnetron", MAGENTA, 4, 40, 40,
                {"magnet": 0.12}),
    MetaUpgrade("insight", "Insight", "+5% experience per rank.", "lens", TEAL, 5, 70, 70, {"growth": 0.05}),
    MetaUpgrade("fortune", "Fortune", "+8% luck per rank.", "fortune", GOLD, 4, 70, 70, {"luck": 0.08}),
    MetaUpgrade("greed", "Greed", "+10% flux earned per rank.", "flux", YELLOW, 5, 60, 60, {"greed": 0.10}),
    MetaUpgrade("haste", "Haste", "Weapons recharge 3% faster per rank.", "overclock", CYAN, 4, 100, 100,
                {"cooldown": -0.03}),
    MetaUpgrade("reroll", "Reroll", "+1 level-up reroll in every run.", "multiplexer", PURPLE, 3, 150, 100,
                {"rerolls": 1}),
    MetaUpgrade("revival", "Revival", "Come back once per run with half health.", "chrono", PINK, 1, 600, 0,
                {"revives": 1}),
]
META_BY_ID = {m.id: m for m in META}


# --------------------------------------------------------------------------- achievements


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    desc: str
    reward: int


ACHIEVEMENTS = [
    Achievement("first_blood", "First Light", "Destroy your first enemy.", 10),
    Achievement("survivor", "Survivor", "Survive for 5 minutes. Unlocks Vex.", 50),
    Achievement("queen", "Regicide", "Defeat the Hive Queen. Unlocks Titan.", 75),
    Achievement("colossus", "Prism Breaker", "Defeat the Prism Colossus.", 100),
    Achievement("serpent", "Snake Charmer", "Defeat the Serpent.", 125),
    Achievement("champion", "Champion of the Grid", "Clear the Neon Grid. Unlocks Kira.", 200),
    Achievement("crimson", "Crimson Victor", "Clear the Crimson Nebula.", 300),
    Achievement("aurora", "Aurora Ascendant", "Clear the Aurora Rift.", 500),
    Achievement("evolved", "Evolution", "Evolve a weapon. Unlocks Echo.", 75),
    Achievement("arsenal", "Full Arsenal", "Hold 6 weapons in one run.", 60),
    Achievement("maxed", "Masterwork", "Bring a weapon to level 8.", 40),
    Achievement("exterminator", "Exterminator", "Destroy 1,000 enemies in one run.", 80),
    Achievement("annihilator", "Annihilator", "Destroy 5,000 enemies in one run.", 200),
    Achievement("untouchable", "Untouchable", "Go 3 minutes without taking damage.", 100),
    Achievement("ascended", "Ascended", "Reach level 30.", 80),
    Achievement("transcendent", "Transcendent", "Reach level 50.", 150),
    Achievement("hoarder", "Hoarder", "Hold 2,000 flux at once.", 0),
    Achievement("veteran", "Veteran", "Play 10 runs.", 50),
    Achievement("roster", "Full Roster", "Unlock every pilot.", 100),
    Achievement("sweep", "Clean Sweep", "Destroy 100 enemies with a single bomb.", 50),
]
ACH_BY_ID = {a.id: a for a in ACHIEVEMENTS}
