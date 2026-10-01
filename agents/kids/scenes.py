"""One draw function per catalogue scene. Signature: fn(c, t, S) with t = seconds since scene start.

S = {"props": {...}, "beats": [t0, t1, ...] (seconds from scene start), "dur": float, "weather": str}
Beat k is fired by narration line k (or its cue word) — see agents/kids/timeline.py.
"""

import math
import random

from agents.kids.cast import FRIENDS, kid
from agents.kids.draw import (BLUE, GREEN, H, INK, ORANGE, PINK, PURPLE, W, YELLOW, T, arrow, badge, bubble,
                              card, circle, col, confetti, ease_io, ease_out, lerp, pop, prog, rr, sparkle,
                              text, text_block)
from agents.kids.props import FOODS, pie, place, prop

CHART_PTS = {"up": [0.1, 0.2, 0.18, 0.4, 0.5, 0.75, 0.9], "down": [0.9, 0.8, 0.82, 0.6, 0.55, 0.35, 0.2],
             "bouncy": [0.5, 0.8, 0.3, 0.75, 0.25, 0.7, 0.35, 0.8]}


def B(S, k):
    b = S["beats"]
    return b[min(k, len(b) - 1)] if b else 0.0


def num(v):
    v = float(v or 0)
    return str(int(v)) if v == int(v) else f"{v:g}"


def count_tag(c, x, y, s, unit, n, t, color=INK, label=""):
    with T(c, x, y, s):
        w = 380 if label else 250
        card(c, 0, 0, w, 100, "#ffffff", INK, 5, 40)
        if label:
            text(c, label, -w / 2 + 25, 0, 40, INK, align="l")
        prop(c, unit, (5 if label else -65), 0, 64, t)
        text(c, f"x {num(n)}", (60 if label else -20), 0, 50, color, align="l")


def price_tag(c, x, y, s, unit, n, t, color=INK):
    with T(c, x, y, s):
        c.move_to(-120, -60)
        for px, py in ((120, -60), (160, 0), (120, 60), (-120, 60)):
            c.line_to(px, py)
        c.close_path()
        col(c, "#ffffff")
        c.fill_preserve()
        col(c, INK)
        c.set_line_width(6)
        c.stroke()
        circle(c, 128, 0, 10, INK)
        prop(c, unit, -55, 0, 70, t)
        text(c, num(n), 40, 0, 70, color, max_w=120)


def chart_panel(c, x, y, w, h, pts, p, colr, t=0.0, ball=False):
    with T(c, x, y):
        rr(c, 0, 0, w, h, 30)
        col(c, "#ffffff")
        c.fill_preserve()
        col(c, INK)
        c.set_line_width(6)
        c.stroke()
        c.set_line_width(2)
        col(c, "#d9e2ec")
        for i in range(1, 4):
            c.move_to(30, h * i / 4)
            c.line_to(w - 30, h * i / 4)
            c.stroke()
        n = len(pts) - 1
        seg = p * n
        P = [(40 + (w - 80) * i / n, h - 40 - (h - 80) * v) for i, v in enumerate(pts)]
        c.move_to(*P[0])
        last = P[0]
        for i in range(1, n + 1):
            if seg >= i:
                c.line_to(*P[i])
                last = P[i]
            else:
                f = seg - (i - 1)
                last = (lerp(P[i - 1][0], P[i][0], f), lerp(P[i - 1][1], P[i][1], f))
                c.line_to(*last)
                break
        c.set_line_width(12)
        col(c, colr)
        c.stroke()
        if ball:
            circle(c, last[0], last[1] - 26, 26, PINK, INK, 5)
            sparkle(c, last[0] - 8, last[1] - 34, 7)
        else:
            circle(c, last[0], last[1], 14, colr)


