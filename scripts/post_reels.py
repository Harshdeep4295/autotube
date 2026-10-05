"""
Post a kids Short (the vertical cut) as an Instagram Reel and a Facebook Page video.
Runs as a step of the kids workflow after the YouTube upload; free Meta Graph API.

    python scripts/post_reels.py                 # newest outputs/*/short.mp4
    python scripts/post_reels.py --dir outputs/20261005_kids_ab12cd --dry-run

Environment: META_ACCESS_TOKEN (long-lived user token, ~60 days), INSTAGRAM_ACCOUNT_ID,
FACEBOOK_PAGE_ID. A missing value skips that platform. Instagram fetches the file from a
temporary public copy (a release asset of this repo, removed afterwards). One platform failing does
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


RELEASE_TAG = "reels-tmp"


def public_copy(video: Path, name: str) -> str:
    """Put the file at a public URL (an asset on a prerelease of this public repo) for Instagram to
    fetch. Needs the gh CLI with GH_TOKEN, as in GitHub Actions; returns "" anywhere else."""
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not repo or not os.getenv("GH_TOKEN"):
        return ""
    gh = ["gh", "release", "--repo", repo]
    try:
        if subprocess.run(gh[:2] + ["view", RELEASE_TAG, "--repo", repo], capture_output=True).returncode != 0:
            subprocess.run(gh[:2] + ["create", RELEASE_TAG, "--repo", repo, "--prerelease", "--title",
                                     "Temporary files for Reel posting",
                                     "--notes", "Holds a Short for a few minutes while Instagram fetches it."],
                           check=True, capture_output=True, timeout=120)
        asset = video.with_name(name)
        asset.write_bytes(video.read_bytes())
        subprocess.run(gh[:2] + ["upload", RELEASE_TAG, str(asset), "--repo", repo, "--clobber"],
                       check=True, capture_output=True, timeout=600)
        return f"https://github.com/{repo}/releases/download/{RELEASE_TAG}/{name}"
    except Exception as e:  # noqa: BLE001
        print(f"Instagram: could not publish a temporary copy ({str(e)[:200]})")
        return ""


def remove_public_copy(name: str) -> None:
    subprocess.run(["gh", "release", "delete-asset", RELEASE_TAG, name, "--repo", os.getenv("GITHUB_REPOSITORY", ""), "-y"],
                   capture_output=True, timeout=120)


def post_instagram(video: Path, caption: str, ig_id: str, token: str, video_url: str = "", wait: int = 600) -> str:
    """Reel from a public `video_url` (two tries: Meta's fetch fails now and then); without one,
    or if both fail, a direct file upload. Returns the media id."""
    base = {"media_type": "REELS", "caption": caption, "access_token": token}
    for attempt in range(2 if video_url else 0):
        try:
            c = _check(requests.post(f"{GRAPH}/{ig_id}/media", timeout=60, data={**base, "video_url": video_url}))
            return _publish_container(c["id"], ig_id, token, wait)
        except RuntimeError as e:
            print(f"Instagram: posting from the public URL failed, try {attempt + 1} ({e})")
            time.sleep(60)
    c = _check(requests.post(f"{GRAPH}/{ig_id}/media", timeout=60, data={**base, "upload_type": "resumable"}))
    _check(requests.post(c["uri"], data=video.read_bytes(), timeout=600, headers={
        "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(video.stat().st_size)}))
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


def newest_short(root: Path) -> Optional[Path]:
    shorts = sorted(root.glob("*/short.mp4"), key=lambda p: p.stat().st_mtime)
    return shorts[-1].parent if shorts else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="", help="job folder with short.mp4 + script.json (default: newest)")
    ap.add_argument("--dry-run", action="store_true", help="print the caption, post nothing")
    ap.add_argument("--only", default="", choices=["", "instagram", "facebook"], help="post to one platform only")
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
    if a.only in ("", "facebook"):
        if not page_id:
            print("Facebook: no page id set — skipped")
        else:
            try:
                print(f"Facebook: posted, id {post_facebook(job / 'short.mp4', title, caption, page_id, token)}")
            except Exception as e:  # noqa: BLE001 — Instagram still gets its turn
                failed = True
                print(f"Facebook: FAILED — {e}")
    if a.only in ("", "instagram"):
        if not ig_id:
            print("Instagram: no account id set — skipped")
        else:
            name = f"short_{job.name}.mp4"
            url = public_copy(job / "short.mp4", name)
            try:
                print(f"Instagram: posted, id {post_instagram(job / 'short.mp4', caption, ig_id, token, video_url=url)}")
            except Exception as e:  # noqa: BLE001
                failed = True
                print(f"Instagram: FAILED — {e}")
            finally:
                if url:
                    remove_public_copy(name)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
