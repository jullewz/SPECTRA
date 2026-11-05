"""Small math and data helpers used everywhere.

created by jullewz
"""

import math

TAU = math.tau


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def approach(v, target, step):
    if v < target:
        return min(v + step, target)
    return max(v - step, target)


def ease_out_cubic(t):
    t = clamp(t, 0.0, 1.0)
    return 1 - (1 - t) ** 3


def ease_out_back(t):
    t = clamp(t, 0.0, 1.0)
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


def ease_in_out(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def scale(color, k):
    """Multiply an RGB color by k, clamped to 0..255."""
    return (
        int(clamp(color[0] * k, 0, 255)),
        int(clamp(color[1] * k, 0, 255)),
        int(clamp(color[2] * k, 0, 255)),
    )


def mix(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def hue(h):
    """A fully saturated color from a hue in 0..1."""
    h = (h % 1.0) * 6
    i = int(h)
    f = h - i
    q, t = int(255 * (1 - f)), int(255 * f)
    return [(255, t, 0), (q, 255, 0), (0, 255, t), (0, q, 255), (t, 0, 255), (255, 0, q)][i % 6]


def dist2(ax, ay, bx, by):
    dx, dy = ax - bx, ay - by
    return dx * dx + dy * dy


def angle_to(ax, ay, bx, by):
    return math.atan2(by - ay, bx - ax)


def wrap_angle(a):
    while a > math.pi:
        a -= TAU
    while a < -math.pi:
        a += TAU
    return a


def normalize(x, y):
    d = math.hypot(x, y)
    if d < 1e-9:
        return 0.0, 0.0
    return x / d, y / d


def point_segment_dist2(px, py, ax, ay, bx, by):
    """Squared distance from point P to segment AB."""
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom < 1e-12:
        return dist2(px, py, ax, ay)
    t = clamp(((px - ax) * abx + (py - ay) * aby) / denom, 0.0, 1.0)
    return dist2(px, py, ax + abx * t, ay + aby * t)


def fmt_time(seconds):
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def fmt_int(n):
    return f"{int(n):,}"


def fmt_pct(v):
    return f"{v * 100:+.0f}%"


def weighted_choice(rng, weights):
    """Pick a key from {key: weight}."""
    total = sum(w for w in weights.values() if w > 0)
    if total <= 0:
        return None
    r = rng.random() * total
    for key, w in weights.items():
        if w <= 0:
            continue
        r -= w
        if r <= 0:
            return key
    return next(k for k, w in weights.items() if w > 0)


class SpatialHash:
    """A uniform grid for fast "who is near this point?" queries."""

    def __init__(self, cell=90):
        self.cell = cell
        self.cells = {}

    def clear(self):
        self.cells.clear()

    def insert(self, obj):
        key = (int(obj.x // self.cell), int(obj.y // self.cell))
        bucket = self.cells.get(key)
        if bucket is None:
            self.cells[key] = [obj]
        else:
            bucket.append(obj)

    def query(self, x, y, r):
        c = self.cell
        x0, x1 = int((x - r) // c), int((x + r) // c)
        y0, y1 = int((y - r) // c), int((y + r) // c)
        cells = self.cells
        out = []
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                bucket = cells.get((cx, cy))
                if bucket:
                    out.extend(bucket)
        return out

    def __len__(self):
        return sum(len(b) for b in self.cells.values())