# ── scenes ───────────────────────────────────────────────────────────────────
def s_title(c, t, S):
    p = S["props"]
    with T(c, W / 2, 360 + math.sin(t * 2) * 8, pop(t, 0.0, 0.7)):
        card(c, 0, 0, 1300, 330, "#ffffff", INK, 10, 70)
        text_block(c, p["question"], 0, 0, 96, GREEN, max_w=1180, max_rows=2)
    for i, name in enumerate(p.get("props") or []):
        x = (330, 960, 1590)[i % 3]
        prop(c, name, x, 700 + math.sin(t * 3 + i) * 12, 150 * pop(t, B(S, 1) + i * 0.15), t)
    kid(c, "mia", 1720, 900, 0.8 * pop(t, B(S, 2)), t, wave=1)


def s_meet(c, t, S):
    p = S["props"]
    b1, b2 = B(S, 1), B(S, 2)
    has_flow = len(S["beats"]) >= 3 and t > b2
    coins = min(9, max(0, int((t - b2 - 0.8) * 2.2))) if has_flow else 0
    place(c, p["place"], 1150, 830, 0.85 * pop(t, b1, 0.6), t, label=p.get("label") or "",
          coins=coins if p["place"] == "stand" else None)
    wx = lerp(-200, 560, ease_out(prog(t, 0.0, 1.4)))
    kid(c, p["who"], wx, 870, 1.05, t, wave=1 if t < b1 + 0.5 else 0)
    if p.get("greeting") and 0.3 < t < max(b1, 1.6):
        with T(c, 560, 360, pop(t, 0.4)):
            bubble(c, 0, 0, 420, 130)
            text(c, p["greeting"], 0, 0, 52, PINK, max_w=380)
    if has_flow:
        lt = t - b2
        for i in range(4):
            ph = lt - i * 1.1
            if ph < 0:
                continue
            ph %= 4.4
            cx = lerp(2100, 1560, ease_out(clamp01(ph / 1.2)))
            kid(c, FRIENDS[i % 4], cx, 890, 0.72, t, bounce=ph < 1.2)
            if 1.2 < ph < 2.0:
                f = ease_io((ph - 1.2) / 0.8)
                prop(c, p["flow"], lerp(cx - 60, 1300, f), lerp(640, 520, f) - math.sin(f * math.pi) * 160, 56, t)
        if p["place"] != "stand":
            count_tag(c, 1150, 250, pop(t, b2 + 0.5), p["flow"], coins, t)


def clamp01(x):
    return max(0.0, min(1.0, x))


def s_wants(c, t, S):
    p = S["props"]
    b1, b2 = B(S, 1), B(S, 2)
    sad = len(S["beats"]) >= 3 and t > b2
    kid(c, p["who"], 430, 880, 1.05, t, mood="sad" if sad else "wow")
    with T(c, 820, 330, pop(t, 0.2, 0.6)):
        bubble(c, 0, 0, 640, 480, thought=True)
        c.save()
        c.rectangle(-310, -230, 620, 460)
        c.clip()
        place(c, p["dream"], 0, 205, 0.5, t, label=p.get("dream_label") or "", big=True, top=p.get("dream_label") or "")
        for i in range(5):
            sparkle(c, -250 + i * 120, -170 + (i % 2) * 80, 16 + 8 * math.sin(t * 6 + i), 0.9)
        c.restore()
    if t > b1:
        count_tag(c, 1480, 330, 1.2 * pop(t, b1), p["unit"], p["need"], t, PINK, "Need")
    if sad:
        count_tag(c, 1480, 490, 1.2 * pop(t, b2), p["unit"], p["have"], t, INK, "Have")


