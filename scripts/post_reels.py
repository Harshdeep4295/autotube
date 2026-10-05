"""
Post a kids Short (the vertical cut) as an Instagram Reel and a Facebook Page video.
Runs as a step of the kids workflow after the YouTube upload; free Meta Graph API.

    python scripts/post_reels.py                 # newest outputs/*/short.mp4
    python scripts/post_reels.py --dir outputs/20261005_kids_ab12cd --dry-run

Environment: META_ACCESS_TOKEN (long-lived user token, ~60 days), INSTAGRAM_ACCOUNT_ID,
FACEBOOK_PAGE_ID. A missing value skips that platform. Facebook goes first: if Instagram refuses
the direct file upload, the Facebook copy's public URL is used instead. One platform failing does
not stop the other; the exit code is 1 if anything that was attempted failed.
"""

import argparse
import json
import os
import subprocess
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


def _publish_container(cid: str, ig_id: str, token: str, wait: int) -> str:
    deadline = time.time() + wait
    while True:
        s = _check(requests.get(f"{GRAPH}/{cid}", timeout=60,
                                params={"fields": "status_code,status", "access_token": token}))
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED") or time.time() > deadline:
            raise RuntimeError(f"container not ready: {s}")
        time.sleep(10)
    return _check(requests.post(f"{GRAPH}/{ig_id}/media_publish", timeout=60,
                                data={"creation_id": cid, "access_token": token}))["id"]


def instagram_copy(video: Path) -> Path:
    """Same picture with stereo 48 kHz AAC sound (the Short's sound is mono). Falls back to the original."""
    out = video.with_name("short_instagram.mp4")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-c:v", "copy", "-c:a", "aac",
                        "-ac", "2", "-ar", "48000", "-b:a", "128k", "-movflags", "+faststart", str(out)],
                       check=True, timeout=300)
        return out
    except Exception as e:  # noqa: BLE001
        print(f"Instagram: could not make the stereo copy ({e}) — using the original file")
        return video


def post_instagram(video: Path, caption: str, ig_id: str, token: str, video_url: str = "", wait: int = 600) -> str:
    """Reel from a direct file upload; if Meta rejects that and a public `video_url` is known,
    from that URL instead. Returns the media id."""
    base = {"media_type": "REELS", "caption": caption, "access_token": token}
    video = instagram_copy(video)
    try:
        c = _check(requests.post(f"{GRAPH}/{ig_id}/media", timeout=60, data={**base, "upload_type": "resumable"}))
        up = requests.post(c["uri"], data=video.read_bytes(), timeout=600, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(video.stat().st_size),
            "Content-Type": "application/octet-stream"})
        try:
            _check(up)
        except RuntimeError as e:
            why = requests.get(f"{GRAPH}/{c['id']}", timeout=60,
                               params={"fields": "status_code,status", "access_token": token}).text[:300]
            raise RuntimeError(f"{e} | container: {why}")
        return _publish_container(c["id"], ig_id, token, wait)
    except RuntimeError as e:
        if not video_url:
            raise
        print(f"Instagram: direct upload failed ({e}) — trying the public video URL")
    c = _check(requests.post(f"{GRAPH}/{ig_id}/media", timeout=60, data={**base, "video_url": video_url}))
    return _publish_container(c["id"], ig_id, token, wait)


def page_token_for(page_id: str, token: str) -> str:
    return _check(requests.get(f"{GRAPH}/{page_id}", timeout=60,
                               params={"fields": "access_token", "access_token": token}))["access_token"]


def post_facebook(video: Path, title: str, caption: str, page_id: str, token: str) -> str:
    """Upload as a Page video with the Page's own token. Returns the video id."""
    with open(video, "rb") as f:
        done = _check(requests.post(f"https://graph-video.facebook.com/{page_id}/videos", timeout=900,
                                    data={"title": title[:250], "description": caption,
                                          "access_token": page_token_for(page_id, token)},
                                    files={"source": (video.name, f, "video/mp4")}))
    return done["id"]


def facebook_source_url(video_id: str, page_id: str, token: str, wait: int = 300) -> str:
    """Public file URL of a Page video once Facebook has processed it ("" if it never appears)."""
    page_token = page_token_for(page_id, token)
    deadline = time.time() + wait
    while time.time() < deadline:
        r = requests.get(f"{GRAPH}/{video_id}", timeout=60, params={"fields": "source", "access_token": page_token})
        if r.ok and r.json().get("source"):
            return r.json()["source"]
        time.sleep(15)
    return ""


def newest_short(root: Path) -> Optional[Path]:
    shorts = sorted(root.glob("*/short.mp4"), key=lambda p: p.stat().st_mtime)
    return shorts[-1].parent if shorts else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="", help="job folder with short.mp4 + script.json (default: newest)")
    ap.add_argument("--dry-run", action="store_true", help="print the caption, post nothing")
    ap.add_argument("--only", default="", choices=["", "instagram", "facebook"], help="post to one platform only")
    ap.add_argument("--fb-video", default="", help="id of the Facebook video already posted for this Short "
                                                   "(its file URL is Instagram's fallback)")
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
    failed, fb_video = False, a.fb_video
    if a.only in ("", "facebook"):
        if not page_id:
            print("Facebook: no page id set — skipped")
        else:
            try:
                fb_video = post_facebook(job / "short.mp4", title, caption, page_id, token)
                print(f"Facebook: posted, id {fb_video}")
            except Exception as e:  # noqa: BLE001 — Instagram still gets its turn
                failed = True
                print(f"Facebook: FAILED — {e}")
    if a.only in ("", "instagram"):
        if not ig_id:
            print("Instagram: no account id set — skipped")
        else:
            try:
                url = facebook_source_url(fb_video, page_id, token) if fb_video and page_id else ""
                print(f"Instagram: posted, id {post_instagram(job / 'short.mp4', caption, ig_id, token, video_url=url)}")
            except Exception as e:  # noqa: BLE001
                failed = True
                print(f"Instagram: FAILED — {e}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
