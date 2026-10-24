"""
Small channel housekeeping tasks, run through the "Channel Admin" workflow (it has the
YouTube token; nothing else does).

    python scripts/channel_admin.py status
    python scripts/channel_admin.py playlist-add --video TdWMrNFhfig --playlist "Explained Like You're 5"
    python scripts/channel_admin.py home-section --playlist "Explained Like You're 5"
    python scripts/channel_admin.py playlist-fill --playlist "Run AI Locally" --track explainer

`playlist-fill` adds every public full-length video of one track (explainer or kids; never
Shorts) that is not in the playlist yet, oldest first.

`status` only reads. The others change the channel and say what they did.
The channel trailer is not handled here: setting it means rewriting the channel's whole
branding block (name, description, keywords, banner), which is safer done in YouTube Studio.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.upload_agent import UploadAgent  # noqa: E402


def status(yt) -> None:
    ch = yt.channels().list(part="snippet,status,statistics,brandingSettings", mine=True).execute()["items"][0]
    st, stats = ch.get("status", {}), ch.get("statistics", {})
    print(f"Channel        : {ch['snippet']['title']} ({ch['id']})")
    print(f"Subscribers    : {stats.get('subscriberCount', '?')}   Views: {stats.get('viewCount', '?')}   "
          f"Videos: {stats.get('videoCount', '?')}")
    print(f"Long uploads   : {st.get('longUploadsStatus', '?')}  (\"allowed\" = phone-verified)")
    print(f"Made for kids  : {st.get('madeForKids', '?')}")
    print(f"Trailer video  : {ch.get('brandingSettings', {}).get('channel', {}).get('unsubscribedTrailer') or 'not set'}")
    print("Playlists:")
    for p in yt.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50).execute().get("items", []):
        print(f"  - {p['snippet']['title']}  ({p['contentDetails']['itemCount']} videos, {p['id']})")
    print("Home page sections:")
    for s in yt.channelSections().list(part="snippet,contentDetails", mine=True).execute().get("items", []):
        print(f"  - position {s['snippet'].get('position')}: {s['snippet']['type']} "
              f"{s.get('contentDetails', {}).get('playlists', '')}")


def playlist_add(agent: UploadAgent, video: str, playlist: str) -> None:
    pid = agent._find_playlist(playlist) or agent._create_playlist(playlist)
    items = agent.youtube.playlistItems().list(part="snippet", playlistId=pid, maxResults=50).execute().get("items", [])
    if any(i["snippet"]["resourceId"].get("videoId") == video for i in items):
        print(f"Already in '{playlist}': {video}")
        return
    agent._add_to_playlist(video, pid)
    print(f"Added {video} to '{playlist}' ({pid})")


def home_section(agent: UploadAgent, playlist: str) -> None:
    yt = agent.youtube
    pid = agent._find_playlist(playlist)
    if not pid:
        sys.exit(f"No playlist titled '{playlist}' on the channel")
    for s in yt.channelSections().list(part="snippet,contentDetails", mine=True).execute().get("items", []):
        if pid in s.get("contentDetails", {}).get("playlists", []):
            print(f"'{playlist}' is already a home page section")
            return
    yt.channelSections().insert(
        part="snippet,contentDetails",
        body={"snippet": {"type": "singlePlaylist"}, "contentDetails": {"playlists": [pid]}},
    ).execute()
    print(f"Added '{playlist}' as a home page section")


def track_of(title: str) -> str:
    """'kids', 'explainer' or 'short' from an upload's title."""
    if "#shorts" in title.lower():
        return "short"
    return "kids" if "Explained Like You're 5" in title else "explainer"


def playlist_fill(agent: UploadAgent, playlist: str, track: str) -> None:
    from scripts.link_comments import channel_uploads
    yt = agent.youtube
    pid = agent._find_playlist(playlist) or agent._create_playlist(playlist)
    have, token = set(), None
    while True:
        res = yt.playlistItems().list(part="snippet", playlistId=pid, maxResults=50, pageToken=token).execute()
        have |= {i["snippet"]["resourceId"].get("videoId") for i in res.get("items", [])}
        token = res.get("nextPageToken")
        if not token:
            break
    _, videos = channel_uploads(yt)
    todo = [v for v in reversed(videos)   # uploads come newest first
            if v["privacy"] == "public" and track_of(v["title"]) == track and v["id"] not in have]
    for v in todo:
        agent._add_to_playlist(v["id"], pid)
        print(f"Added {v['id']} ({v['title'][:60]}) to '{playlist}'")
    print(f"Done: {len(todo)} added, {len(have)} were already in '{playlist}'.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["status", "playlist-add", "home-section", "playlist-fill"])
    ap.add_argument("--video", default="")
    ap.add_argument("--playlist", default="")
    ap.add_argument("--track", default="explainer", choices=["explainer", "kids"])
    a = ap.parse_args()
    agent = UploadAgent()
    if a.action == "status":
        status(agent.youtube)
    elif a.action == "playlist-add":
        if not (a.video and a.playlist):
            sys.exit("playlist-add needs --video and --playlist")
        playlist_add(agent, a.video, a.playlist)
    elif a.action == "playlist-fill":
        if not a.playlist:
            sys.exit("playlist-fill needs --playlist")
        playlist_fill(agent, a.playlist, a.track)
    else:
        if not a.playlist:
            sys.exit("home-section needs --playlist")
        home_section(agent, a.playlist)


if __name__ == "__main__":
    main()
