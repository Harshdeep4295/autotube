"""
Post a kids Short (the vertical cut) as an Instagram Reel and a Facebook Page video.
Runs as a step of the kids workflow after the YouTube upload; free Meta Graph API.

    python scripts/post_reels.py                 # newest outputs/*/short.mp4
    python scripts/post_reels.py --dir outputs/20261005_kids_ab12cd --dry-run

Environment: META_ACCESS_TOKEN (long-lived user token, ~60 days), INSTAGRAM_ACCOUNT_ID,
FACEBOOK_PAGE_ID. A missing value skips that platform. One platform failing does not stop
the other; the exit code is 1 if anything that was attempted failed.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402

GRAPH = "https://graph.facebook.com"
HASHTAGS = "#explainedlikeyoure5 #eli5 #learnontiktok #financeforbeginners #techexplained #reels"


def caption_for(script: Dict, full_url: str = "") -> str:
    base = script.get("title", "").split(" (")[0].strip()
    parts = [f"{base} — explained like you're 5.", script.get("description", "").strip()]
    if full_url:
        parts.append(f"Full video on YouTube ({config.CHANNEL_NAME}): {full_url}")
    parts.append("Narration voice is AI-generated. Animation is made with code. Not financial advice.")
    parts.append(HASHTAGS)
    return "\n\n".join(p for p in parts if p)[:2100]


def _check(r: requests.Response) -> Dict:
    try:
        data = r.json()
    except ValueError:
        data = {"error": {"message": r.text[:300]}}
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"{r.status_code}: {json.dumps(data.get('error', data))[:400]}")
    return data


def post_instagram(video: Path, caption: str, ig_id: str, token: str, wait: int = 600) -> str:
    """Resumable upload → wait until processed → publish. Returns the media id."""
    c = _check(requests.post(f"{GRAPH}/{ig_id}/media", timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption, "access_token": token}))
    size = video.stat().st_size
    with open(video, "rb") as f:
        _check(requests.post(c["uri"], data=f, timeout=600, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}))
    deadline = time.time() + wait
    while True:
        s = _check(requests.get(f"{GRAPH}/{c['id']}", timeout=60,
                                params={"fields": "status_code,status", "access_token": token}))
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED") or time.time() > deadline:
            raise RuntimeError(f"container not ready: {s}")
        time.sleep(10)
    done = _check(requests.post(f"{GRAPH}/{ig_id}/media_publish", timeout=60,
                                data={"creation_id": c["id"], "access_token": token}))
    return done["id"]


def post_facebook(video: Path, title: str, caption: str, page_id: str, token: str) -> str:
    """Upload as a Page video with the Page's own token. Returns the video id."""
    page_token = _check(requests.get(f"{GRAPH}/{page_id}", timeout=60,
                                     params={"fields": "access_token", "access_token": token}))["access_token"]
    with open(video, "rb") as f:
        done = _check(requests.post(f"https://graph-video.facebook.com/{page_id}/videos", timeout=900,
                                    data={"title": title[:250], "description": caption, "access_token": page_token},
                                    files={"source": (video.name, f, "video/mp4")}))
    return done["id"]


def newest_short(root: Path) -> Optional[Path]:
    shorts = sorted(root.glob("*/short.mp4"), key=lambda p: p.stat().st_mtime)
    return shorts[-1].parent if shorts else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="", help="job folder with short.mp4 + script.json (default: newest)")
    ap.add_argument("--dry-run", action="store_true", help="print the caption, post nothing")
    a = ap.parse_args()

    job = Path(a.dir) if a.dir else newest_short(Path(config.OUTPUT_DIR))
    if not job or not (job / "short.mp4").exists():
        print("No short.mp4 found — nothing to post")
        return
    script = json.loads((job / "script.json").read_text())
    try:
        full_url = json.loads((job / "result.json").read_text()).get("url", "")
    except (OSError, json.JSONDecodeError):
        full_url = ""
    full_url = full_url if full_url.startswith("http") else ""
    caption = caption_for(script, full_url)
    title = script.get("title", "").split(" (")[0].strip()
    print(f"Short: {job / 'short.mp4'}\n--- caption ---\n{caption}\n---")
    if a.dry_run:
        return
    if not full_url:
        print("This job was not uploaded to YouTube (dry run) — not posting")
        return

    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    ig_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    if not token:
        print("META_ACCESS_TOKEN not set — skipping Instagram and Facebook")
        return
    failed = False
    for name, target, post in (
        ("Instagram", ig_id, lambda: post_instagram(job / "short.mp4", caption, ig_id, token)),
        ("Facebook", page_id, lambda: post_facebook(job / "short.mp4", title, caption, page_id, token)),
    ):
        if not target:
            print(f"{name}: no account id set — skipped")
            continue
        try:
            print(f"{name}: posted, id {post()}")
        except Exception as e:  # noqa: BLE001 — the other platform still gets its turn
            failed = True
            print(f"{name}: FAILED — {e}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
