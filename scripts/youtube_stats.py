"""
Read-only YouTube Analytics for the channel, printed as plain text: per-video views, watch
time and how much of each video people watch, plus where the views come from. Run through
the "YouTube Stats" workflow (it has the token; the token needs the yt-analytics.readonly scope).

    python scripts/youtube_stats.py --days 14

Analytics data is usually two to three days behind.
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.discovery import build  # noqa: E402

from agents.upload_agent import UploadAgent  # noqa: E402


def query(ya, start: str, end: str, metrics: str, dimensions: str, sort: str = "-views", limit: int = 50):
    try:
        r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, metrics=metrics,
                               dimensions=dimensions, sort=sort, maxResults=limit).execute()
        return [h["name"] for h in r.get("columnHeaders", [])], r.get("rows", [])
    except Exception as e:  # noqa: BLE001 — one refused report must not hide the others
        print(f"  (report '{dimensions}' not available: {str(e)[-260:]})")
        return [], []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()
    yt = UploadAgent().youtube
    ya = build("youtubeAnalytics", "v2", credentials=yt._http.credentials)
    end, start = date.today().isoformat(), (date.today() - timedelta(days=a.days)).isoformat()
    print(f"YouTube Analytics {start} to {end}")

    print("\n== Per video ==")
    _, rows = query(ya, start, end, "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
                                    "subscribersGained,likes,shares", "video")
    titles = {}
    ids = [r[0] for r in rows]
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,contentDetails", id=",".join(ids[i:i + 50])).execute().get("items", []):
            titles[v["id"]] = v["snippet"]["title"]
    for vid, views, minutes, avg_s, avg_pct, subs, likes, shares in rows:
        print(f"- views {views:>4}  watched {minutes:>4} min  avg {avg_s:>4}s = {avg_pct:5.1f}%  subs +{subs}  "
              f"likes {likes}  shares {shares}  {titles.get(vid, vid)[:60]}")

    for label, dims in (("Where views come from", "insightTrafficSourceType"), ("By content type", "creatorContentType"),
                        ("By country", "country"), ("By day", "day")):
        print(f"\n== {label} ==")
        names, rows = query(ya, start, end, "views,estimatedMinutesWatched,averageViewPercentage", dims,
                            sort="day" if dims == "day" else "-views", limit=25)
        for r in rows:
            print(f"- {str(r[0]):<24} views {r[1]:>4}  watched {r[2]:>4} min  avg watched {r[3]:5.1f}%")


if __name__ == "__main__":
    main()