def s_split(c, t, S):
    p = S["props"]
    n = p["pieces"]
    b0, b1, b2, b3 = B(S, 0), B(S, 1), B(S, 2), B(S, 3)
    multi = len(S["beats"]) >= 2
    kid(c, p["who"], 330, 880, 1.05, t, mood="wow" if t < b1 else "happy")
    if t < b2 or not multi:
        with T(c, 330, 380 + math.sin(t * 4) * 6, pop(t, b0 + 0.1) * (1 - prog(t, b2, 0.3) if multi else 1)):
            prop(c, "bulb", 0, 0, 200, t)
    m = ease_io(prog(t, b1, 0.9)) if multi else 1.0
    if m < 1:
        place(c, p["whole"], 1150, 830, 0.85 * (1 - m), t, label="")
    if m > 0:
        cuts = n * ease_io(prog(t, b2, 1.6)) if len(S["beats"]) >= 3 else n
        out_d = 110 * ease_out(prog(t, b3, 0.6)) if len(S["beats"]) >= 4 else 0
        with T(c, 1150, 430, m):
            style = "pizza" if p["whole"] in FOODS else "plain"
            pie(c, 0, 0, 290, n, cuts=cuts, out=(1,), out_d=out_d, style=style, icon=p["whole"], t=t)
            if p.get("whole_label") and out_d <= 0:
                text(c, p["whole_label"], 0, 360, 56, INK, outline="#ffffff", olw=12, max_w=700)
        if out_d > 0:
            badge(c, 1620, 250, pop(t, b3 + 0.3), p["piece_name"])


def s_trade(c, t, S):
    p = S["props"]
    buyers = p["buyers"]
    n = len(buyers)
    xs = [1180 + i * (560 / max(1, n - 1)) if n > 1 else 1450 for i in range(n)]
    got = 0
    kid(c, p["seller"], 330, 880, 1.05, t, wave=1 if t < B(S, 1) else 0)
    # stack of what the seller gives, top-centre
    with T(c, 800, 330, pop(t, 0.1)):
        given = sum(1 for i in range(n) if t > B(S, i + 1))
        if p["gives"] == "slice":
            total = max(n + 2, 8)
            gone = given if t < B(S, n) + 1.6 else total   # "soon every slice is sold"
            if gone < total:
                pie(c, 0, 0, 150, total, cuts=total, missing=tuple(range(gone)))
            else:
                text(c, "SOLD!", 0, 0, 80 * pop(t, B(S, n) + 1.6), PINK, outline="#ffffff", olw=12)
        else:
            card(c, 0, 0, 300, 220, "#ffffff", INK, 5, 40)
            for k in range(max(0, n - given)):
                prop(c, p["gives"], -90 + k * 60, 0, 110, t)
    for i, who in enumerate(buyers):
        bt = B(S, i + 1)
        has = t > bt + 0.8
        kid(c, who, xs[i], 880, 0.95, t, hold=(lambda cc, hx, hy, g=p["gives"]: prop(cc, g, hx, hy, 80, t)) if has else None)
        lt = t - bt
        if 0 < lt < 0.8:
            f = ease_io(lt / 0.8)
            prop(c, p["gives"], lerp(800, xs[i] + 60, f), lerp(330, 540, f) - math.sin(f * math.pi) * 120, 90, t)
        if 0.6 < lt < 1.8:
            for j in range(3):
                f = ease_io(clamp01((lt - 0.6 - j * 0.12) / 0.9))
                if 0 < f < 1:
                    prop(c, p["gets"], lerp(xs[i] - 40, 380, f), lerp(620, 560, f) - math.sin(f * math.pi) * 200, 56, t)
        if t > bt + 1.2:
            got += 1
    each = p.get("each") or 1
    count_tag(c, 330, 330, pop(t, B(S, 1) + 1.0), p["gets"], got * each, t, GREEN if got == n else INK)


def s_grow(c, t, S):
    p = S["props"]
    b1, b2 = B(S, 1), B(S, 2)
    g = ease_io(prog(t, b1, 1.0)) if len(S["beats"]) >= 2 else 0
    s = lerp(0.55, 1.0, g)
    name = p["small"] if g < 0.5 else p["big"]
    place(c, name, 1150, 830, s * pop(t, 0.0), t, label=(p.get("label_before") if g < 0.5 else p.get("label_after")) or "",
          big=g >= 0.5, top=p.get("label_after") or "")
    if g > 0:
        for i in range(7):
            sparkle(c, 800 + i * 110, 200 + (i % 2) * 90, (18 + 10 * math.sin(t * 7 + i)) * g)
    kid(c, p["who"], 380, 880, 1.05, t, wave=1 if t > b2 and len(S["beats"]) >= 3 else 0,
        mood="wow" if g > 0 else "happy")


