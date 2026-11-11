"""
Plan a week of uploads in one go: one explainer topic and one kids question per day.

    python scripts/plan_week.py                       # 7 days from tomorrow (UTC)
    python scripts/plan_week.py --start 2026-11-16 --days 7
    python scripts/plan_week.py --dry-run             # print the plan, write nothing

Steps:
  1. content database: every video on the channel with its numbers (agents/content_db.py)
  2. topic index: vectors for every subject, so repeats are found by meaning (agents/topic_index.py)
  3. what is trending: most-viewed niche videos on YouTube this week (agents/youtube_trends.py) and
     new open models on Hugging Face (agents/trend_agent.py)
  4. Claude (the owner's subscription; free models if it is not set up) picks the week from the
     unused topic bank, the new models and tool repos, guided by 1-3
  5. every pick is checked (not on the channel, not a repeat by words or meaning, real source);
     a rejected or missing day is filled from the topic bank

Writes data/week_plan.json, data/content_db.json and data/topic_index.npz. Read-only on YouTube.
A big model release on the day still takes the explainer slot (agents/research_agent.py).
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import content_db, topic_index  # noqa: E402
from agents.kids_topic_agent import KidsTopicAgent, norm, too_close  # noqa: E402
from agents.published import explainer_published  # noqa: E402
from agents.research_agent import ResearchAgent, bank_topic  # noqa: E402
from config import config  # noqa: E402

logger = logging.getLogger("plan_week")

KIND_OF = {"tool": "tool", "concept": "concept", "trend": "trend"}


# ── candidates ────────────────────────────────────────────────────────────────

def explainer_bank(history: List[Dict], titles: List[str]) -> List[Dict]:
    """Unused topic-bank entries (not in history, not on the channel), in bank order."""
    try:
        bank = json.loads(Path(config.EXPLAINER_TOPICS_FILE).read_text()).get("topics", [])
    except (OSError, json.JSONDecodeError):
        return []
    used = {h.get("normalized_topic") or ResearchAgent._normalize(h["topic"]) for h in history}
    out = []
    for i, b in enumerate(bank):
        if ResearchAgent._normalize(b["topic"]) in used or explainer_published(b["topic"], titles):
            continue
        out.append({"ref": f"bank:{i}", "topic": b["topic"], "kind": b.get("kind", "tool"), "entry": b})
    return out


def hf_models(history: List[Dict]) -> List[Dict]:
    from agents.trend_agent import HF_TRENDING, age_days, rank
    try:
        r = requests.get(HF_TRENDING, timeout=20, headers={"User-Agent": "AutoTube/1.0"})
        r.raise_for_status()
        ranked = rank(r.json(), history)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Hugging Face trending unavailable: {str(e)[:120]}")
        return []
    return [{"ref": f"hf:{m['id']}", "model": m, "likes": m.get("likes"), "days": round(age_days(m))} for m in ranked[:8]]


def areas_for(n: int, kids_history: List[Dict]) -> List[str]:
    cycle = [a.strip() for a in config.KIDS_AREA_CYCLE.split(",") if a.strip()] or ["tech", "finance"]
    return [cycle[(len(kids_history) + i) % len(cycle)] for i in range(n)]


# ── checks ────────────────────────────────────────────────────────────────────

class Checker:
    """Is a topic new? Words (history, channel) and meaning (topic index) against everything so far."""

    def __init__(self, explainer_history, explainer_subjects, titles, kids_history, kids_subjects):
        self.ex_used = {h.get("normalized_topic") or ResearchAgent._normalize(h["topic"]) for h in explainer_history}
        self.ex_past = list(dict.fromkeys([h["topic"] for h in explainer_history] + explainer_subjects))
        self.titles = titles
        self.history = explainer_history
        self.kids_used = {norm(h["topic"]) for h in kids_history} | {norm(q) for q in kids_subjects}
        self.kids_past = list(dict.fromkeys([h["topic"] for h in kids_history] + kids_subjects))

    def explainer_ok(self, t: Dict) -> Optional[str]:
        topic = t["topic"]
        if ResearchAgent._normalize(topic) in self.ex_used:
            return "already in the history"
        if explainer_published(topic, self.titles):
            return "already on the channel"
        if t.get("model_id"):
            from agents.trend_agent import covered
            if covered(t["model_id"], self.history):
                return "model already covered"
        dup = topic_index.duplicate_of(topic, self.ex_past, config.EXPLAINER_DUP_SIMILARITY)
        if dup:
            return f"same as '{dup[1][:60]}' ({dup[0]:.2f})"
        return None

    def kids_ok(self, q: str) -> Optional[str]:
        if norm(q) in self.kids_used:
            return "already made"
        if too_close(q, self.kids_past):
            return "too close by words"
        dup = topic_index.duplicate_of(q, self.kids_past)
        if dup:
            return f"same as '{dup[1][:60]}' ({dup[0]:.2f})"
        return None

    def take_explainer(self, t: Dict) -> None:
        self.ex_used.add(ResearchAgent._normalize(t["topic"]))
        self.ex_past.append(t["topic"])
        if t.get("model_id"):
            self.history = self.history + [{"topic": t["topic"], "source": "trend"}]

    def take_kids(self, q: str) -> None:
        self.kids_used.add(norm(q))
        self.kids_past.append(q)


# ── the plan ──────────────────────────────────────────────────────────────────

PROMPT = """You plan a week of uploads for the YouTube channel "{channel}": free and open-source AI you can
run yourself. Two uploads a day, each with its own Short:
- EXPLAINER (about 5 minutes): set up one open-source tool ("tool"), how an AI idea works ("concept"),
  or a model released days ago ("trend": what it is, can you run it at home).
