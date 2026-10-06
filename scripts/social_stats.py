"""
Read-only numbers for the Instagram account and the Facebook Page (Meta Graph API), printed as
plain text. Run through the "Social Stats" workflow, which has the token.

    python scripts/social_stats.py

Environment: META_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID, FACEBOOK_PAGE_ID. Fields the token is not
allowed to read (Reel views need the instagram_manage_insights permission) show as "n/a".
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.post_reels import GRAPH, page_token_for  # noqa: E402


def get(path: str, token: str, **params) -> Optional[Dict]:
    """One Graph API read; None (with the reason printed) if Meta refuses it."""
    r = requests.get(f"{GRAPH}/{path}", params={**params, "access_token": token}, timeout=60)
    try:
        data = r.json()
    except ValueError:
        data = {"error": {"message": r.text[:200]}}
    if r.status_code >= 400 or "error" in data:
        print(f"  (could not read {path.split('?')[0]}: {str(data.get('error', {}).get('message', ''))[:160]})")
        return None
    return data


def reel_insights(media_id: str, token: str) -> Dict[str, int]:
    r = requests.get(f"{GRAPH}/{media_id}/insights", timeout=60,
                     params={"metric": "views,reach,saved,shares", "access_token": token})
    if not r.ok:
        return {}
    return {m["name"]: m["values"][0]["value"] for m in r.json().get("data", []) if m.get("values")}


def instagram(ig_id: str, token: str) -> None:
    print("== Instagram ==")
    acct = get(ig_id, token, fields="username,followers_count,media_count")
    if acct:
        print(f"@{acct.get('username')}: {acct.get('followers_count', 'n/a')} followers, {acct.get('media_count', 'n/a')} posts")
    media = get(f"{ig_id}/media", token, limit=25,
                fields="id,caption,media_product_type,permalink,timestamp,like_count,comments_count")
    for m in (media or {}).get("data", []):
        ins = reel_insights(m["id"], token)
        title = (m.get("caption") or "").split("\n")[0][:60]
        print(f"- {m.get('timestamp', '')[:16]}  views {ins.get('views', 'n/a')}  reach {ins.get('reach', 'n/a')}  "
              f"likes {m.get('like_count', 'n/a')}  comments {m.get('comments_count', 'n/a')}  "
              f"shares {ins.get('shares', 'n/a')}  saves {ins.get('saved', 'n/a')}\n  {title}\n  {m.get('permalink', '')}")


def facebook(page_id: str, token: str) -> None:
    print("== Facebook ==")
    page_token = page_token_for(page_id, token)
    page = get(page_id, page_token, fields="name,followers_count,fan_count")
    if page:
        print(f"{page.get('name')}: {page.get('followers_count', 'n/a')} followers, {page.get('fan_count', 'n/a')} likes")
    videos = get(f"{page_id}/videos", page_token, limit=25,
                 fields="id,title,created_time,views,permalink_url,likes.summary(true).limit(0),comments.summary(true).limit(0)")
    if videos is None:   # "views" can be refused on its own; the rest is still worth showing
        videos = get(f"{page_id}/videos", page_token, limit=25, fields="id,title,created_time,permalink_url")
    for v in (videos or {}).get("data", []):
        likes = v.get("likes", {}).get("summary", {}).get("total_count", "n/a")
        comments = v.get("comments", {}).get("summary", {}).get("total_count", "n/a")
        print(f"- {v.get('created_time', '')[:16]}  views {v.get('views', 'n/a')}  likes {likes}  comments {comments}\n"
              f"  {v.get('title', '')[:60]}\n  https://www.facebook.com{v.get('permalink_url', '')}")


def main() -> None:
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("META_ACCESS_TOKEN not set")
    if os.getenv("INSTAGRAM_ACCOUNT_ID"):
        instagram(os.environ["INSTAGRAM_ACCOUNT_ID"].strip(), token)
    if os.getenv("FACEBOOK_PAGE_ID"):
        facebook(os.environ["FACEBOOK_PAGE_ID"].strip(), token)


if __name__ == "__main__":
    main()
