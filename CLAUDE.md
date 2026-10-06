# AutoTube — Claude Code Instructions

Autonomous faceless-YouTube pipeline for the channel **Run It Local** (free and open-source AI you can
run yourself). One entry point, `orchestrator.py`, with two video styles:

| Style | What it makes | Renderer | State (2026-10-01) |
|---|---|---|---|
| `explainer` (default) | 8+ min animated explainer on a practical-AI topic | Remotion (`video/explainer/`) | **Paused since 2026-10-04**: scheduled runs render but don't upload (`SCHEDULED_DRY_RUN=true`) . The topic bank exists since 2026-10-05; un-pause after a dry run has been reviewed |
| `kids` | 2–3 min "Explained Like You're 5" story video (finance / tech idea), plus a vertical cut uploaded as a Short | pycairo (`agents/kids/`) | **Live** since 2026-10-02: daily upload, public at 14:30 UTC |

**Hard constraint: $0.** Gemini and Groq free tiers, standard GitHub Actions runner, open-source
everything else. Never add a paid provider.

**Read next, by task:**
- What to fix and build next → `docs/GROWTH_PLAN.md`
- Explainer setup / run / test / troubleshooting → `docs/RUNBOOK_EXPLAINER.md`
- Explainer design, Phase B (AI clips on a free Kaggle GPU, not started) → `docs/PLAN_EXPLAINER_AND_AI_VIDEO.md`
- Kids track design, settings, milestones → `docs/PLAN_KIDS_EXPLAINER.md`
- Channel identity, brand files, Studio settings → `docs/CHANNEL_SETUP.md`
- Session history from 2026-09-29/30 → `docs/HANDOFF.md` (dated; parts are superseded by this file)

---

## Git workflow — IMPORTANT

**Never run `git add`, `git commit`, or `git push` without explicit instruction from the user.**

After code changes: say what changed, suggest a `git diff` review, suggest a commit message.

- `main` is production: both scheduled workflows run from it, and the bot commits topic history back to
  it (`chore: update topic history [skip ci]`). Pull before starting work.
