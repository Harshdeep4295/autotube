"""
The week's plan (data/week_plan.json, written by scripts/plan_week.py): one explainer topic and
one kids question per day. The daily runs ask for today's entry; no plan, an old plan or no entry
for today means the usual pickers decide.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from config import config

logger = logging.getLogger(__name__)
REPO = Path(__file__).resolve().parent.parent


def load() -> Dict:
    try:
        return json.loads((REPO / config.WEEK_PLAN_FILE).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def for_today(track: str, today: Optional[str] = None) -> Optional[Dict]:
    """Today's planned topic for 'explainer' or 'kids' (UTC date), or None."""
    if not config.WEEK_PLAN:
        return None
    today = today or datetime.now(timezone.utc).date().isoformat()
    for day in load().get("days", []):
        if day.get("date") == today and day.get(track):
            return dict(day[track])
    return None