def s_crowd(c, t, S):
    p = S["props"]
    b1, b2 = B(S, 1), B(S, 2)
    with T(c, 960, 250, pop(t, 0.0) * 1.0, math.sin(t * 2) * 0.05):
        prop(c, p["thing"], 0, 0, 320, t)
    if p.get("label"):
        text(c, p["label"], 960, 470, 54, INK, outline="#ffffff", olw=12, max_w=900)
    shouts = p["shouts"]
    for i in range(4):
        x = 300 + i * 440
        kid(c, FRIENDS[i], x, 900, 0.72, t, wave=1, mood="wow")
        if i < len(shouts) and t > b1:
            with T(c, x + 20, 585, pop(t, b1 + i * 0.25)):
                bubble(c, 0, 0, 200, 90)
                text(c, shouts[i], 0, 0, 40, PINK, max_w=170)
    if len(S["beats"]) >= 3 and t > b2:
        rnd = random.Random(4)
        for i in range(10):
            x0 = rnd.uniform(200, 1700)
            y = 800 - ((t - b2) * 180 + rnd.uniform(0, 400)) % 700
            prop(c, "heart", x0 + math.sin(t * 2 + i) * 20, y, 50, t)


def s_chart(c, t, S):
    p = S["props"]
    mode = p["mode"]
    colr = {"up": GREEN, "down": PINK, "bouncy": BLUE}[mode]
    end = B(S, 2) if len(S["beats"]) >= 3 else S["dur"] - 0.5
    pp = ease_io(prog(t, 0.2, max(1.5, end - 0.2))) if mode != "bouncy" else prog(t, 0.2, max(2.0, S["dur"] - 0.6))
    chart_panel(c, 160, 190, 1000, 560, CHART_PTS[mode], pp, colr, t, ball=(mode == "bouncy"))
    if p.get("title"):
        with T(c, 660, 120, pop(t, B(S, 1))):
            text(c, p["title"], 0, 0, 64, colr, outline="#ffffff", olw=14, max_w=1000)
    if mode != "bouncy":
        y0, y1 = (700, 260) if mode == "up" else (260, 700)
        arrow(c, 1300, y0, 1300, y1, colr, ease_out(prog(t, end - 0.2, 0.5)), 26)
    kid(c, p["who"], 1620, 880, 1.0, t, mood="sad" if mode == "down" else ("wow" if mode == "bouncy" else "happy"),
        wave=1 if mode == "up" else 0)


def s_price(c, t, S):
    p = S["props"]
    b1 = B(S, 1)
    changed = len(S["beats"]) >= 2 and t > b1
    up = (p["new"] or 0) >= (p["old"] or 0)
    colr = GREEN if up else PINK
    kid(c, p["who"], 600, 880, 1.15, t, hold=lambda cc, hx, hy: prop(cc, p["item"], hx, hy, 130, t),
        mood=("happy" if up else "sad") if changed else "happy")
    with T(c, 1250, 450, pop(t, 0.2)):
        if not changed:
            price_tag(c, 0, 0, 1.4, p["unit"], p["old"], t)
        else:
            s = pop(t, b1, 0.5)
            price_tag(c, 0, 0, 1.4 * s, p["unit"], p["new"], t, colr)
            with T(c, 0, -170, s):
                text(c, f"was {num(p['old'])}", 0, 0, 48, INK, outline="#ffffff", olw=10)
    if changed:
        y0, y1 = (700, 280) if up else (280, 700)
        arrow(c, 1650, y0, 1650, y1, colr, ease_out(prog(t, B(S, 2) if len(S["beats"]) >= 3 else b1 + 0.4, 0.5)), 26)


