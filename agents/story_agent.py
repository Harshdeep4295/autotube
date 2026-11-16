"""
Tech story of the day: on story days (every other day from STORY_START, a side-by-side test
against the tool and new-model videos), the explainer is "what happened and what it means for
you" about one of the last day and a half's biggest tech / AI news stories.

  1. headlines from a few big tech news feeds, newest first
  2. Claude (owner's subscription; free models without it) picks up to three that a curious
     non-expert would want explained, best first
  3. the first pick that is not a repeat (topic_judge) and whose article can be read (the script
     is grounded in it; numbers are checked against it) becomes the topic

No usable story → None, and the day's usual topic (plan, bank) is made instead.
"""

import html
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)

FEEDS = (
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://techcrunch.com/feed/",
    "https://www.engadget.com/rss.xml",
)
MAX_AGE_HOURS = 36
MIN_ARTICLE_CHARS = 1500
STORY_START = date(2026, 11, 17)   # first story day; then every other day

PROMPT = """You pick today's TECH STORY video for the YouTube channel "{channel}". The video (about 5
minutes) explains one news story to curious non-experts: what happened, how the technology behind
it works in plain words, and what it means for the viewer. It is made from the article alone.

Good picks: news many people will hear about and wonder "how does that work?" or "what does that
mean for me?" (a big AI launch or failure, a rocket or satellite event, a security breach that
affects users, a new device or chip, a change to an app millions use, an energy or science
breakthrough). Bad picks: only a stock move, lawsuit, deal, job cut or executive news; politics;
crime, war, deaths; gossip; reviews and shopping lists; a story the article cannot explain.

HEADLINES (n | source | hours old | headline - summary):
{headlines}

ALREADY ON THE CHANNEL (never the same story or idea):
{made}

Return JSON only, best first, at most 3:
{{"picks": [{{"n": <headline number>, "topic": "<What happened, in a few words>: <the question or
what it means for you>", "why": "<a few words>"}}]}}"""


def is_story_day(day: Optional[date] = None) -> bool:
    day = day or datetime.now(timezone.utc).date()
    return config.EXPLAINER_STORIES and day >= STORY_START and (day - STORY_START).days % 2 == 0


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text or ""))).strip()


def headlines(max_age_hours: int = MAX_AGE_HOURS) -> List[Dict]:
    import feedparser
    now = datetime.now(timezone.utc)
    out, seen = [], set()
    for url in FEEDS:
        try:
            entries = feedparser.parse(url).entries[:20]
        except Exception as e:  # noqa: BLE001 — one dead feed must not lose the others
            logger.warning(f"[story] feed failed {url}: {str(e)[:100]}")
            continue
        for e in entries:
            t = e.get("published_parsed") or e.get("updated_parsed")
            when = datetime(*t[:6], tzinfo=timezone.utc) if t else None
            age = (now - when).total_seconds() / 3600 if when else None
            title = _clean(e.get("title", ""))
            if not title or not e.get("link") or (age is not None and age > max_age_hours):
                continue
            key = re.sub(r"[^a-z0-9]", "", title.lower())[:60]
            if key in seen:
                continue
            seen.add(key)
            out.append({"title": title, "summary": _clean(e.get("summary", ""))[:240], "url": e["link"],
                        "source": url.split("/")[2].replace("www.", "").replace("feeds.", ""),
                        "age": round(age, 1) if age is not None else None})
    out.sort(key=lambda h: h["age"] if h["age"] is not None else 99)
    logger.info(f"[story] {len(out)} headlines from the last {max_age_hours} hours")
    return out


def _ask(prompt: str) -> str:
    from agents import claude_writer
    if claude_writer.available():
        return claude_writer.ask(prompt, timeout=300)
    from agents.llm import FreeLLM
    return FreeLLM().complete("You pick news stories for a tech explainer channel. Reply with JSON only.",
                              prompt, max_tokens=800, temperature=0.3)


def pick(made: List[str]) -> Optional[Dict]:
    """Today's story as an explainer topic (kind "story"), or None."""
    from agents.source_fetcher import fetch_text
    from agents.topic_judge import same_as
    heads = headlines()
    if not heads:
        return None
    heads = heads[:45]
    listing = "\n".join(f"{i} | {h['source']} | {h['age'] if h['age'] is not None else '?'} | {h['title']} - {h['summary']}"
                        for i, h in enumerate(heads, 1))
    try:
        text = _ask(PROMPT.format(channel=config.CHANNEL_NAME, headlines=listing,
                                  made="\n".join(f"- {m}" for m in made[-60:]) or "(none)"))
        m = re.search(r"\{.*\}", text or "", re.S)
        picks = (json.loads(m.group(0)) if m else {}).get("picks") or []
    except Exception as e:  # noqa: BLE001 — the usual topic is made instead
        logger.warning(f"[story] no pick ({str(e)[:150]})")
        return None
    for p in picks[:3]:
        try:
            h = heads[int(p.get("n")) - 1]
        except (TypeError, ValueError, IndexError):
            continue
        topic = str(p.get("topic") or h["title"]).strip()
        dup = same_as(topic, made, "explainer")
        if dup:
            logger.info(f"[story] '{topic[:60]}' is the same as '{dup[1][:50]}' — next pick")
            continue
        article = fetch_text(h["url"], limit=8000)
        if len(article) < MIN_ARTICLE_CHARS:
            logger.info(f"[story] article too short to explain ({len(article)} chars): {h['url'][:90]}")
            continue
        logger.info(f"[story] → {topic[:80]} ({h['source']}, {h['age']} h old; {str(p.get('why', ''))[:60]})")
        return {"topic": topic, "kind": "story", "source": "story", "url": h["url"], "source_url": h["url"],
                "summary": f"{h['title']}. {h['summary']}", "headline": h["title"]}
    logger.info("[story] no usable story today — the usual topic instead")
    return None


def slot(day: str) -> Dict:
    """The week plan's entry for a story day: picked on the morning itself, from that day's news."""
    return {"topic": "Tech story of the day (picked that morning from the news)", "kind": "story", "slot": True,
            "planned": True, "why": "side-by-side test: a tech news story every other day", "date": day}
