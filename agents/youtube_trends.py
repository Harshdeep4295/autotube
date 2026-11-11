"""
What is getting views on YouTube in the niche this week: for each search in YT_TREND_QUERIES, the
most-viewed videos published in the last `days` days (YouTube Data API, the channel's own sign-in,
about 100 quota units per search). Read-only. Used by the weekly planner.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from config import config

logger = logging.getLogger(__name__)


def scan(yt, days: int = 7, per_query: int = 10) -> List[Dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found: Dict[str, Dict] = {}
    for q in [q.strip() for q in config.YT_TREND_QUERIES.split(",") if q.strip()]:
        try:
            res = yt.search().list(part="snippet", q=q, type="video", order="viewCount", publishedAfter=since,
                                   relevanceLanguage="en", maxResults=per_query).execute()
        except Exception as e:  # noqa: BLE001 — one refused search must not lose the others
            logger.warning(f"[yt-trends] search '{q}' failed: {str(e)[:150]}")
            continue
        for it in res.get("items", []):
            vid = it.get("id", {}).get("videoId")
            if vid and vid not in found:
                sn = it["snippet"]
                found[vid] = {"id": vid, "title": sn.get("title", ""), "channel": sn.get("channelTitle", ""),
                              "published": sn.get("publishedAt", "")[:10], "query": q, "views": 0}
    ids = list(found)
    for i in range(0, len(ids), 50):
        try:
            res = yt.videos().list(part="statistics,contentDetails", id=",".join(ids[i:i + 50])).execute()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[yt-trends] statistics failed: {str(e)[:150]}")
            break
        for v in res.get("items", []):
            found[v["id"]]["views"] = int(v.get("statistics", {}).get("viewCount", 0) or 0)
            found[v["id"]]["duration"] = v.get("contentDetails", {}).get("duration", "")
    out = sorted(found.values(), key=lambda v: -v["views"])
    logger.info(f"[yt-trends] {len(out)} videos from {len(config.YT_TREND_QUERIES.split(','))} searches")
    return out


def as_text(videos: List[Dict], n: int = 40) -> str:
    import html
    return "\n".join(f"  {v['views']:>8,} views | {html.unescape(v['title'])[:100]} ({v['channel']}, {v['published']})"
                     for v in videos[:n])