def s_many(c, t, S):
    p = S["props"]
    items = p["items"]
    n = len(items)
    b1, b2, b3 = B(S, 1), B(S, 2), B(S, 3)
    with T(c, W / 2, 830, pop(t, 0.0, 0.7)):
        for i in range(-9, 10):
            rr(c, i * 100 - 8, -80, 16, 80, 6)
            col(c, "#b08968")
            c.fill()
        rr(c, -950, -60, 1900, 14, 6)
        c.fill()
    step = 1700 / n
    for i, it in enumerate(items):
        x = 110 + step * (i + 0.5)
        y = 690 + (i % 2) * 30
        s = pop(t, b1 + i * 0.4) if len(S["beats"]) >= 2 else 1
        prop(c, it["prop"], x, y - 90, min(230, step * 0.8) * s, t)
        with T(c, x, y + 55, s):
            card(c, 0, 0, min(step - 20, 240), 60, "#ffffff", INK, 4, 26)
            text(c, it["label"], 0, 0, 34, INK, max_w=min(step - 40, 220))
    if len(S["beats"]) >= 3 and t > b2:
        lt = t - b2
        rnd = random.Random(7)
        for k in range(8):
            a = rnd.randrange(n)
            b = (a + rnd.randint(1, max(1, n - 1))) % n
            ph = (lt * 0.35 + k * 0.12) % 1.0
            xa, xb = 110 + step * (a + 0.5), 110 + step * (b + 0.5)
            x = lerp(xa, xb, ease_io(ph))
            y = 918 + (k % 3) * 10
            kid(c, FRIENDS[k % 4], x, y, 0.33, t + k, flip=xb < xa)
            prop(c, p["carry"] if k % 2 else "coin", x + 30, y - 120, 36, t)
    if p.get("reveal") and len(S["beats"]) >= 4 and t > b3:
        with T(c, W / 2, 190, pop(t, b3, 0.6), math.sin(t * 3) * 0.03):
            card(c, 0, 0, 1150, 190, GREEN, INK, 10, 60)
            text(c, p["reveal"], 0, 0, 118, "#ffffff", outline=INK, olw=14, max_w=1060)
        confetti(c, t - b3)


def s_steps(c, t, S):
    p = S["props"]
    items = p["items"]
    n = len(items)
    xs = [260 + i * (1400 / max(1, n - 1)) for i in range(n)]
    y = 470
    shown = [t >= B(S, i) for i in range(n)]
    for i in range(n - 1):
        if shown[i + 1]:
            arrow(c, xs[i] + 130, y, xs[i + 1] - 130, y, "#9aa5b1", ease_out(prog(t, B(S, i + 1), 0.5)), 12)
    for i, it in enumerate(items):
        if not shown[i]:
            continue
        s = pop(t, B(S, i))
        with T(c, xs[i], y, s):
            circle(c, 0, 0, 120, "#ffffff", INK, 6)
            prop(c, it["prop"], 0, 0, 160, t)
            card(c, 0, 190, 280, 70, YELLOW, INK, 5, 30)
            text(c, it["label"], 0, 190, 36, INK, max_w=250)
    # traveller moves to the newest step
    cur = max(i for i in range(n) if shown[i]) if any(shown) else 0
    if cur > 0:
        f = ease_io(prog(t, B(S, cur), 0.9))
        x = lerp(xs[cur - 1], xs[cur], f)
        prop(c, p["traveller"], x, y - 190 - math.sin(f * math.pi) * 80, 110, t)
    else:
        prop(c, p["traveller"], xs[0], y - 190, 110 * pop(t, 0.3), t)
    kid(c, "zoe", 1780, 960, 0.6, t, wave=1)


def s_compare(c, t, S):
    p = S["props"]
    b1, b2 = B(S, 1), B(S, 2)
    two = len(S["beats"]) >= 2
    for side, x, bt in (("left", 560, 0.0), ("right", 1360, b1 if two else 0.4)):
        if t < bt:
            continue
        s = pop(t, bt)
        with T(c, x, 460, s):
            card(c, 0, 0, 560, 600, "#ffffff", INK, 8, 50)
            prop(c, p[side]["prop"], 0, -60, 320, t)
            text(c, p[side]["label"], 0, 200, 54, INK, max_w=500)
    text(c, "VS", W / 2, 460, 90 * pop(t, b1 if two else 0.4), PINK, outline="#ffffff", olw=14)
    win = p.get("winner")
    if win in ("left", "right") and len(S["beats"]) >= 3 and t > b2:
        x = 560 if win == "left" else 1360
        prop(c, "star", x + 230, 190, 150 * pop(t, b2), t, math.sin(t * 3) * 0.2)
        for i in range(5):
            sparkle(c, x - 250 + i * 125, 140 + (i % 2) * 40, 16 + 8 * math.sin(t * 7 + i))


