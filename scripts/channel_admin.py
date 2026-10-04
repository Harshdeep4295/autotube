"""
Small channel housekeeping tasks, run through the "Channel Admin" workflow (it has the
YouTube token; nothing else does).

    python scripts/channel_admin.py status
    python scripts/channel_admin.py playlist-add --video TdWMrNFhfig --playlist "Explained Like You're 5"
    python scripts/channel_admin.py home-section --playlist "Explained Like You're 5"

`status` only reads. The other two change the channel and say what they did.
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["status", "playlist-add", "home-section"])
    ap.add_argument("--video", default="")
    ap.add_argument("--playlist", default="")
    a = ap.parse_args()
    agent = UploadAgent()
    if a.action == "status":
        status(agent.youtube)
    elif a.action == "playlist-add":
        if not (a.video and a.playlist):
            sys.exit("playlist-add needs --video and --playlist")
        playlist_add(agent, a.video, a.playlist)
    else:
        if not a.playlist:
            sys.exit("home-section needs --playlist")
        home_section(agent, a.playlist)


if __name__ == "__main__":
    main()
