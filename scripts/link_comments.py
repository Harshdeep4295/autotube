"""
Put a "▶ Full video: <link>" comment from the channel on every public Short.

Shorts viewers rarely open the description, but the comments sit right in the Shorts player.
The link is taken from the Short's own description ("Watch the full video: <url>"), so a Short
without one is skipped. Safe to run again: a Short that already has a comment from the channel
is left alone. Private or scheduled Shorts are skipped and picked up on a later run.

    python scripts/link_comments.py --dry-run    # only lists what it would post
    python scripts/link_comments.py
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FULL_LINK = re.compile(r"Watch the full video:\s*(https?://\S+)")


def full_video_link(description: str) -> str:
    m = FULL_LINK.search(description or "")
    return m.group(1).rstrip(".,)") if m else ""


def comment_text(link: str) -> str:
    return f"▶ Full video: {link}"


def channel_uploads(yt, limit: int = 200) -> list:
    """Newest uploads of the signed-in channel: id, title, description, privacy."""
    ch = yt.channels().list(part="id,contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < limit:
        res = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50,
                                      pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in res.get("items", [])]
        token = res.get("nextPageToken")
        if not token:
            break
    out = []
    for i in range(0, len(ids), 50):
        res = yt.videos().list(part="snippet,status", id=",".join(ids[i:i + 50])).execute()
        for v in res.get("items", []):
            out.append({"id": v["id"], "title": v["snippet"]["title"],
                        "description": v["snippet"].get("description", ""),
                        "privacy": v["status"].get("privacyStatus", "")})
    return ch["id"], out


def has_channel_comment(yt, video_id: str, channel_id: str) -> bool:
    res = yt.commentThreads().list(part="snippet", videoId=video_id, maxResults=100,
                                   moderationStatus="published").execute()
    for t in res.get("items", []):
        author = t["snippet"]["topLevelComment"]["snippet"].get("authorChannelId", {}).get("value")
        if author == channel_id:
            return True
    return False


def to_comment(videos: list) -> list:
    """Public Shorts that point to a full video: [(video, link)]."""
    out = []
    for v in videos:
        if "#shorts" not in v["title"].lower() or v["privacy"] != "public":
            continue
        link = full_video_link(v["description"])
        if link:
            out.append((v, link))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="only list what would be posted")
    a = ap.parse_args()

    from agents.upload_agent import UploadAgent
    yt = UploadAgent().youtube
    channel_id, videos = channel_uploads(yt)
    posted = skipped = 0
    for v, link in to_comment(videos):
        if has_channel_comment(yt, v["id"], channel_id):
            skipped += 1
            continue
        if a.dry_run:
            print(f"Would comment on {v['id']} ({v['title'][:60]}): {comment_text(link)}")
            posted += 1
            continue
        try:
            yt.commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": v["id"],
                "topLevelComment": {"snippet": {"textOriginal": comment_text(link)}},
            }}).execute()
        except Exception as e:  # noqa: BLE001
            if "insufficient" in str(e).lower() or "forbidden" in str(e).lower():
                sys.exit(f"YouTube refused the comment ({e}). The sign-in token may lack the "
                         "youtube.force-ssl permission; nothing else was changed.")
            print(f"Could not comment on {v['id']}: {e}")
            continue
        print(f"Commented on {v['id']} ({v['title'][:60]}): {comment_text(link)}")
        posted += 1
    verb = "would post" if a.dry_run else "posted"
    print(f"Done: {verb} {posted}, already had a channel comment {skipped}.")


if __name__ == "__main__":
    main()