def s_reveal(c, t, S):
    p = S["props"]
    with T(c, W / 2, 330, pop(t, 0.0, 0.6), math.sin(t * 3) * 0.03):
        card(c, 0, 0, 1200, 220, GREEN, INK, 10, 70)
        text(c, p["word"], 0, 0, 130, "#ffffff", outline=INK, olw=14, max_w=1100)
    prop(c, p["prop"], 960, 640, 220 * pop(t, 0.4), t)
    if p.get("sub"):
        with T(c, W / 2, 830, pop(t, B(S, 1) if len(S["beats"]) >= 2 else 0.8)):
            card(c, 0, 0, 1300, 100, "#ffffff", INK, 6, 40)
            text(c, p["sub"], 0, 0, 52, INK, max_w=1220)
    confetti(c, t)


def s_talk(c, t, S):
    p = S["props"]
    kid(c, p["who"], 560, 880, 1.15, t, wave=1)
    with T(c, 860, 330, pop(t, B(S, 1) if len(S["beats"]) >= 2 else 0.3)):
        bubble(c, 0, 0, 720, 230, tail_dx=-160)
        text_block(c, p["bubble"], 0, 0, 58, INK, max_w=640, max_rows=2)
    bounce = abs(math.sin(t * 3)) * 30 if len(S["beats"]) >= 3 and t > B(S, 2) else 0
    prop(c, p["prop"], 1450, 640 - bounce, 300 * pop(t, 0.2), t)


def s_recap(c, t, S):
    p = S["props"]
    cards = p["cards"]
    n = len(cards)
    with T(c, W / 2, 120, pop(t, 0.0)):
        text(c, "Let's remember!", 0, 0, 96, PINK, outline="#ffffff", olw=16)
    cw = 520 if n == 3 else 600
    xs = [W / 2 + (i - (n - 1) / 2) * (cw + 70) for i in range(n)]
    for i, cd in enumerate(cards):
        bt = B(S, i + 1)
        if t < bt - 0.01 and len(S["beats"]) > 1:
            continue
        colr = (YELLOW, GREEN, BLUE)[i % 3]
        with T(c, xs[i], 530, pop(t, bt, 0.55), (i - (n - 1) / 2) * 0.03):
            card(c, 0, 0, cw, 600, "#ffffff", colr, 14, 50)
            prop(c, cd["prop"], 0, -100, 280, t)
            text(c, cd["term"], 0, 120, 64, colr, outline=INK, olw=8, max_w=cw - 60)
            text_block(c, "= " + cd["means"], 0, 215, 38, INK, max_w=cw - 70, max_rows=2)


def s_outro(c, t, S):
    p = S["props"]
    cast = p["cast"]
    n = len(cast)
    for i, who in enumerate(cast):
        x = W / 2 + (i - (n - 1) / 2) * 400
        kid(c, who, x, 880, 1.1 * pop(t, i * 0.15), t, wave=1)
    with T(c, W / 2, 200, pop(t, 0.3)):
        text(c, p.get("message") or "Great job, friend!", 0, 0, 110, PINK, outline="#ffffff", olw=18, max_w=1700)
    confetti(c, t - (B(S, 1) if len(S["beats"]) >= 2 else 0.2))


SCENES = {
    "title": s_title, "meet": s_meet, "wants": s_wants, "split": s_split, "trade": s_trade, "grow": s_grow,
    "crowd": s_crowd, "chart": s_chart, "price": s_price, "many": s_many, "steps": s_steps,
    "compare": s_compare, "reveal": s_reveal, "talk": s_talk, "recap": s_recap, "outro": s_outro,
}
