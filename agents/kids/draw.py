"""Drawing primitives for the kids story kit (pycairo). Canvas is always 1920x1080 design units."""

import math
import random
import shutil
import subprocess
from pathlib import Path

import cairo

W, H = 1920, 1080
FONT = "Fredoka"
_FONT_READY = False


def ensure_fonts() -> None:
    """Install the bundled Fredoka (OFL) for fontconfig once; fall back to DejaVu Sans silently."""
    global _FONT_READY, FONT
    if _FONT_READY:
        return
    _FONT_READY = True
    try:
        dest = Path.home() / ".local" / "share" / "fonts"
        dest.mkdir(parents=True, exist_ok=True)
        for f in (Path(__file__).parent / "fonts").glob("*.ttf"):
            if not (dest / f.name).exists():
                shutil.copy(f, dest / f.name)
        subprocess.run(["fc-cache", "-f"], capture_output=True, timeout=60)
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=30).stdout
        fam = next((l.split(",")[0].strip() for l in out.splitlines() if "Fredoka" in l), None)
        FONT = fam or "DejaVu Sans"
    except Exception:  # noqa: BLE001 — never fail a render over a font
        FONT = "DejaVu Sans"


# ── colour + maths ────────────────────────────────────────────────────────────
def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def col(c, h, a=1.0):
    c.set_source_rgba(*hexc(h, a))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, t0, d):
    return clamp((t - t0) / d) if d > 0 else (1.0 if t >= t0 else 0.0)


def ease_out(p):
    return 1 - (1 - p) ** 3


def ease_io(p):
    return p * p * (3 - 2 * p)


def back(p):
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    s = 1.9
    p -= 1
    return p * p * ((s + 1) * p + s) + 1


def pop(t, t0, d=0.45):
    return back(prog(t, t0, d))


def lerp(a, b, p):
    return a + (b - a) * p


INK = "#2b2d42"
PINK, YELLOW, GREEN, BLUE, PURPLE, ORANGE = "#ef476f", "#ffd166", "#06d6a0", "#118ab2", "#9b5de5", "#fb8500"


