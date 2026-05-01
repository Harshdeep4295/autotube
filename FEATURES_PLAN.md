# AutoTube — New Features Plan

Three new features planned for implementation, each env-var-gated and off by default.

---

## Feature 3: Auto-Playlist Grouping

**Status:** Phase 1 (implement first — least invasive, no OAuth changes needed)

### What it does
After each successful YouTube upload, detects which playlist the video belongs to (by matching title/tags against a keyword map) and automatically adds it to that playlist. Auto-creates new playlists when a keyword has no existing match.

### New env vars
| Var | Default | Description |
|---|---|---|
| `PLAYLIST_ENABLED` | `false` | Enable/disable this feature |
| `PLAYLIST_MAP_JSON` | `{}` | JSON map of keyword → playlist ID for pre-seeding known playlists |
| `PLAYLIST_AUTO_CREATE` | `true` | Auto-create playlist via API when no match found |

### How to test
```bash
PLAYLIST_ENABLED=true PLAYLIST_MAP_JSON='{"AI": "PLyourplaylistid"}' python orchestrator.py --dry-run
```

### Files changed
| File | Change |
|---|---|
| `config.py` | Add `PLAYLIST_ENABLED`, `PLAYLIST_MAP`, `PLAYLIST_AUTO_CREATE` fields + `import json` |
| `agents/upload_agent.py` | Add `_add_to_playlist()` and `_resolve_playlist_id()` methods; call after upload |
| `data/playlists.json` | New file — persists auto-created playlist IDs across runs |

### How playlist resolution works
1. Check `PLAYLIST_MAP_JSON` for a static keyword→ID match (env var, fast path)
2. Check `data/playlists.json` for a previously auto-created playlist
3. Call `playlists().list(mine=True)` to check existing channel playlists
4. If still no match and `PLAYLIST_AUTO_CREATE=true`: call `playlists().insert()` to create, save to `data/playlists.json`

Keyword is derived from `script["tags"][0]` or falls back to `config.CHANNEL_NICHE`.

### OAuth note
Requires `youtube` full scope (for `playlists().insert()` and `playlistItems().insert()`). If the existing token lacks this scope, the `_add_to_playlist()` call is wrapped in try/except — a 403 logs a warning but does NOT break the upload.

---

## Feature 2: Audience-Driven Topics (YouTube Comments)

**Status:** Phase 2 (implement after Feature 3; requires OAuth re-auth)

### What it does
Adds a new topic source that reads comments from:
1. **Own recent uploads** — surfaces questions viewers asked about your own videos
2. **Competitor/related videos** — pulls top-viewed niche videos and extracts comment questions

Sourced topics flow into the existing `get_topics()` → scoring → dedup pipeline unchanged.

### New env vars
| Var | Default | Description |
|---|---|---|
| `COMMENTS_ENABLED` | `false` | Enable/disable this feature |
| `COMMENTS_OWN_VIDEOS` | `10` | How many of your own recent videos to scan |
| `COMMENTS_COMPETITOR_VIDEOS` | `5` | How many competitor videos to scan via YouTube Search |
| `COMMENTS_MAX_PER_VIDEO` | `100` | Max comments per video to process |

### How to test
```bash
COMMENTS_ENABLED=true python orchestrator.py --dry-run --count 1
```
Check logs for `YouTube Comments: N topics`. Check `data/topics_history.json` for entries with `source: "youtube_comments"`.

### Files changed
| File | Change |
|---|---|
| `config.py` | Add `COMMENTS_ENABLED`, `COMMENTS_OWN_VIDEOS`, `COMMENTS_COMPETITOR_VIDEOS`, `COMMENTS_MAX_PER_VIDEO` |
| `agents/comment_research_agent.py` | **New file** — `CommentResearchAgent` class |
| `agents/research_agent.py` | Add comment source call at end of `get_topics()` (line ~285) |

### `CommentResearchAgent` design

```
get_comment_topics()
  │
  ├─ _get_own_video_ids(max=COMMENTS_OWN_VIDEOS)
  │     channels().list(mine=True) → uploadsPlaylistId
  │     playlistItems().list(playlistId=...) → [video_ids]
  │
  ├─ _get_competitor_video_ids(max=COMMENTS_COMPETITOR_VIDEOS)
  │     search().list(q=CHANNEL_NICHE, type='video', order='viewCount') → [video_ids]
  │     (costs 100 quota units per call; 5 calls = 500 of 10,000 daily quota)
  │
  ├─ _fetch_comments(video_id) per video
  │     commentThreads().list(order='relevance', textFormat='plainText')
  │
  ├─ _extract_questions(comments)
  │     Regex: "can you do X", "video on X", "what about X",
  │            "how does X", "I wish you covered X", "next video on X"
  │
  └─ _score_comment_topic(question, frequency)
        Returns: {topic, angle, source="youtube_comments",
                  trend_score=frequency*10, reddit_mentions=0, quality_score}
```

