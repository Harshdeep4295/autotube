"""
Script rules, checked on every script before it is rendered (both tracks).

They follow the usual shape of a video people finish: the first 15 seconds confirm the title and
open a question, no channel talk in the first 45 seconds, the answer is said out loud near the
end, one ask at the close, and no sentence said twice. `check_script` returns the broken rules as
plain sentences, which the script writers send back to the model as fix instructions.

    python -m agents.script_rules outputs/<job>/script.json
"""

import json
import re
import sys
from typing import Dict, List

from agents.packaging import content_words, packaging_problems

WPM = 140
HOOK_WORDS = round(15 / 60 * WPM)       # ≈ the first 15 seconds
TURN_WORDS = round(45 / 60 * WPM)       # ≈ the first 45 seconds
INTRO = re.compile(r"\b(welcome( back)?|in this video|in today's video|today we('ll| will| are)|before we (get )?start|"
                   r"let's get started|subscribe|like and|hit the bell|my channel|this channel)\b", re.I)
PAYOFF = re.compile(r"\b(that('s| is) (why|how|what)|now you know|so that('s| is)|here('s| is) the answer|"
                    r"and that('s| is) (it|all)|so,? (a|an|the) .{3,40} (is|are|means)\b)", re.I)
ASKS = {"subscribe": r"\bsubscribe\b", "like": r"\b(like (this|the) video|hit like|leave a like|thumbs up)\b",
        "comment": r"\bcomments?\b", "share": r"\bshare (this|the|it)\b", "watch next": r"\bwatch (the )?(next|full|whole)\b",
        "bell": r"\bbell\b"}


def spoken_lines(script: Dict) -> List[str]:
    """Narration in order: kids scripts keep it in scenes → lines, explainers in shots."""
    if isinstance(script.get("shots"), list):
        return [str(s.get("text", "")).strip() for s in script["shots"] if isinstance(s, dict) and str(s.get("text", "")).strip()]
    return [str(ln.get("text", "")).strip() for sc in script.get("scenes", []) if isinstance(sc, dict)
            for ln in sc.get("lines", []) if str(ln.get("text", "")).strip()]


def _head(lines: List[str], words: int) -> str:
    out, n = [], 0
    for t in lines:
        if n >= words:
            break
        out.append(t)
        n += len(t.split())
    return " ".join(out)


def _norm(t: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", t.lower()))


def repeated_lines(lines: List[str]) -> List[str]:
    seen, out = set(), []
    for t in lines:
        for sent in re.split(r"(?<=[.!?])\s+", t):
            k = _norm(sent)
            if len(k.split()) < 5:
                continue
            if k in seen and sent not in out:
                out.append(sent)
            seen.add(k)
    return out


def check_script(script: Dict) -> List[str]:
    lines = spoken_lines(script)
    if not lines:
        return ["the script has no narration"]
    title = str(script.get("title", ""))
    out = list(packaging_problems(title, str(script.get("thumbnail_text", ""))))

    hook = _head(lines, HOOK_WORDS)
    if title and not set(content_words(title)) & set(content_words(hook)):
        out.append("the first 15 seconds never mention what the title promises; name it in the first line")
    if "?" not in hook:
        out.append("the first 15 seconds ask no question; open with the question the viewer has")
    if not re.search(r"\byou(r|'ll|'re)?\b", hook, re.I):
        out.append('the first 15 seconds never speak to the viewer; say "you" and what they will get')
    m = INTRO.search(_head(lines, TURN_WORDS))
    if m:
        out.append(f'"{m.group(0)}" in the first 45 seconds: no welcome, channel talk or subscribe pitch before the content')

    tail = lines[len(lines) * 2 // 3:]
    if not any(PAYOFF.search(t) for t in tail):
        out.append('the answer is never said out loud near the end; add one line that starts "That is why", '
                   '"That is how" or "Now you know" and states it')
    close = " ".join(lines[-3:])
    asks = [name for name, rx in ASKS.items() if re.search(rx, close, re.I)]
    if len(asks) > 1:
        out.append(f"the close asks for {len(asks)} things ({', '.join(asks)}); keep one")
    rep = repeated_lines(lines)
    if rep:
        out.append("said twice: " + " | ".join(f'"{r}"' for r in rep[:3]) + "; say each thing once")
    return out


if __name__ == "__main__":
    for path in sys.argv[1:]:
        s = json.loads(open(path).read())
        problems = check_script(s)
        print(f"{path}\n  {s.get('title', '')}\n  " + ("\n  ".join(f"x {p}" for p in problems) if problems else "ok: every rule passes"))
