"""Global constants and the SPECTRA color palette.

created by jullewz
"""

TITLE = "SPECTRA"
SUBTITLE = "a neon survival roguelite"
VERSION = "1.0.0"
AUTHOR = "jullewz"

WIDTH, HEIGHT = 1280, 720
FPS = 60
MAX_DT = 1 / 30

# --------------------------------------------------------------------------- palette

BG = (5, 5, 14)
WHITE = (236, 238, 255)
GREY = (140, 140, 168)
DIM = (82, 82, 108)
DARK = (22, 22, 40)
PANEL = (14, 14, 30)

CYAN = (70, 230, 255)
BLUE = (90, 140, 255)
PURPLE = (170, 100, 255)
MAGENTA = (255, 70, 200)
PINK = (255, 120, 175)
RED = (255, 72, 92)
ORANGE = (255, 150, 50)
YELLOW = (255, 225, 90)
GOLD = (255, 198, 66)
GREEN = (90, 255, 160)
LIME = (190, 255, 90)
TEAL = (40, 225, 195)

RAINBOW = [(255, 80, 110), (255, 170, 60), (255, 240, 90), (110, 255, 140), (80, 200, 255), (160, 110, 255)]

# XP gems: (minimum value, color)
GEM_TIERS = [(1, (90, 190, 255)), (5, (110, 255, 160)), (25, (255, 110, 220)), (100, (255, 215, 80))]

# --------------------------------------------------------------------------- rules

RUN_LENGTH = 12 * 60          # the final boss arrives at 12:00
MAX_ENEMIES = 340
MAX_GEMS = 420
WEAPON_SLOTS = 6
PASSIVE_SLOTS = 6
DESPAWN_DISTANCE = 1150       # enemies farther than this are moved back near the player
SPAWN_DISTANCE = 790          # just outside the screen corners
PLAYER_RADIUS = 14
BASE_MAGNET = 100
IFRAMES = 0.5