- KIDS "Explained Like You're 5" (2-3 minutes): one question about AI, tech or money, told with a
  simple story. All ages, not made for kids. No real brands, companies, people or coins, no advice,
  nothing scary.

WHAT THE CHANNEL'S OWN NUMBERS SAY
{performance}

WHAT IS GETTING VIEWS ON YOUTUBE THIS WEEK (niche searches, last 7 days, most viewed first)
{youtube}

NEW OPEN MODELS TRENDING ON HUGGING FACE (ref | likes | days old)
{models}

UNUSED EXPLAINER TOPICS FROM THE BANK (ref | kind | topic)
{bank}

HEADLINES PEOPLE ARE READING NOW (for kids questions from the news)
{headlines}

KIDS QUESTIONS ALREADY ON THE CHANNEL (never repeat these or ask the same thing in other words)
{kids_done}

DAYS AND THE KIDS AREA FOR EACH: {days}

RULES
Explainer: pick each day's topic by ref: "bank:N", "hf:<model id>" from the lists above, or
"repo:<owner>/<name>" for an open-source tool on GitHub that this week's YouTube list shows people
want and the bank lacks (only repos you are sure exist; give the topic in the bank's style,
"<Tool>: <what you can do with it>"). At most 3 "hf" days, never two in a row. Alternate tool and
concept topics on the other days. Prefer topics close to what is getting views this week and to
the channel's own best videos.
Kids: one question per day in that day's area, under 60 characters, that a curious adult or child
would really ask, about something in the news right now (see the headlines) on most days, with a surprising angle (like
"Why does gasoline cost so much?" or "How do AI safety rules keep robots safe?" — the channel's
best). hint is one sentence: the simple story or comparison that makes it click.
"why" is one short sentence for the owner.

