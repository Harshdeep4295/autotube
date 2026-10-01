"""The recurring cast. Same kids every episode — a series identity, not one-off clip art."""

import math

import cairo

from agents.kids.draw import INK, T, circle, col, rr

CAST = {
    # main cast
    "mia": dict(skin="#f1c27d", hair="#5a3825", shirt="#ef476f", style="buns"),
    "leo": dict(skin="#c68642", hair="#1b1b1b", shirt="#118ab2", style="spiky"),
    "zoe": dict(skin="#ffdbac", hair="#e07a1f", shirt="#06d6a0", style="pony"),
    # friends (crowds, customers, buyers)
    "sam": dict(skin="#8d5524", hair="#2b2b2b", shirt="#9b5de5", style="spiky"),
    "ava": dict(skin="#e0ac69", hair="#6f4e37", shirt="#f15bb5", style="buns"),
    "raj": dict(skin="#c68642", hair="#222222", shirt="#fee440", style="short"),
    "kim": dict(skin="#f1c27d", hair="#333333", shirt="#00bbf9", style="pony"),
}
MAIN = ("mia", "leo", "zoe")
FRIENDS = ("sam", "ava", "raj", "kim")


def kid(c, who, x, y, s=1.0, t=0.0, mood="happy", wave=0.0, hold=None, bounce=True, flip=False):
    """Draw a cast member standing with feet at (x, y). hold(c, hx, hy) draws something in the raised hand."""
    look = CAST.get(who, CAST["mia"])
    skin, hair, shirt, style = look["skin"], look["hair"], look["shirt"], look["style"]
    by = -abs(math.sin(t * 3.2 + x * 0.01)) * 8 if bounce else 0
    with T(c, x, y + by, s):
        if flip:
            c.scale(-1, 1)
        c.set_line_cap(cairo.LINE_CAP_ROUND)
        for lx in (-22, 22):
            c.move_to(lx, -90)
            c.line_to(lx, -8)
            c.set_line_width(20)
            col(c, skin)
            c.stroke()
            rr(c, lx - 18, -18, 38, 20, 10)
            col(c, "#3d405b")
            c.fill()
        c.move_to(-40, -210)
        c.line_to(40, -210)
        c.line_to(62, -80)
        c.curve_to(30, -70, -30, -70, -62, -80)
        c.close_path()
        col(c, shirt)
        c.fill()
        c.move_to(-38, -195)
        c.line_to(-70, -120)
        c.set_line_width(18)
        col(c, skin)
        c.stroke()
        if hold:
            ang = -1.0
        elif wave:
            ang = -2.3 + math.sin(t * 9) * 0.45
        else:
            ang = -0.3
        ax, ay = 38 + math.cos(ang) * 80, -195 + math.sin(ang) * 80
        c.move_to(38, -195)
        c.line_to(ax, ay)
        c.stroke()
        circle(c, -70, -118, 12, skin)
        circle(c, ax, ay, 12, skin)
        if hold:
            c.save()
            if flip:
                c.scale(-1, 1)
                hold(c, -(ax + 10), ay - 30)
            else:
                hold(c, ax + 10, ay - 30)
            c.restore()
        hy = -275
        if style == "buns":
            circle(c, -52, hy - 55, 26, hair)
            circle(c, 52, hy - 55, 26, hair)
        circle(c, 0, hy, 68, skin)
        c.arc(0, hy, 70, math.pi * 1.05, math.pi * 1.95)
        c.close_path()
        col(c, hair)
        c.fill()
        if style == "spiky":
            for i in range(5):
                a = math.pi * (1.15 + i * 0.17)
                c.move_to(62 * math.cos(a - 0.12), hy + 62 * math.sin(a - 0.12))
                c.line_to(90 * math.cos(a), hy + 90 * math.sin(a))
                c.line_to(62 * math.cos(a + 0.12), hy + 62 * math.sin(a + 0.12))
                col(c, hair)
                c.fill()
        elif style == "pony":
            c.move_to(55, hy - 40)
            c.curve_to(110, hy - 30, 110, hy + 40, 80, hy + 60)
            c.curve_to(90, hy, 70, hy - 20, 50, hy - 20)
            col(c, hair)
            c.fill()
        blink = (t % 3.3) < 0.12
        for ex in (-24, 24):
            if blink:
                c.move_to(ex - 9, hy - 2)
                c.line_to(ex + 9, hy - 2)
                c.set_line_width(5)
                col(c, INK)
                c.stroke()
            else:
                circle(c, ex, hy - 4, 10, INK)
                circle(c, ex + 3, hy - 8, 3.5, "#ffffff")
        circle(c, -40, hy + 20, 11, "#ff8fa3")
        circle(c, 40, hy + 20, 11, "#ff8fa3")
        c.set_line_width(6)
        col(c, INK)
        if mood == "sad":
            c.arc(0, hy + 38, 16, 1.2 * math.pi, 1.8 * math.pi)
            c.stroke()
            c.move_to(-34, hy - 26)
            c.line_to(-14, hy - 20)
            c.move_to(34, hy - 26)
            c.line_to(14, hy - 20)
            c.set_line_width(4)
            c.stroke()
        elif mood == "wow":
            c.arc(0, hy + 26, 11, 0, 2 * math.pi)
            c.fill()
        else:
            c.arc(0, hy + 14, 20, 0.15 * math.pi, 0.85 * math.pi)
            c.stroke()