- Work on a feature branch and merge by PR (PRs #1–#4 followed this). `shadow` is a stale branch from the
  old channel.
- Commit style: conventional prefixes with a scope, e.g. `feat(kids): …`, `fix(upload): …`, `ci(explainer): …`.
- The repo is **public**. Never commit secrets or personal details.

---

## Setup and commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
sudo apt-get install ffmpeg fonts-liberation fontconfig libcairo2-dev pkg-config python3-dev build-essential
(cd video/explainer && npm ci && npx remotion browser ensure)     # Node 22; explainer only

# Tests (no secrets, no network LLM calls)
.venv/bin/python -m pytest -q
(cd video/explainer && npm run test:scenes && npx tsc --noEmit)

# Offline renders of a fixture script (no LLM, no upload)
.venv/bin/python -m agents.explainer_agent tests/fixtures/explainer_script.json --out outputs/test
.venv/bin/python -m agents.kids_agent tests/fixtures/kids_stock_market.json --out outputs/kids_test

# Full pipeline without upload (needs GEMINI_API_KEY or GROQ_API_KEY in .env)
.venv/bin/python orchestrator.py --dry-run [--topic "..."] [--script path.json]
.venv/bin/python orchestrator.py --style kids --dry-run [--topic "What is interest?"]

# QA any video
.venv/bin/python scripts/qa_video.py path/to/video.mp4 --expected 512.3 --min 480
```

**Omitting `--dry-run` uploads to the real channel.** Always dry-run unless the user asks for an upload.

`orchestrator.py` flags: `--style explainer|kids` (overrides `VIDEO_STYLE`), `--dry-run`, `--topic`,
`--script` (skips research and the LLM), `--count`.

Output goes to `outputs/<date>_<id>/` (`<date>_kids_<id>` for kids): `video.mp4`, `thumbnail.jpg`,
`captions.srt`, `script.json`, `qa.json`, `render_report.json`, `result.json`, plus `contact_sheet.jpg`
for kids. `outputs/` and `logs/` are gitignored.

---

## Explainer pipeline (default)

```
research_agent          topic bank (data/explainer_topics.json: one open-source tool each, README as source);
                        news feeds (HN / Dev.to / Lobsters / Reddit / RSS, NICHE_KEYWORDS) once the bank is used up
source_fetcher          text of the source article (grounding)
explainer_script_agent  outline + one LLM call per chapter; repairs, salvage, top-up of short chapters
scene_schema            validate / repair every scene (unknown or broken → key_point)
fact_check              flags numbers not found in the source → script.json "fact_flags"
kokoro_voice            one WAV per shot (shot length = narration length)
word_timing             faster-whisper word times for captions (falls back to proportional)
video/explainer         Remotion render, 1920×1080 @ 30 fps, progress streamed to the log
scripts/qa_video.py     length / resolution / black / freeze / loudness; a failure blocks the upload
upload_agent            private upload, AI disclosure, thumbnail, captions, optional publishAt + playlist
research.mark_used      topic recorded only after a successful upload
```

Rules:
- The scene catalogue (15 types) lives in `agents/scene_schema.py`. Each type has one component in
  `video/explainer/src/scenes/`, registered in `registry.tsx`. After a catalogue change run
  `python -m agents.scene_schema --fixtures > video/explainer/test/fixtures.json` (a test checks they match).
- Load fonts inside compositions (`useFontsReady` in `src/fonts.ts`), never at module level: it breaks long renders.
- Loudness-normalize the voice in its own FFmpeg pass, never inside a mix graph: that drops the last ~3 s.
- A script is rejected before render if it cannot reach `EXPLAINER_MIN_SECONDS` at `EXPLAINER_WPM`.
- All LLM calls go through `agents/llm.py` (`FreeLLM`): Gemini free models, then Groq free models, with
  503 / rate-limit retries and automatic follow of a "use models/X" successor on a 404.

## Kids track (`--style kids`)

```
kids_topic_agent    headlines (KIDS_FEEDS) → LLM picks the evergreen idea; fallback data/kids_topics.json
                    (90 questions, finance ↔ tech alternate)
kids_script_agent   plan (one analogy) → scenes script → length guard (240–360 words) → checker + 1 fix round
kids_agent          validate / repair → Kokoro af_heart (Piper fallback) → word timings → beat timeline
                    → pycairo frames + ffmpeg → QA (≤ 180 s) → thumbnail, SRT, contact sheet
```

Rules:
- The scene catalogue (16 types), cast (7 characters) and prop list live in `agents/kids_scene_schema.py`.
  Each scene has one draw function in `agents/kids/scenes.py`; props are drawn in `agents/kids/props.py`.
  `tests/test_kids.py` fails if they drift.
- Line *i* of a scene fires beat *i*; a `cue` word moves the beat onto that word. Keep new scenes beat-driven.
- Hard cap 180 s. All ages, **not** made for kids. No advice, real brands, companies, people or coins,
  nothing scary; the checker enforces it and the description says "not financial advice".
- Shares voice, timing, QA, upload and history code with the explainer. No Node or browser needed.

## Upload rules (both styles)

- Uploads are **private** (`VIDEO_PRIVACY`), with `containsSyntheticMedia=true` and
  `selfDeclaredMadeForKids=false`.
- `EXPLAINER_PUBLISH_AT_UTC` / `KIDS_PUBLISH_AT_UTC` (`HH:MM`) make YouTube publish at the next such
  time; the gap is the owner's review window. Empty means private until published by hand.
- Each kids video also gets a vertical 9:16 cut (`short.mp4`, `agents/kids/short.py`) uploaded as a second
  video with `#Shorts`, a link to the full video, no custom thumbnail and no playlist. A failed Short never
  fails the run. `KIDS_SHORTS=false` turns it off.
- Playlists are matched by exact title and created on first use: `KIDS_PLAYLIST` for kids,
  `EXPLAINER_PLAYLIST` for explainers (empty = no playlist).
- Topic history (`data/topics_history.json`, `data/kids_topics_history.json`) and
  `data/posted_videos.json` are written only after a successful upload, then committed by the workflow.
  `posted_videos.json` also holds the old channel's uploads.

---

## GitHub Actions

| Workflow | Trigger | Notes |
|---|---|---|
| `tests.yml` | every push / PR | pytest, scene overflow tests + `tsc`, end-to-end fixture render + QA |
| `explainer.yml` | daily 03:17 UTC + manual | Scheduled runs **upload** unless repo variable `SCHEDULED_DRY_RUN=true`. Manual `dry_run` defaults to true. 90 min timeout |
| `kids_explainer.yml` | daily 03:47 UTC + manual | Scheduled runs **upload** because repo variable `KIDS_SCHEDULED_DRY_RUN=false` is set (the workflow default is dry). 45 min timeout |
| `channel_admin.yml` | manual | `status` (read-only), `playlist-add`, `home-section` on the YouTube channel |
| `post_reels.yml` | manual | Posts the Short of an earlier kids run (by run ID) to Instagram and/or Facebook |
| `social_stats.yml` | manual | Read-only Instagram and Facebook numbers (followers, per-post views and likes) printed in the run log |
| `kids_backfill.yml` | manual | Gives a published kids video a Short and the current description; needs the video ID and the ID of the run that made it (script from its artifact, kept 7 days). `dry_run` defaults to true |

- Secrets in use: `GEMINI_API_KEY`, `GROQ_API_KEY`, `YOUTUBE_TOKEN_JSON`. Older secrets for paid services
  (Anthropic, Kling, Pika, Replicate, GCP, Supabase, Pexels) are still stored but no workflow reads them.
- Repo variables set as of 2026-10-01: `EXPLAINER_PUBLISH_AT_UTC=18:30`, `KIDS_PUBLISH_AT_UTC=14:30`,
  `KIDS_SCHEDULED_DRY_RUN=false`, `GEMINI_FREE_MODELS`, `GROQ_FREE_MODELS`. Others (`CHANNEL_NAME`,
  `KOKORO_VOICE`, `EXPLAINER_PLAYLIST`, `SCHEDULED_DRY_RUN`, `KIDS_*`) are optional.
- Each run uploads `outputs/*` and `logs/` as an artifact kept 7 days. Read `script.json`, `qa.json` and
  `render_report.json` there when a run fails: `gh run download <run-id>`.
- Actions minutes are unmetered (public repo). An explainer run takes 32–43 min, a kids run about 4 min.
- GitHub can start scheduled runs hours late (the 03:17 UTC run on 2026-10-01 started at 10:15 UTC),
  which shortens the review window. A run that finishes less than 30 min before the publish time
  schedules the video for the next day.

---

## Key files

| File | Purpose |
|---|---|
| `config.py` | Every setting, read from env; `assert_free_only()` |
| `orchestrator.py` | Entry point: `run_explainer`, `run_kids`, upload scheduling, output cleanup |
| `agents/llm.py` | Free-tier LLM chain used by explainer and kids |
| `agents/explainer_script_agent.py`, `templates/explainer_prompts.py` | Explainer script writer and prompts |
| `agents/explainer_agent.py` | Script → voice → `props.json` → Remotion → QA → thumbnail / SRT |
| `agents/scene_schema.py`, `agents/fact_check.py`, `agents/source_fetcher.py` | Scene catalogue, number check, grounding |
| `agents/kokoro_voice.py`, `agents/word_timing.py` | Voice and caption timing (shared) |
| `agents/kids_agent.py`, `agents/kids_script_agent.py`, `agents/kids_topic_agent.py`, `templates/kids_prompts.py` | Kids render, script, topics, prompts |
| `agents/kids_scene_schema.py`, `agents/kids/` | Kids catalogue and pycairo renderer (draw, cast, props, scenes, timeline, render, voice, music) |
| `agents/research_agent.py` | Explainer topics: bank first (`EXPLAINER_TOPIC_MODE=bank`), news feeds as fallback; history |
| `data/explainer_topics.json` | Evergreen explainer topic bank (topic + GitHub repo); add entries freely |
| `agents/upload_agent.py` | YouTube Data API v3: resumable upload, thumbnail, captions, playlist |
| `scripts/qa_video.py` | Automated video QA, also a CLI |
| `scripts/commit_state.py` | Commits topic history / posted videos back to `main` without losing a race between workflows |
| `scripts/channel_admin.py` | Channel housekeeping (status, add a video to a playlist, home page section), run via `channel_admin.yml` |
| `scripts/post_reels.py` | Posts each kids Short as an Instagram Reel and a Facebook Page video (Meta Graph API). Step in `kids_explainer.yml`; needs secret `META_ACCESS_TOKEN` (expires about every 60 days; issued 2026-10-05) and variables `INSTAGRAM_ACCOUNT_ID`, `FACEBOOK_PAGE_ID`. Skips dry runs, never fails the run |
| `scripts/backfill_kids.py` | Short + current description for an already-published kids video, run via `kids_backfill.yml` |
| `generate_youtube_token.py` | One-time OAuth token generator for the channel |
| `video/explainer/` | Remotion 4 project: `src/scenes/`, `src/brand/`, `Thumbnail.tsx`, `test/scenes.test.mjs` |
| `branding/` | Logo, banner, watermark (rendered from `video/explainer/src/brand/`) |
| `tests/` | pytest suite and fixtures (`explainer_script.json`, `kids_*.json`) |
| `poc/ai_video/wan_clips.py` | Untested Phase B sketch (AI clips on a free GPU) |

---

## Config quick reference

```python
FREE_ONLY = true                    # refuses to start if SCRIPT_MODEL_PROVIDER=claude|bedrock, VIDEO_ANIMATION_MODE=veo
                                    # or GCS_BUCKET_NAME is still set in the environment
VIDEO_STYLE = "explainer"           # or "kids"
GEMINI_FREE_MODELS = "gemini-3.5-flash-lite,gemini-3.8-flash"   # comma lists, tried in order;
GROQ_FREE_MODELS   = "openai/gpt-oss-120b,qwen/qwen3-32b"       # change when a free model is retired
GEMINI_THINKING_LEVEL = "low"       # thinking tokens count against output; keeps long JSON from being cut off
CHANNEL_NAME = "Run It Local"       # CHANNEL_SUBNICHE and NICHE_KEYWORDS define and filter the niche
VIDEO_PRIVACY = "private"

# Explainer
EXPLAINER_TARGET_WORDS = 1100       # ≈ 8.5–9 min at EXPLAINER_WPM = 125 (measured ~122)
EXPLAINER_MIN_SECONDS = 480
EXPLAINER_PUBLISH_AT_UTC = ""       # e.g. "18:30"
EXPLAINER_PLAYLIST = ""             # playlist title; empty = none
EXPLAINER_TOPIC_MODE = "bank"       # bank = data/explainer_topics.json, feeds when used up; feed = news feeds only
KOKORO_VOICE = "am_michael"         # KOKORO_SPEED = 1.05; WORD_TIMINGS = "whisper" (falls back)

# Kids
KIDS_TARGET_WORDS = 300             # KIDS_MIN_SECONDS = 90, KIDS_MAX_SECONDS = 180, KIDS_WPM = 140
KIDS_KOKORO_VOICE = "af_heart"      # KIDS_KOKORO_SPEED = 0.92; KIDS_TTS = "kokoro" | "piper" (+ PIPER_MODEL)
KIDS_TOPIC_MODE = "mixed"           # "mixed" | "feed" | "bank"; KIDS_FEEDS = comma list of RSS URLs
KIDS_PUBLISH_AT_UTC = ""            # KIDS_PLAYLIST = "Explained Like You're 5"
KIDS_SHORTS = true                  # vertical cut uploaded as a Short; KIDS_SHORT_PUBLISH_AT_UTC = "" (same time as the full video)
```

---

## Current status and open work (2026-10-01)

- Two explainer videos are uploaded (Sep 30, Oct 1); the first has 3 views. Both topics were big-company
  model launches, not "tools you can run yourself". `docs/GROWTH_PLAN.md` lists the findings and the
  ordered fixes (topic bank, one hook and one call to action, thumbnails, hold videos with unverified numbers).
- The Gemini key returned `402 prepayment credits are depleted` on Oct 1, so scripts currently come from
  Groq only. The key appears to be on a prepaid billing account; replace it with a free-tier key.
- The old renderer, Shorts reposting, approval queue, paid-provider integrations and their docs were
  removed on 2026-10-01. Only the explainer and kids paths remain.
- Explainer uploads are paused (2026-10-04) because research kept picking off-niche news. The topic bank
  (2026-10-05) fixes the topics; un-pause by deleting the repo variable `SCHEDULED_DRY_RUN`.
- More kids scene types (rest of milestone M5) and Phase B (AI clips) have not started.
- The YouTube OAuth token was once shown in a chat session; `docs/HANDOFF.md` §4 has the revoke and
  regenerate steps. If the consent screen is in "Testing", refresh tokens expire after 7 days.

---

## Common pitfalls

- **`google-generativeai`** is the wrong package. Use `google-genai`: `from google import genai`.
- **"All free LLM options failed"**: a free model was retired or the daily quota is used up. Update
  `GEMINI_FREE_MODELS` / `GROQ_FREE_MODELS` (env or repo variable), not code.
- **"script too short"**: the model wrote too little even after top-ups. Re-run or put another model first.
- **Remotion `delayRender() … not cleared`**: font loading was moved to module level. Move it back.
- **Captions slightly off**: `render_report.json` → `timing_source: proportional` means faster-whisper
  was unavailable and the word times are estimates. With `av` 19 every line fails with
  `open() got an unexpected keyword argument 'metadata_errors'`; `requirements.txt` pins `av<19`.
- **Kokoro dies with `espeak-ng-data/phontab: No such file`**: the virtualenv path is too long (the
  espeak data path must stay under about 160 characters). Put the venv at a short path.
- **`madeForKids`** is read-only in the YouTube API. The writable field is `selfDeclaredMadeForKids`.
- **Refresh token expired**: the OAuth consent screen is still in "Testing". Publish the app.
- **Restricted sandboxes** (Claude Code on the web): Pollinations, Hugging Face and some other hosts
  may be blocked. Use CI for anything that needs them.

---

## MCP tools: code-review-graph

`.mcp.json` registers `code-review-graph` (run with `uvx`), and `.claude/settings.json` hooks update the
graph after edits. When the server is connected, use its tools (`detect_changes`, `get_impact_radius`,
`get_affected_flows`, `query_graph`, `semantic_search_nodes`, `get_architecture_overview`) before
Grep / Read for code exploration. When it is not installed, use the normal search tools.