Return ONLY this JSON:
{{"days": [{{"date": "YYYY-MM-DD", "explainer": {{"ref": "...", "topic": "...", "why": "..."}},
            "kids": {{"question": "...", "area": "...", "hint": "...", "why": "..."}}}}]}}"""


def ask_llm(prompt: str) -> (str, str):
    from agents import claude_writer
    if claude_writer.available():
        return claude_writer.ask(prompt, timeout=900), f"claude ({config.CLAUDE_SCRIPT_MODEL})"
    from agents.llm import FreeLLM
    llm = FreeLLM()
    return llm.complete("You plan YouTube uploads. Reply with JSON only.", prompt, max_tokens=6000), llm.last_model or "free model"


def parse_json(text: str) -> Dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0)) if m else {}


def repo_topic(repo: str, topic: str) -> Optional[Dict]:
    """A GitHub repo pick, only if the repo exists and has a README."""
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo or ""):
        return None
    headers = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.getenv('GITHUB_TOKEN')}"
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=20)
        if r.status_code != 200 or r.json().get("archived"):
            return None
        branch = r.json().get("default_branch", "main")
        readme = requests.get(f"https://raw.githubusercontent.com/{repo}/{branch}/README.md", timeout=20)
        if readme.status_code != 200 or len(readme.text) < 500:
            return None
    except requests.RequestException:
        return None
    return bank_topic({"topic": topic, "repo": repo, "branch": branch}, source="bank")


def resolve(pick: Dict, bank: Dict[str, Dict], models: Dict[str, Dict]) -> Optional[Dict]:
    ref = str(pick.get("ref", "")).strip()
    if ref in bank:
        return bank_topic(bank[ref]["entry"])
    if ref in models:
        from agents.trend_agent import to_topic
        t = to_topic(models[ref]["model"])
        t["model_id"] = models[ref]["model"]["id"]
        return t
    if ref.startswith("repo:") and pick.get("topic"):
        return repo_topic(ref[5:], str(pick["topic"]).strip())
    return None


def build_plan(dates: List[str], raw: Dict, ctx: Dict) -> List[Dict]:
    """Checked days: Claude's picks where they pass, the topic bank where they do not."""
    check: Checker = ctx["checker"]
    by_date = {d.get("date"): d for d in raw.get("days", []) if isinstance(d, dict)}
    bank = {b["ref"]: b for b in ctx["bank"]}
    models = {m["ref"]: m for m in ctx["models"]}
    spare_bank = list(ctx["bank"])
    kids_bank = ctx["kids_bank"]
    days, last_kind = [], None
    for d, area in zip(dates, ctx["areas"]):
        want = by_date.get(d, {})
        # explainer
        ex, note = None, ""
        pick = want.get("explainer") or {}
        if pick:
            ex = resolve(pick, bank, models)
            why = check.explainer_ok(ex) if ex else "unknown ref or repo"
            if why:
                note = f"Claude's pick {pick.get('ref')} rejected: {why}"
                ex = None
        if ex is None:
            for b in sorted(spare_bank, key=lambda b: b["kind"] == last_kind):
                t = bank_topic(b["entry"])
                if not check.explainer_ok(t):
                    ex = t
                    break
        if ex:
            spare_bank = [b for b in spare_bank if b["topic"] != ex["topic"]]
            check.take_explainer(ex)
            ex.update({"planned": True, "why": pick.get("why", "") if not note else note})
            last_kind = ex.get("kind")
        # kids
        kid, knote = None, ""
        kp = want.get("kids") or {}
        q = str(kp.get("question", "")).strip()
        if q:
            why = check.kids_ok(q)
            if why:
                knote = f"Claude's question '{q}' rejected: {why}"
            else:
                kid = {"topic": q, "area": area, "source": "plan", "hint": str(kp.get("hint", "")).strip(),
                       "why": str(kp.get("why", "")).strip()}
        if kid is None:
            for b in sorted(kids_bank, key=lambda b: b.get("area") != area):
                if not check.kids_ok(b["question"]):
                    kid = {"topic": b["question"], "area": b.get("area", area), "source": "bank",
                           "hint": b.get("hint", ""), "why": knote or "from the kids topic bank"}
                    break
        if kid:
            kids_bank = [b for b in kids_bank if b["question"] != kid["topic"]]
            check.take_kids(kid["topic"])
        days.append({"date": d, "explainer": ex, "kids": kid})
    return days


def start_date(text: str, today: Optional[date] = None) -> date:
    today = today or datetime.now(timezone.utc).date()
    if text == "tomorrow":
        return today + timedelta(days=1)
    if text == "next-monday":
        return today + timedelta(days=(7 - today.weekday()) or 7)
    return date.fromisoformat(text)