# ── shapes ───────────────────────────────────────────────────────────────────
def rr(c, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    c.close_path()


def fill_stroke(c, fill, stroke=INK, lw=6):
    col(c, fill)
    if stroke:
        c.fill_preserve()
        col(c, stroke)
        c.set_line_width(lw)
        c.stroke()
    else:
        c.fill()


def circle(c, x, y, r, fill, stroke=None, lw=6):
    c.arc(x, y, max(r, 0.01), 0, 2 * math.pi)
    fill_stroke(c, fill, stroke, lw)


def card(c, x, y, w, h, fill="#ffffff", stroke=INK, lw=6, r=36):
    rr(c, x - w / 2, y - h / 2, w, h, r)
    fill_stroke(c, fill, stroke, lw)


def text(c, s, x, y, size, color=INK, align="c", outline=None, olw=10, max_w=None):
    """Draw text centred vertically on y. Shrinks to fit max_w. Returns the drawn width."""
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    c.set_font_size(size)
    e = c.text_extents(s)
    if max_w and e.width > max_w:
        size = size * max_w / e.width
        c.set_font_size(size)
        e = c.text_extents(s)
    ox = {"c": -e.width / 2 - e.x_bearing, "l": -e.x_bearing, "r": -e.width - e.x_bearing}[align]
    c.move_to(x + ox, y + size * 0.35)
    c.text_path(s)
    if outline:
        col(c, outline)
        c.set_line_width(olw)
        c.set_line_join(cairo.LINE_JOIN_ROUND)
        c.stroke_preserve()
    col(c, color)
    c.fill()
    return e.width


def wrap(c, s, size, max_w):
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    c.set_font_size(size)
    rows, cur = [], []
    for w in s.split():
        if cur and c.text_extents(" ".join(cur + [w])).x_advance > max_w:
            rows.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        rows.append(" ".join(cur))
    return rows


def text_block(c, s, x, y, size, color=INK, max_w=600, line_h=1.2, max_rows=3):
    rows = wrap(c, s, size, max_w)
    while len(rows) > max_rows and size > 16:
        size *= 0.88
        rows = wrap(c, s, size, max_w)
    y0 = y - (len(rows) - 1) * size * line_h / 2
    for i, r in enumerate(rows):
        text(c, r, x, y0 + i * size * line_h, size, color, max_w=max_w)


class T:
    """Scoped transform: with T(c, x, y, scale, rot, alpha): draw at local origin."""

    def __init__(self, c, x=0, y=0, sc=1.0, rot=0.0, alpha=None):
        self.c, self.x, self.y, self.sc, self.rot, self.a = c, x, y, sc, rot, alpha

    def __enter__(self):
        c = self.c
        c.save()
        c.translate(self.x, self.y)
        c.rotate(self.rot)
        s = max(self.sc, 1e-4)
        c.scale(s, s)
        if self.a is not None:
            c.push_group()
        return c

    def __exit__(self, *a):
        if self.a is not None:
            self.c.pop_group_to_source()
            self.c.paint_with_alpha(clamp(self.a))
        self.c.restore()


# ── decorations ──────────────────────────────────────────────────────────────
def sparkle(c, x, y, r, a=1.0, color="#ffffff"):
    if r <= 0:
        return
    c.save()
    c.translate(x, y)
    c.move_to(0, -r)
    for px, py in ((r, 0), (0, r), (-r, 0), (0, -r)):
        c.curve_to(0, 0, 0, 0, px, py)
    col(c, color, a)
    c.fill()
    c.restore()


def arrow(c, x0, y0, x1, y1, color, p=1.0, lw=18):
    if p <= 0:
        return
    x1, y1 = lerp(x0, x1, p), lerp(y0, y1, p)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(x0, y0)
    c.line_to(x1, y1)
    c.set_line_width(lw)
    col(c, color)
    c.stroke()
    a = math.atan2(y1 - y0, x1 - x0)
    L = lw * 2.4
    c.move_to(x1 + math.cos(a) * lw * 0.6, y1 + math.sin(a) * lw * 0.6)
    c.line_to(x1 - math.cos(a - 0.6) * L, y1 - math.sin(a - 0.6) * L)
    c.line_to(x1 - math.cos(a + 0.6) * L, y1 - math.sin(a + 0.6) * L)
    c.close_path()
    c.fill()


def bubble(c, x, y, w, h, thought=False, tail_dx=-50):
    with T(c, x, y):
        if thought:
            circle(c, -w * 0.25, h / 2 + 40, 22, "#ffffff", INK, 5)
            circle(c, -w * 0.33, h / 2 + 85, 13, "#ffffff", INK, 5)
        else:
            c.move_to(-30, h / 2 - 4)
            c.line_to(tail_dx, h / 2 + 60)
            c.line_to(20, h / 2 - 4)
            fill_stroke(c, "#ffffff", INK, 5)
        rr(c, -w / 2, -h / 2, w, h, min(60, h / 2))
        fill_stroke(c, "#ffffff", INK, 5)
        if not thought:
            c.move_to(-28, h / 2 - 4)
            c.line_to(18, h / 2 - 4)
            c.set_line_width(8)
            col(c, "#ffffff")
            c.stroke()


def badge(c, x, y, s, label, fill=GREEN, size=56):
    with T(c, x, y, s):
        c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        c.set_font_size(size)
        w = min(c.text_extents(label).width, 700) + 80
        card(c, 0, 0, w, size * 1.9, fill, INK, 6, size)
        text(c, label, 0, 0, size, "#ffffff", outline=INK, olw=8, max_w=700)


def confetti(c, lt, n=70, seed=11):
    if lt < 0:
        return
    rnd = random.Random(seed)
    cols = [PINK, YELLOW, GREEN, BLUE, PURPLE]
    for i in range(n):
        x0 = rnd.uniform(0, W)
        vy = rnd.uniform(180, 420)
        ph = rnd.uniform(0, 6)
        y = -40 + lt * vy - rnd.uniform(0, 300)
        x = x0 + math.sin(lt * 3 + ph) * 40
        if -50 < y < H:
            with T(c, x, y, 1, lt * 5 + ph):
                c.rectangle(-9, -5, 18, 10)
                col(c, cols[i % 5])
                c.fill()


# ── backgrounds ──────────────────────────────────────────────────────────────
CLOUDS = [(200, 180, 1.0), (760, 120, 0.8), (1320, 200, 1.1), (1750, 110, 0.7)]


def cloud(c, x, y, s, color="#ffffff"):
    with T(c, x, y, s):
        for dx, dy, r in ((-60, 10, 45), (0, -15, 60), (60, 10, 45), (0, 20, 45)):
            circle(c, dx, dy, r, color)


def background(c, t, weather="sunny"):
    sky = {"sunny": ("#7ec8f0", "#d8f1ff"), "rainy": ("#8d99ae", "#c9d2dd"), "night": ("#1d2b53", "#4a4e8c")}
    top, bot = sky.get(weather, sky["sunny"])
    g = cairo.LinearGradient(0, 0, 0, 820)
    g.add_color_stop_rgb(0, *hexc(top)[:3])
    g.add_color_stop_rgb(1, *hexc(bot)[:3])
    c.rectangle(0, 0, W, H)
    c.set_source(g)
    c.fill()
    if weather == "sunny":
        with T(c, 1700, 150, 1, t * 0.3):
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            for i in range(12):
                a = i * math.pi / 6
                c.move_to(math.cos(a) * 95, math.sin(a) * 95)
                c.line_to(math.cos(a) * 130, math.sin(a) * 130)
                c.set_line_width(12)
                col(c, YELLOW)
                c.stroke()
        circle(c, 1700, 150, 80, YELLOW)
        circle(c, 1700, 150, 62, "#ffe08a")
    elif weather == "night":
        rnd = random.Random(5)
        for _ in range(60):
            sx, sy = rnd.uniform(0, W), rnd.uniform(0, 600)
            sparkle(c, sx, sy, 5 + 3 * math.sin(t * 3 + sx), 0.9)
        circle(c, 1650, 160, 70, "#fff3b0")
        circle(c, 1680, 140, 62, top)
    for cx, cy, s in CLOUDS:
        x = (cx + t * 18 * s) % (W + 400) - 200
        cloud(c, x, cy, s, {"rainy": "#6c757d", "night": "#39437a"}.get(weather, "#ffffff"))
    hill, grass = {"rainy": ("#5c8f60", "#6f9f72"), "night": ("#2f5d50", "#3a6b5a")}.get(weather, ("#6fbf73", "#8fd694"))
    c.move_to(0, 760)
    c.curve_to(400, 640, 800, 700, 1000, 760)
    c.curve_to(1300, 660, 1700, 680, W, 740)
    c.line_to(W, 900)
    c.line_to(0, 900)
    col(c, hill)
    c.fill()
    c.rectangle(0, 800, W, H - 800)
    col(c, grass)
    c.fill()
    if weather == "rainy":
        rnd = random.Random(3)
        c.set_line_width(4)
        for _ in range(90):
            rx = rnd.uniform(0, W)
            sp = rnd.uniform(700, 1000)
            ry = (rnd.uniform(0, 900) + t * sp) % 900
            c.move_to(rx, ry)
            c.line_to(rx - 8, ry + 30)
            col(c, "#e3f2fd", 0.8)
            c.stroke()
        for rx in (300, 900, 1500):
            c.save()
            c.translate(rx, 860)
            c.scale(1, 0.25)
            c.arc(0, 0, 90, 0, 2 * math.pi)
            c.restore()
            col(c, "#9ec9e2", 0.8)
            c.fill()
