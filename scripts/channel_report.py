"""
One JSON snapshot of the channel for the report page: YouTube Analytics totals, days, videos,
traffic sources and search terms, plus Instagram and Facebook counts. Read-only. Run by the
"Channel Report" workflow, which publishes the file as a release asset.

    python scripts/channel_report.py --days 90 --out report.json

Analytics data is usually two to three days behind; "data_through" says how far it reaches.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.discovery import build  # noqa: E402

from agents.upload_agent import UploadAgent  # noqa: E402
from scripts.social_stats import get  # noqa: E402
from scripts.post_reels import page_token_for  # noqa: E402


def rows(ya, start: str, end: str, metrics: str, **kw) -> List[List]:
    try:
        return ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, metrics=metrics, **kw).execute().get("rows", [])
    except Exception as e:  # noqa: BLE001 — one refused report must not lose the others
        print(f"(report {kw.get('dimensions', 'totals')} not available: {str(e)[-200:]})", file=sys.stderr)
        return []


def youtube(days: int) -> Dict:
    yt = UploadAgent().youtube
    ya = build("youtubeAnalytics", "v2", credentials=yt._http.credentials)
    end, start = date.today().isoformat(), (date.today() - timedelta(days=days)).isoformat()
    tot = (rows(ya, start, end, "views,estimatedMinutesWatched,subscribersGained,subscribersLost,likes,comments,shares") or [[0] * 7])[0]
    by_day = rows(ya, start, end, "views,estimatedMinutesWatched", dimensions="day", sort="day", maxResults=200)
    vids = rows(ya, start, end, "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes",
                dimensions="video", sort="-views", maxResults=50)
    titles = {}
    ids = [r[0] for r in vids]
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute().get("items", []):
            titles[v["id"]] = v["snippet"]["title"]
    pair = lambda dim, n=25, **kw: [  # noqa: E731
        {"name": str(r[0]), "views": r[1], "minutes": r[2], "pct": round(r[3], 1) if len(r) > 3 else None}
        for r in rows(ya, start, end, kw.pop("metrics", "views,estimatedMinutesWatched,averageViewPercentage"),
                      dimensions=dim, sort="-views", maxResults=n, **kw)]
    return {
        "start": start, "data_through": by_day[-1][0] if by_day else None,
        "totals": dict(zip(("views", "minutes", "subs_gained", "subs_lost", "likes", "comments", "shares"), tot)),
        "days": [{"day": d, "views": v, "minutes": m} for d, v, m in by_day],
        "videos": [{"id": r[0], "title": titles.get(r[0], r[0]), "short": "#shorts" in titles.get(r[0], "").lower(),
                    "views": r[1], "minutes": r[2], "avg_seconds": r[3], "pct": round(r[4], 1), "subs": r[5], "likes": r[6]}
                   for r in vids],
        "sources": pair("insightTrafficSourceType"),
        "types": pair("creatorContentType"),
        "search": pair("insightTrafficSourceDetail", metrics="views,estimatedMinutesWatched",
                       filters="insightTrafficSourceType==YT_SEARCH"),
    }


def social() -> Dict:
    out: Dict = {}
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    ig, page = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip(), os.getenv("FACEBOOK_PAGE_ID", "").strip()
    if token and ig:
        acct = get(ig, token, fields="username,followers_count,media_count") or {}
        media = (get(f"{ig}/media", token, limit=50, fields="like_count,comments_count") or {}).get("data", [])
        out["instagram"] = {"username": acct.get("username"), "followers": acct.get("followers_count"),
                            "posts": acct.get("media_count"), "likes": sum(m.get("like_count") or 0 for m in media),
                            "comments": sum(m.get("comments_count") or 0 for m in media)}
    if token and page:
        pt = page_token_for(page, token)
        p = get(page, pt, fields="name,followers_count,fan_count") or {}
        vids = (get(f"{page}/videos", pt, limit=50, fields="views") or {}).get("data", [])
        out["facebook"] = {"name": p.get("name"), "followers": p.get("followers_count"), "posts": len(vids),
                           "views": sum(v.get("views") or 0 for v in vids)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--out", default="report.json")
    a = ap.parse_args()
    report = {"generated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "youtube": youtube(a.days)}
    try:
        report.update(social())
    except Exception as e:  # noqa: BLE001 — the YouTube part is still worth publishing
        print(f"(social numbers not available: {str(e)[:200]})", file=sys.stderr)
    Path(a.out).write_text(json.dumps(report, indent=1))
    t = report["youtube"]["totals"]
    print(f"{a.out}: {t['views']} views, {t['minutes']} min, data through {report['youtube']['data_through']}")


if __name__ == "__main__":
    main()