def markdown(plan: Dict) -> str:
    rows = ["| Day | Explainer | Kids |", "|---|---|---|"]
    for d in plan["days"]:
        ex, k = d.get("explainer") or {}, d.get("kids") or {}
        rows.append(f"| {d['date']} | {ex.get('topic', '—')} ({ex.get('kind', '')}, {ex.get('source', '')}) | "
                    f"{k.get('topic', '—')} ({k.get('area', '')}) |")
    return f"### Week plan from {plan['start']} (written by {plan['writer']})\n\n" + "\n".join(rows) + "\n"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="tomorrow", help="YYYY-MM-DD, 'tomorrow' or 'next-monday'")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--no-llm", action="store_true", help="fill the week from the topic banks only")
    a = ap.parse_args()
    start = start_date(a.start)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(a.days)]

    # 1. content database
    videos, yt = [], None
    if os.getenv("YOUTUBE_TOKEN_JSON"):
        try:
            from agents.upload_agent import UploadAgent
            from scripts.link_comments import channel_uploads
            yt = UploadAgent().youtube
            _, videos = channel_uploads(yt, limit=500)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not list the channel: {str(e)[:150]}")
    db = content_db.build(videos, content_db.load_report()) if videos else content_db.load()
    logger.info(f"Content database: {len(db.get('videos', []))} videos")
    titles = [v["title"] for v in db.get("videos", [])]
    ex_subjects, kids_subjects = content_db.subjects(db, "explainer"), content_db.subjects(db, "kids")

    explainer_history = ResearchAgent.__new__(ResearchAgent)._load_history()
    kids_agent = KidsTopicAgent()
    kids_history = kids_agent.history()

    # 2. topic index
    size = topic_index.save(ex_subjects + kids_subjects + [h["topic"] for h in explainer_history + kids_history]) \
        if not a.dry_run else 0
    logger.info(f"Topic index: {size or 'not saved'} entries ({'on' if topic_index.enabled() else 'off'})")

    # 3. trends
    from agents import youtube_trends
    yt_videos = youtube_trends.scan(yt) if yt else []
    models = hf_models(explainer_history)
    bank = explainer_bank(explainer_history, titles)
    areas = areas_for(len(dates), kids_history)
    kids_bank = kids_agent.bank()
    try:
        heads = kids_agent.headlines()
    except Exception:  # noqa: BLE001
        heads = []
    check = Checker(explainer_history, ex_subjects, titles, kids_history, kids_subjects)

    # 4. picks
    raw, writer = {}, "topic banks"
    if not a.no_llm:
        prompt = PROMPT.format(
            channel=config.CHANNEL_NAME,
            performance=content_db.summary(db) if db.get("videos") else "(no numbers yet)",
            youtube=youtube_trends.as_text(yt_videos) or "(not available)",
            models="\n".join(f"  {m['ref']} | {m['likes']} | {m['days']}" for m in models) or "  (none new)",
            bank="\n".join(f"  {b['ref']} | {b['kind']} | {b['topic']}" for b in bank[:40]),
            headlines="\n".join(f"  {h}" for h in heads[:30]) or "  (not available)",
            kids_done="\n".join(f"  {q}" for q in check.kids_past[-150:]),
            days=", ".join(f"{d} {ar}" for d, ar in zip(dates, areas)))
        try:
            text, writer = ask_llm(prompt)
            raw = parse_json(text)
        except Exception as e:  # noqa: BLE001 — the banks still fill the week
            logger.warning(f"Planner LLM failed ({str(e)[:200]}) — filling from the topic banks")
            writer = "topic banks"

    # 5. checks + fill
    days = build_plan(dates, raw, {"checker": check, "bank": bank, "models": models, "areas": areas,
                                   "kids_bank": kids_bank})
    plan = {"made": datetime.now(timezone.utc).isoformat(timespec="minutes"), "start": dates[0],
            "writer": writer, "youtube_trends": [{k: v[k] for k in ("title", "views", "channel")} for v in yt_videos[:15]],
            "days": days}
    print(markdown(plan))
    for d in days:
        for tr in ("explainer", "kids"):
            if (d.get(tr) or {}).get("why", "").startswith("Claude's"):
                print(f"  {d['date']} {tr}: {d[tr]['why']}")
    if a.dry_run:
        return 0
    Path(config.WEEK_PLAN_FILE).write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n")
    if videos:
        content_db.save(db)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(markdown(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