Topic dict shape is compatible with all other sources — no changes to scoring/dedup needed.

### OAuth re-auth (required for Features 2 + 3)

The current token at `data/youtube_token.json` has only `youtube.upload` scope. Features 2 and 3 need the full `youtube` scope. Do this once for both:

1. Edit `generate_youtube_token.py` line ~25:
   ```python
   SCOPES = [
       "https://www.googleapis.com/auth/youtube",
       "https://www.googleapis.com/auth/youtube.force-ssl",
   ]
   ```
2. Edit `upload_agent.py` `_build_service()` lines ~223–226 to match
3. Edit `setup.py` lines ~138–141 to match
4. Delete `data/youtube_token.json`
5. Run `python generate_youtube_token.py` — browser OAuth flow, saves new token
6. Update `YOUTUBE_TOKEN_JSON` GitHub Secret with new token content

---

## Feature 1: Multi-Format Shorts (9:16)

**Status:** Phase 3 (implement last — most invasive, touches rendering pipeline)

### What it does
Enables generating vertical 9:16 video (1080×1920) for YouTube Shorts / TikTok. Activated by setting `VIDEO_FORMAT=shorts`. All existing 16:9 behavior is untouched when `VIDEO_FORMAT=landscape` (default).

Shorts mode also:
- Generates a shorter script (~150 words, 60s target)
- Appends `#Shorts` to title and description
- Adjusts caption placement to avoid UI chrome overlap
- Fetches portrait-oriented Pexels clips

### New env vars
| Var | Default | Description |
|---|---|---|
| `VIDEO_FORMAT` | `landscape` | `landscape` = 1920×1080, `shorts` = 1080×1920 |
| `SHORTS_WORD_COUNT` | `150` | Target word count for Shorts scripts |

### How to test
```bash
VIDEO_FORMAT=shorts python orchestrator.py --dry-run --count 1
```
Then: `ffprobe outputs/.../video.mp4` — confirm resolution is 1080×1920.

### Files changed
| File | Lines | Change |
|---|---|---|
| `config.py` | 129–130 | Make `VIDEO_WIDTH`/`VIDEO_HEIGHT` env-aware (1080/1920 if shorts) |
| `config.py` | 134–135 | Make `THUMB_WIDTH`/`THUMB_HEIGHT` env-aware |
| `config.py` | new | Add `VIDEO_FORMAT`, `SHORTS_WORD_COUNT`, `IS_SHORTS` property |
| `agents/video_agent.py` | 881 | `imagen.generate(full_prompt, 1920, 1080)` → use `self.W, self.H` |
| `agents/video_agent.py` | 898 | Pollinations URL hardcoded `1920x1080` → `{self.W}x{self.H}` |
| `agents/video_agent.py` | 1332 | Pexels `"orientation": "landscape"` → portrait when shorts |
| `agents/video_agent.py` | 509 | Pika `"aspect_ratio": "16:9"` → `"9:16"` when shorts |
| `agents/video_agent.py` | 1756 | Caption Y: `self.H - 180` → `self.H - 300` when shorts |
| `agents/thumbnail_agent.py` | 117 | Pollinations URL hardcoded `1280x720` → `{self.W}x{self.H}` |
| `agents/thumbnail_agent.py` | `_add_vignette()` | Left gradient → bottom gradient for portrait |
| `agents/thumbnail_agent.py` | `_add_headline()` | Y position adapts for portrait layout |
| `agents/script_agent.py` | `generate()` | Branch to `SHORTS_USER_PROMPT` when `config.IS_SHORTS` |
| `agents/upload_agent.py` | `_upload_video()` | Append `#Shorts` to title/description when shorts |
| `templates/prompts.py` | new | Add `SHORTS_USER_PROMPT` — 150 words, 3 sections, title ends with `#Shorts` |

---

## Interaction Matrix (when all three are active)

| Pipeline stage | Feature active | Effect |
|---|---|---|
| `get_topics()` | F2 (comments) | Comment topics injected alongside Reddit/RSS/HN |
| `script.generate()` | F1 (shorts) | Uses shorter Shorts prompt (~150 words) |
| `video.render()` | F1 (shorts) | Renders 1080×1920, portrait clips, adjusted captions |
| `thumbnail.create()` | F1 (shorts) | Renders 1080×1920 thumbnail with portrait layout |
| `uploader.publish()` | F1 (shorts) | Appends `#Shorts` to title/description |
| `uploader.publish()` | F3 (playlist) | After upload: resolves/creates playlist, inserts video |

No conflicts — each feature hooks into a different pipeline stage.
