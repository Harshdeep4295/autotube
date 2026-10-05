"""
Give an already-published kids video what newer ones get automatically: a Short (the vertical
cut) and the current description (links to other videos + subscribe link). Run through the
"Kids Backfill" workflow, which has the YouTube token and fetches the video's script.json.

    python scripts/backfill_kids.py --video TdWMrNFhfig --script prev/script.json --publish-at 16:30
    python scripts/backfill_kids.py --video TdWMrNFhfig --script prev/script.json --dry-run

--dry-run renders the Short and prints the new description; it never talks to YouTube.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.kids_agent import KidsAgent, description_for, short_meta  # noqa: E402
from config import config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="ID of the published full video")
    ap.add_argument("--script", required=True, help="script.json of that video (from the run's artifact)")
    ap.add_argument("--publish-at", default="", help="HH:MM UTC for the Short; empty = stays private")
    ap.add_argument("--no-short", action="store_true")
    ap.add_argument("--no-description", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    script = json.loads(Path(a.script).read_text())
    url = f"https://youtube.com/watch?v={a.video}"
    description = description_for(script, skip_url=url)
    agent = None
    title, tags = script.get("title", ""), script.get("tags", [])

    if not a.dry_run:
        from agents.upload_agent import UploadAgent

        agent = UploadAgent()
        items = agent.youtube.videos().list(part="snippet", id=a.video).execute().get("items", [])
        if not items:
            sys.exit(f"Video {a.video} not found on the channel")
        snippet = items[0]["snippet"]
        title, tags = snippet["title"], snippet.get("tags", tags)
        if "(Explained Like You're 5)" not in title:
            sys.exit(f"'{title}' is not a kids video — refusing to touch it")

    if not a.no_description:
        if a.dry_run:
            print(f"--- new description for {a.video} ---\n{description}\n---")
        else:
            body = {"id": a.video, "snippet": {"title": title, "description": description, "tags": tags,
                                               "categoryId": snippet["categoryId"]}}
            agent.youtube.videos().update(part="snippet", body=body).execute()
            print(f"Updated the description of {a.video} ({title})")

    if not a.no_short:
        out = Path(config.OUTPUT_DIR) / f"backfill_{a.video}"
        rendered = KidsAgent().render(script, str(out), enforce_length=False)
        short_path = rendered.get("short_path")
        if not short_path:
            sys.exit("No Short was produced (too long, or it failed QA) — see the log above")
        print(f"Short rendered: {short_path}")
        if not a.dry_run:
            from orchestrator import next_utc_time

            publish_at = next_utc_time(a.publish_at) if a.publish_at else None
            up = agent.publish(short_path, None, short_meta({"title": title, "description": description, "tags": tags}, url),
                               publish_at=publish_at)
            if up.get("success") is False:
                sys.exit(f"Short upload failed: {up.get('error', '')}")
            print(f"Short uploaded: {up.get('url', '')} ({'public at ' + publish_at if publish_at else 'private'})")


if __name__ == "__main__":
    main()
