"""
One record per video on the channel, so planning starts from what exists and what worked:
track, subject, title, privacy, and its numbers from the daily Channel Report (views, average
seconds watched, share watched, subscribers). Saved to data/content_db.json by the weekly planner.

    from agents.content_db import build, summary
    db = build(videos, report)          # videos: scripts.link_comments.channel_uploads(...)[1]
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

from agents.published import KIDS_SUFFIX
from config import config

logger = logging.getLogger(__name__)

REPORT_URL = "https://raw.githubusercontent.com/{repo}/report-data/report.json"


def subject(title: str) -> str:
    """The idea a title is about: kids question without the suffix, explainer title without #Shorts."""
    t = KIDS_SUFFIX.sub("", title)
    return re.sub(r"\s*#shorts\b", "", t, flags=re.I).strip()


def track(title: str) -> str:
    return "kids" if "explained like you" in title.lower() else "explainer"


def load_report() -> Optional[Dict]:
    """The newest Channel Report (public branch report-data), or None."""
    repo = os.getenv("GITHUB_REPOSITORY", "Harshdeep4295/autotube")
    try:
        r = requests.get(REPORT_URL.format(repo=repo), timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001 — the plan works without numbers, just less well
        logger.warning(f"[content-db] channel report unavailable: {str(e)[:120]}")
        return None


def build(videos: List[Dict], report: Optional[Dict] = None) -> Dict:
    stats = {v["id"]: v for v in ((report or {}).get("youtube") or {}).get("videos", [])}
    items = []
    for v in videos:
        s = stats.get(v["id"], {})
        title = v.get("title", "")
        items.append({
            "id": v["id"], "title": title, "subject": subject(title), "track": track(title),
            "short": "#shorts" in title.lower(), "privacy": v.get("privacy", ""),
            "views": s.get("views", 0), "avg_seconds": s.get("avg_seconds"), "pct": s.get("pct"),
            "subs": s.get("subs", 0),
        })
    return {"built": datetime.now(timezone.utc).isoformat(timespec="minutes"),
            "data_through": ((report or {}).get("youtube") or {}).get("data_through"), "videos": items}


def save(db: Dict, path: Optional[str] = None) -> None:
    Path(path or config.CONTENT_DB_FILE).write_text(json.dumps(db, indent=1, ensure_ascii=False) + "\n")


def load(path: Optional[str] = None) -> Dict:
    try:
        return json.loads(Path(path or config.CONTENT_DB_FILE).read_text())
    except (OSError, json.JSONDecodeError):
        return {"videos": []}


def subjects(db: Dict, which: str) -> List[str]:
    """Distinct subjects of one track ('kids' or 'explainer')."""
    return list(dict.fromkeys(v["subject"] for v in db.get("videos", []) if v["track"] == which and v["subject"]))


def summary(db: Dict, n: int = 8) -> str:
    """What worked and what did not, per track and format, for the planning prompt."""
    lines = [f"Numbers up to {db.get('data_through') or 'unknown'} (views, average seconds watched, share watched):"]
    vids = db.get("videos", [])
    for tr in ("explainer", "kids"):
        for short in (False, True):
            group = [v for v in vids if v["track"] == tr and v["short"] == short]
            if not group:
                continue
            group.sort(key=lambda v: -(v["views"] or 0))
            name = f"{tr} {'Shorts' if short else 'full videos'}"
            lines.append(f"\n{name}: {len(group)} on the channel. Best:")
            lines += [f"  {v['views']} views, {v['avg_seconds']}s, {v['pct']}% - {v['subject']}" for v in group[:n]]
            low = [v for v in group[n:] if v["avg_seconds"] is not None][-4:]
            if low:
                lines.append("  Weakest:")
                lines += [f"  {v['views']} views, {v['avg_seconds']}s, {v['pct']}% - {v['subject']}" for v in low]
    return "\n".join(lines)
