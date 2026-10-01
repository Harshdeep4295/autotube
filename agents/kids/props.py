"""Prop library. Every prop draws centred on (0,0) inside a 200x200 box; `prop()` places and scales it.

Keep this list in sync with agents/kids_scene_schema.PROPS (a test enforces it).
"""

import math

import cairo

from agents.kids.draw import (BLUE, GREEN, INK, ORANGE, PINK, PURPLE, YELLOW, T, circle, col,
                              fill_stroke, rr, sparkle, text)


def _coin(c, t):
    k = abs(math.cos(t * 4)) * 0.75 + 0.25
    c.save()
    c.scale(k, 1)
    circle(c, 0, 0, 90, "#f7b801", "#c77d00", 12)
    circle(c, 0, 0, 64, "#ffd23f")
    c.move_to(0, -45)
    for i in range(1, 10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 45 if i % 2 == 0 else 20
        c.line_to(r * math.cos(a), r * math.sin(a))
    c.close_path()
    col(c, "#f7b801")
    c.fill()
    c.restore()


def _lemon(c, t):
    c.save()
    c.scale(1.25, 1)
    c.arc(0, 10, 62, 0, 2 * math.pi)
    c.restore()
    c.move_to(74, -2)
    c.line_to(96, 10)
    c.line_to(74, 22)
    c.move_to(-74, -2)
    c.line_to(-96, 10)
    c.line_to(-74, 22)
    fill_stroke(c, "#ffe14d", "#e0a800", 6)
    c.save()
    c.scale(1.25, 1)
    c.arc(0, 10, 62, 0, 2 * math.pi)
    c.restore()
    fill_stroke(c, "#ffe14d", "#e0a800", 6)
    c.move_to(0, -52)
    c.curve_to(15, -95, 55, -95, 55, -78)
    c.curve_to(40, -62, 15, -56, 0, -52)
    col(c, GREEN)
    c.fill()


def _cup(c, t):
    c.move_to(-50, -70)
    c.line_to(50, -70)
    c.line_to(38, 90)
    c.line_to(-38, 90)
    c.close_path()
    fill_stroke(c, "#ffffff", "#9aa5b1", 6)
    c.move_to(-45, -20)
    c.line_to(45, -20)
    c.line_to(38, 90)
    c.line_to(-38, 90)
    c.close_path()
    col(c, "#ffe14d")
    c.fill()
    c.move_to(15, -70)
    c.line_to(38, -100)
    c.set_line_width(10)
    col(c, PINK)
    c.stroke()


def _jar(c, t):
    rr(c, -70, -60, 140, 150, 30)
    fill_stroke(c, "#dff3ff", "#7aa6c2", 6)
    rr(c, -58, -85, 116, 28, 10)
    col(c, "#7aa6c2")
    c.fill()
    for i, (x, y) in enumerate(((-30, 60), (5, 60), (40, 60), (-12, 30), (22, 30))):
        with T(c, x, y, 0.22):
            _coin(c, 0)


def _pie(c, t, n=8, missing=0):
    for i in range(n):
        if i < missing:
            continue
        a0, a1 = -math.pi / 2 + i * 2 * math.pi / n, -math.pi / 2 + (i + 1) * 2 * math.pi / n
        _slice_path(c, 0, 0, 92, a0, a1)


def _slice_path(c, x, y, r, a0, a1):
    c.move_to(x, y)
    c.arc(x, y, r, a0, a1)
    c.close_path()
    fill_stroke(c, YELLOW, "#e09f3e", 4)
    c.arc(x, y, r, a0, a1)
    c.set_line_width(max(4, r * 0.12))
    col(c, "#e09f3e")
    c.stroke()
    am = (a0 + a1) / 2
    for rf, da in ((0.55, 0), (0.78, 0.1), (0.78, -0.1)):
        if abs(a1 - a0) > 0.3 or da == 0:
            circle(c, x + math.cos(am + da) * r * rf, y + math.sin(am + da) * r * rf, r * 0.07, "#fff3b0", "#e0a800", 2)


def _pizza(c, t):
    _pie(c, t)


def _slice(c, t):
    _slice_path(c, 0, -95, 190, math.pi / 2 - 0.33, math.pi / 2 + 0.33)


def _apple(c, t):
    circle(c, -28, 15, 62, "#e63946")
    circle(c, 28, 15, 62, "#e63946")
    c.move_to(0, -40)
    c.line_to(8, -80)
    c.set_line_width(10)
    col(c, "#6b4226")
    c.stroke()
    c.move_to(8, -65)
    c.curve_to(40, -95, 70, -70, 60, -60)
    c.curve_to(40, -50, 20, -55, 8, -65)
    col(c, GREEN)
    c.fill()
    circle(c, -40, -5, 14, "#ffffff")


def _cookie(c, t):
    circle(c, 0, 0, 88, "#d4a373", "#9c6644", 6)
    for x, y in ((-30, -30), (25, -40), (35, 20), (-20, 35), (0, 0)):
        circle(c, x, y, 12, "#5a3825")


def _toy(c, t):  # beach ball
    circle(c, 0, 0, 88, "#ffffff", INK, 6)
    for i, colr in enumerate((PINK, YELLOW, BLUE)):
        a = i * 2 * math.pi / 3 + t
        c.move_to(0, 0)
        c.arc(0, 0, 84, a, a + math.pi / 3)
        c.close_path()
        col(c, colr)
        c.fill()
    circle(c, 0, 0, 16, "#ffffff", INK, 4)


def _book(c, t):
    rr(c, -85, -70, 80, 140, 10)
    fill_stroke(c, BLUE)
    rr(c, 5, -70, 80, 140, 10)
    fill_stroke(c, BLUE)
    rr(c, -75, -60, 70, 120, 6)
    col(c, "#ffffff")
    c.fill()
    rr(c, 5, -60, 70, 120, 6)
    c.fill()
    c.set_line_width(4)
    col(c, "#c9d2dd")
    for i in range(4):
        for x0 in (-65, 15):
            c.move_to(x0, -35 + i * 25)
            c.line_to(x0 + 50, -35 + i * 25)
            c.stroke()


def _bulb(c, t):
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(8):
        a = i * math.pi / 4 + t
        c.move_to(math.cos(a) * 72, math.sin(a) * 72 - 15)
        c.line_to(math.cos(a) * 95, math.sin(a) * 95 - 15)
        c.set_line_width(8)
        col(c, YELLOW)
        c.stroke()
    circle(c, 0, -15, 55, "#fff3b0", "#f4a259", 6)
    rr(c, -25, 35, 50, 36, 8)
    col(c, "#9aa5b1")
    c.fill()


def _heart(c, t):
    s = 1 + 0.06 * math.sin(t * 6)
    c.save()
    c.scale(s, s)
    c.move_to(0, 80)
    c.curve_to(-120, 0, -70, -90, 0, -40)
    c.curve_to(70, -90, 120, 0, 0, 80)
    fill_stroke(c, PINK)
    c.restore()


def _star(c, t):
    c.move_to(0, -95)
    for i in range(1, 10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 95 if i % 2 == 0 else 42
        c.line_to(r * math.cos(a), r * math.sin(a))
    c.close_path()
    fill_stroke(c, YELLOW, ORANGE, 6)


def _letter(c, t):
    rr(c, -90, -60, 180, 120, 12)
    fill_stroke(c, "#ffffff")
    c.move_to(-90, -55)
    c.line_to(0, 15)
    c.line_to(90, -55)
    c.set_line_width(6)
    col(c, INK)
    c.stroke()
    _heart_small(c, 0, 25)


def _heart_small(c, x, y):
    with T(c, x, y, 0.22):
        c.move_to(0, 80)
        c.curve_to(-120, 0, -70, -90, 0, -40)
        c.curve_to(70, -90, 120, 0, 0, 80)
        col(c, PINK)
        c.fill()


def _phone(c, t):
    rr(c, -52, -95, 104, 190, 18)
    fill_stroke(c, INK)
    rr(c, -42, -78, 84, 145, 8)
    col(c, "#9bf6ff")
    c.fill()
    circle(c, 0, 80, 7, "#ffffff")
    rr(c, -30, -60, 45, 18, 8)
    col(c, "#ffffff")
    c.fill()
    rr(c, -15, -30, 45, 18, 8)
    col(c, GREEN)
    c.fill()


def _laptop(c, t):
    rr(c, -80, -80, 160, 110, 10)
    fill_stroke(c, INK)
    rr(c, -68, -70, 136, 88, 6)
    col(c, "#9bf6ff")
    c.fill()
    c.move_to(-100, 40)
    c.line_to(100, 40)
    c.line_to(85, 30)
    c.line_to(-85, 30)
    c.close_path()
    fill_stroke(c, "#9aa5b1", INK, 5)


def _robot(c, t):
    c.move_to(0, -95)
    c.line_to(0, -70)
    c.set_line_width(6)
    col(c, INK)
    c.stroke()
    circle(c, 0, -95, 10, PINK)
    rr(c, -65, -70, 130, 90, 24)
    fill_stroke(c, "#cfd8dc")
    blink = (t % 2.7) < 0.15
    for ex in (-28, 28):
        if blink:
            c.move_to(ex - 12, -28)
            c.line_to(ex + 12, -28)
            c.set_line_width(6)
            col(c, INK)
            c.stroke()
        else:
            circle(c, ex, -28, 14, BLUE)
    rr(c, -25, -2, 50, 10, 5)
    col(c, INK)
    c.fill()
    rr(c, -50, 25, 100, 70, 16)
    fill_stroke(c, "#b0bec5")
    circle(c, 0, 58, 12, YELLOW)


def _cloud(c, t):
    for dx, dy, r in ((-50, 15, 45), (0, -15, 60), (50, 15, 45), (0, 25, 45)):
        circle(c, dx, dy, r, "#ffffff")
    c.save()
    c.set_line_width(5)
    col(c, "#9aa5b1")
    c.move_to(-95, 60)
    c.line_to(95, 60)
    c.stroke()
    c.restore()


def _server(c, t):
    for i in range(3):
        rr(c, -75, -85 + i * 60, 150, 50, 10)
        fill_stroke(c, "#455a64")
        on = (int(t * 3) + i) % 2 == 0
        circle(c, 45, -60 + i * 60, 8, GREEN if on else "#90a4ae")
        rr(c, -60, -66 + i * 60, 60, 12, 5)
        col(c, "#90a4ae")
        c.fill()


def _lock(c, t):
    c.arc(0, -25, 45, math.pi, 2 * math.pi)
    c.set_line_width(20)
    col(c, "#9aa5b1")
    c.stroke()
    rr(c, -70, -25, 140, 110, 20)
    fill_stroke(c, YELLOW, ORANGE, 6)
    circle(c, 0, 20, 14, INK)
    rr(c, -5, 25, 10, 30, 4)
    col(c, INK)
    c.fill()


def _key(c, t):
    circle(c, -50, 0, 42, YELLOW, ORANGE, 6)
    circle(c, -50, 0, 16, "#ffffff")
    rr(c, -12, -10, 110, 20, 6)
    fill_stroke(c, YELLOW, ORANGE, 5)
    rr(c, 70, 8, 14, 26, 4)
    col(c, ORANGE)
    c.fill()
    rr(c, 45, 8, 14, 20, 4)
    c.fill()


def _gift(c, t):
    rr(c, -80, -30, 160, 110, 10)
    fill_stroke(c, PURPLE)
    rr(c, -90, -60, 180, 40, 10)
    fill_stroke(c, PURPLE)
    c.rectangle(-12, -60, 24, 140)
    col(c, YELLOW)
    c.fill()
    for s in (-1, 1):
        c.save()
        c.translate(0, -62)
        c.scale(s, 1)
        c.move_to(0, 0)
        c.curve_to(30, -50, 70, -30, 0, 0)
        c.set_line_width(10)
        col(c, YELLOW)
        c.stroke()
        c.restore()


def _seed(c, t):
    c.save()
    c.scale(0.7, 1)
    circle(c, 0, 30, 45, "#b5835a", "#7f5539", 6)
    c.restore()
    c.move_to(0, -10)
    c.curve_to(-10, -50, 10, -70, 0, -90)
    c.set_line_width(8)
    col(c, GREEN)
    c.stroke()
    c.move_to(0, -60)
    c.curve_to(30, -95, 60, -70, 50, -60)
    c.curve_to(30, -50, 10, -55, 0, -60)
    c.fill()


def _tree(c, t):
    rr(c, -18, 0, 36, 95, 8)
    col(c, "#9c6644")
    c.fill()
    for dx, dy, r in ((-40, -20, 50), (40, -20, 50), (0, -60, 58), (0, -10, 55)):
        circle(c, dx, dy, r, "#58b368")
    for dx, dy in ((-30, -40), (30, -10), (10, -70)):
        circle(c, dx, dy, 10, "#e63946")


def _battery(c, t):
    rr(c, -85, -45, 160, 90, 14)
    fill_stroke(c, "#ffffff")
    rr(c, 75, -18, 16, 36, 5)
    col(c, INK)
    c.fill()
    lvl = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(t * 1.5))
    rr(c, -75, -35, 140 * lvl, 70, 8)
    col(c, GREEN)
    c.fill()


def _stand(c, t):
    with T(c, 0, 95, 0.36):
        stand_big(c, t, big=False)


def _shop(c, t):
    rr(c, -80, -40, 160, 130, 12)
    fill_stroke(c, "#ffffff")
    c.move_to(-95, -40)
    c.line_to(0, -100)
    c.line_to(95, -40)
    c.close_path()
    fill_stroke(c, PINK)
    rr(c, -25, 20, 50, 70, 8)
    fill_stroke(c, YELLOW, INK, 4)
    rr(c, -65, -20, 35, 30, 5)
    fill_stroke(c, "#9bf6ff", INK, 4)
    rr(c, 30, -20, 35, 30, 5)
    fill_stroke(c, "#9bf6ff", INK, 4)


def _bank(c, t):
    c.move_to(-100, -40)
    c.line_to(0, -100)
    c.line_to(100, -40)
    c.close_path()
    fill_stroke(c, "#e9ecef")
    rr(c, -95, 60, 190, 30, 6)
    fill_stroke(c, "#e9ecef")
    for x in (-70, -25, 20, 65):
        rr(c, x - 12, -35, 24, 95, 4)
        fill_stroke(c, "#ffffff", INK, 4)
    with T(c, 0, -62, 0.18):
        _coin(c, 0)


def _house(c, t):
    rr(c, -75, -20, 150, 110, 10)
    fill_stroke(c, "#fff3b0")
    c.move_to(-95, -20)
    c.line_to(0, -100)
    c.line_to(95, -20)
    c.close_path()
    fill_stroke(c, "#e76f51")
    rr(c, -20, 30, 40, 60, 6)
    fill_stroke(c, "#9c6644", INK, 4)
    rr(c, 30, 5, 30, 30, 4)
    fill_stroke(c, "#9bf6ff", INK, 4)


def _truck(c, t):
    rr(c, -95, -50, 120, 90, 10)
    fill_stroke(c, BLUE)
    rr(c, 25, -20, 70, 60, 10)
    fill_stroke(c, YELLOW)
    rr(c, 45, -10, 35, 22, 4)
    col(c, "#9bf6ff")
    c.fill()
    for x in (-60, 55):
        with T(c, x, 50, 1, t * 4):
            circle(c, 0, 0, 22, INK)
            circle(c, 0, 0, 8, "#ffffff")


def _rocket(c, t):
    with T(c, 0, 0, 1, 0.5):
        c.move_to(0, -95)
        c.curve_to(45, -60, 45, 20, 30, 50)
        c.line_to(-30, 50)
        c.curve_to(-45, 20, -45, -60, 0, -95)
        fill_stroke(c, "#ffffff")
        circle(c, 0, -30, 18, "#9bf6ff", INK, 5)
        for s in (-1, 1):
            c.move_to(s * 30, 10)
            c.line_to(s * 60, 60)
            c.line_to(s * 28, 50)
            c.close_path()
            fill_stroke(c, PINK, INK, 5)
        fl = 30 + 12 * math.sin(t * 20)
        c.move_to(-18, 52)
        c.line_to(0, 52 + fl)
        c.line_to(18, 52)
        c.close_path()
        col(c, ORANGE)
        c.fill()


def _piggy(c, t):
    c.save()
    c.scale(1.2, 1)
    circle(c, 0, 10, 65, "#ffafcc", INK, 5)
    c.restore()
    circle(c, 70, 10, 22, "#ff8fab", INK, 5)
    circle(c, 64, 8, 4, INK)
    circle(c, 76, 8, 4, INK)
    circle(c, 35, -15, 7, INK)
    c.move_to(-15, -45)
    c.line_to(5, -75)
    c.line_to(20, -45)
    fill_stroke(c, "#ffafcc", INK, 5)
    rr(c, -25, -58, 40, 8, 4)
    col(c, INK)
    c.fill()
    for x in (-50, -15, 20, 45):
        rr(c, x - 9, 60, 18, 26, 6)
        fill_stroke(c, "#ffafcc", INK, 4)


def _box(c, t):
    c.move_to(-80, -40)
    c.line_to(80, -40)
    c.line_to(80, 80)
    c.line_to(-80, 80)
    c.close_path()
    fill_stroke(c, "#d4a373", "#9c6644", 6)
    c.move_to(-80, -40)
    c.line_to(-50, -80)
    c.line_to(110, -80)
    c.line_to(80, -40)
    c.close_path()
    fill_stroke(c, "#e6b98a", "#9c6644", 6)
    rr(c, -15, -40, 30, 50, 4)
    col(c, "#fff3b0")
    c.fill()


def _chip(c, t):
    c.set_line_width(8)
    col(c, "#9aa5b1")
    for i in range(4):
        for s in (-1, 1):
            y = -45 + i * 30
            c.move_to(s * 70, y)
            c.line_to(s * 95, y)
            c.stroke()
            c.move_to(y, s * 70)
            c.line_to(y, s * 95)
            c.stroke()
    rr(c, -70, -70, 140, 140, 14)
    fill_stroke(c, "#37474f")
    rr(c, -35, -35, 70, 70, 8)
    col(c, GREEN if int(t * 2) % 2 else "#00bbf9")
    c.fill()


def _water(c, t):
    c.move_to(0, -95)
    c.curve_to(60, -20, 75, 20, 75, 35)
    c.arc(0, 35, 75, 0, math.pi)
    c.curve_to(-75, 20, -60, -20, 0, -95)
    fill_stroke(c, "#4cc9f0", BLUE, 6)
    circle(c, -25, 30, 12, "#ffffff")


def _chart(c, t):
    rr(c, -95, -80, 190, 160, 16)
    fill_stroke(c, "#ffffff")
    c.move_to(-70, 50)
    for x, y in ((-35, 20), (0, 30), (35, -20), (70, -55)):
        c.line_to(x, y)
    c.set_line_width(10)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    col(c, GREEN)
    c.stroke()


_DRAW = {
    "coin": _coin, "lemon": _lemon, "cup": _cup, "jar": _jar, "pizza": _pizza, "slice": _slice,
    "apple": _apple, "cookie": _cookie, "toy": _toy, "book": _book, "bulb": _bulb, "heart": _heart,
    "star": _star, "letter": _letter, "phone": _phone, "laptop": _laptop, "robot": _robot,
    "cloud": _cloud, "server": _server, "lock": _lock, "key": _key, "gift": _gift, "seed": _seed,
    "tree": _tree, "battery": _battery, "stand": _stand, "shop": _shop, "bank": _bank,
    "house": _house, "truck": _truck, "rocket": _rocket, "piggy": _piggy, "box": _box,
    "chip": _chip, "water": _water, "chart": _chart,
}
NAMES = tuple(_DRAW)


def prop(c, name, x, y, size=200, t=0.0, rot=0.0):
    """Draw prop `name` centred at (x, y), `size` px wide. Unknown names draw a star."""
    if size <= 0.5:
        return
    with T(c, x, y, size / 200.0, rot):
        _DRAW.get(name, _star)(c, t)


FOODS = {"pizza", "slice", "stand", "lemon", "cookie", "apple", "cup", "jar"}
PASTELS = ("#ffd6e0", "#c1f0e1", "#fff1b8", "#cde7ff", "#e6d9ff", "#ffe0c2")


def pie(c, x, y, r, pieces=8, cuts=None, missing=(), out=(), out_d=0.0, style="pizza", icon=None, t=0.0):
    """A whole split into `pieces`: a pizza (food analogies) or a pastel 'plain' pie with a small icon
    of the whole thing on every piece. cuts: how many cut lines are drawn (float for animation)."""
    n = max(2, int(pieces))
    for i in range(n):
        if i in missing:
            continue
        a0, a1 = -math.pi / 2 + i * 2 * math.pi / n, -math.pi / 2 + (i + 1) * 2 * math.pi / n
        am = (a0 + a1) / 2
        d = out_d if i in out else 0
        px, py = x + math.cos(am) * d, y + math.sin(am) * d
        if style == "pizza":
            _slice_path(c, px, py, r, a0, a1)
        else:
            c.move_to(px, py)
            c.arc(px, py, r, a0, a1)
            c.close_path()
            fill_stroke(c, PASTELS[i % len(PASTELS)], INK, max(3, r * 0.02))
            if icon:
                prop(c, icon, px + math.cos(am) * r * 0.62, py + math.sin(am) * r * 0.62,
                     min(r * 0.42, r * 2.6 / n), t)
    if cuts is not None:
        k = int(cuts)
        c.set_line_width(max(3, r * 0.025))
        col(c, "#b5651d" if style == "pizza" else INK)
        for i in range(min(k + 1, n)):
            f = 1.0 if i < k else cuts - k
            if f <= 0:
                continue
            a = -math.pi / 2 + i * 2 * math.pi / n
            c.move_to(x, y)
            c.line_to(x + math.cos(a) * r * f, y + math.sin(a) * r * f)
            c.stroke()


def piece_center(x, y, r, i, pieces):
    n = max(2, int(pieces))
    am = -math.pi / 2 + (i + 0.5) * 2 * math.pi / n
    return x + math.cos(am) * r * 0.6, y + math.sin(am) * r * 0.6


def stand_big(c, t=0.0, big=False, label="LEMONADE", top="", coins=None):
    """Lemonade-stand style market stall, ground at y=0, ~540 tall. Used for the 'stand' prop and places."""
    w = 520 if big else 380
    for px in (-w / 2 + 20, w / 2 - 40):
        rr(c, px, -420, 20, 420, 6)
        col(c, "#9c6644")
        c.fill()
    rr(c, -w / 2, -230, w, 230, 16)
    fill_stroke(c, "#d4a373", "#9c6644", 6)
    for i in range(1, 4):
        c.move_to(-w / 2 + 10, -230 + i * 57)
        c.line_to(w / 2 - 10, -230 + i * 57)
        c.set_line_width(4)
        col(c, "#b5835a")
        c.stroke()
    rr(c, -w / 2 - 20, -250, w + 40, 26, 10)
    col(c, "#9c6644")
    c.fill()
    sw = 330 if big else 270
    rr(c, -sw / 2, -170, sw, 90, 20)
    fill_stroke(c, "#fff3b0", "#e0a800", 6)
    text(c, label[:12].upper(), 0, -127, 56 if big else 46, ORANGE, max_w=sw - 30)
    aw = w + 60
    stripes = 8 if big else 6
    sw_ = aw / stripes
    for i in range(stripes):
        x0 = -aw / 2 + i * sw_
        c.move_to(x0, -520)
        c.line_to(x0 + sw_, -520)
        c.line_to(x0 + sw_, -440)
        c.arc(x0 + sw_ / 2, -440, sw_ / 2, 0, math.pi)
        c.close_path()
        col(c, PINK if i % 2 == 0 else "#ffffff")
        c.fill()
    rr(c, -aw / 2 - 10, -540, aw + 20, 30, 12)
    col(c, "#d62f5a")
    c.fill()
    if big:
        rr(c, -230, -680, 460, 120, 30)
        fill_stroke(c, YELLOW, ORANGE, 8)
        text(c, (top or "BIG!")[:10].upper(), 0, -620, 72, "#ffffff", outline=ORANGE, olw=12, max_w=420)
        for i in range(12):
            bx = -210 + i * 38.2
            on = (int(t * 4) + i) % 2 == 0
            for by in (-690, -550):
                circle(c, bx, by, 9, "#fff7c2" if on else "#f4a259")
    with T(c, -w / 2 + 90, -300, 0.55):
        _cup(c, t)
    with T(c, 10, -300, 0.5):
        _cup(c, t)
    with T(c, 70, -300, 0.5):
        _cup(c, t)
    if coins is not None:
        with T(c, w / 2 - 80, -320, 0.55):
            rr(c, -70, -60, 140, 150, 30)
            fill_stroke(c, "#dff3ff", "#7aa6c2", 6)
            for i in range(min(int(coins), 9)):
                row, k = divmod(i, 3)
                with T(c, -38 + k * 38 + (row % 2) * 10, 60 - row * 26, 0.22):
                    _coin(c, 0)


def place(c, name, x, y, s=1.0, t=0.0, label="", coins=None, big=False, top=""):
    """Draw a 'place' large, standing on the ground at (x, y). Stands get their full drawing."""
    if name == "stand":
        with T(c, x, y, s):
            stand_big(c, t, big=big, label=label or "LEMONADE", top=top, coins=coins)
        return
    size = 460 * s * (1.25 if big else 1.0)
    prop(c, name, x, y - size / 2, size, t)
    if label:
        from agents.kids.draw import card
        with T(c, x, y - size * 1.02, 1):
            card(c, 0, 0, max(200, len(label) * 26 + 60), 70, "#fff3b0", "#e0a800", 5, 30)
            text(c, label[:16], 0, 0, 40, ORANGE, max_w=420)
    if big:
        for i in range(5):
            sparkle(c, x - size / 2 + i * size / 4, y - size - 30 + (i % 2) * 40, 14 + 6 * math.sin(t * 7 + i))
