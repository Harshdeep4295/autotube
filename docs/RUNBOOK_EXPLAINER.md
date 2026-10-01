# Runbook: Animated Explainer pipeline (Phase A)

Everything here is free: GitHub's standard runner, Gemini/Groq free tiers, and
open-source software (Remotion free license, Kokoro, faster-whisper, FFmpeg).
Plan and background: [PLAN_EXPLAINER_AND_AI_VIDEO.md](PLAN_EXPLAINER_AND_AI_VIDEO.md).

**Channel direction (decided 2026-09-29).** A new channel on one sub-niche:
_Practical AI: free and open-source AI tools you can run and use yourself._
Voice is Kokoro `am_michael`. Every upload is **private** and carries the AI disclosure. You publish it.

---

## 1. How a video is made

```
research_agent  → topics from HN / Dev.to / Lobsters / Reddit / RSS, filtered to the niche
source_fetcher  → text of the topic's source article (grounding)
explainer_script_agent → outline + one call per chapter (Gemini free → Groq free)
                  every shot = 1-2 narration sentences + a scene from the catalogue
scene_schema    → validates / repairs every scene (nothing can overflow the frame)
fact_check      → flags numbers that are not in the source (for your review)
kokoro_voice    → one WAV per shot, so shot length = narration length
word_timing     → faster-whisper word times → captions (falls back to estimates)
video/explainer → Remotion renders 1920×1080 @ 30 fps
scripts/qa_video.py → length / black / freeze / loudness checks; failure blocks the upload
upload_agent    → PRIVATE upload + containsSyntheticMedia + thumbnail + captions
research_agent.mark_used → the topic is recorded only after a successful upload
```

| File | What it is |
|---|---|
| `agents/scene_schema.py` | Scene catalogue (15 scenes), validation, repair, prompt text, test fixtures |
| `agents/explainer_script_agent.py` | Topic → grounded script (outline + chapters) |
| `agents/llm.py` | Free-tier LLM chain with rate-limit retries and model fallback |
| `agents/explainer_agent.py` | Script → voice → props.json → Remotion → QA → thumbnail/SRT |
| `agents/kokoro_voice.py`, `agents/word_timing.py` | Voice and caption timing |
| `video/explainer/` | Remotion project (scenes in `src/scenes/`, registry in `src/scenes/registry.tsx`) |
| `scripts/qa_video.py` | Automated video QA (also a CLI) |
| `templates/explainer_prompts.py` | Prompts |
| `tests/` | pytest suite; `tests/fixtures/explainer_script.json` is the offline e2e script |

## 2. One-time setup

### 2.1 New YouTube channel
The channel is **Run It Local**. Name, handle, description, keywords, logo, banner, watermark and the
step-by-step list are in [CHANNEL_SETUP.md](CHANNEL_SETUP.md). `CHANNEL_NAME` defaults to "Run It Local";
set the GitHub variable only if you choose another name.

### 2.2 YouTube API credentials for the NEW channel (free)
1. Google Cloud console → create a project → **APIs & Services → Library → YouTube Data API v3 → Enable**.
2. **OAuth consent screen**: External. Add your Google account as a test user, then **Publish app**
   (set it to "In production"). While an app is in "Testing", Google expires its refresh tokens after 7 days,
   so uploads would stop working every week. For your own use you'll see an "unverified app" warning; that's fine.
3. **Credentials → Create OAuth client ID → Desktop app** → download the JSON.
4. Locally: put that JSON in `.env` as `YOUTUBE_CLIENT_SECRETS={...}` and run
   `python generate_youtube_token.py`. In the browser, **pick the new channel** when asked.
   Copy the printed token JSON.

### 2.3 Free LLM keys
- Gemini: https://aistudio.google.com → **Get API key** (free tier, no card).
- Groq (optional fallback): https://console.groq.com → API Keys.

### 2.4 GitHub settings (repo → Settings)
| Kind | Name | Value |
|---|---|---|
| Secret | `GEMINI_API_KEY` | from 2.3 |
| Secret | `GROQ_API_KEY` | optional |
| Secret | `YOUTUBE_TOKEN_JSON` | token JSON from 2.2 (the whole `{...}`) |
| Variable | `CHANNEL_NAME` | optional, default "Run It Local" |
| Variable | `KOKORO_VOICE` | optional, default `am_michael` |
| Variable | `GEMINI_FREE_MODELS` / `GROQ_FREE_MODELS` | optional. Change these when a free model is retired |

**Public or private repo?** Public: Actions minutes are free and unmetered, on 4 vCPU (faster renders).
Private: 2,000 free minutes/month, 2 vCPU. One video/day fits either way. Before making the
repo public, check nothing personal is committed (secrets live in GitHub Secrets, not the repo).

### 2.5 Retire the old setup
- VM: remove any AutoTube cron jobs (`crontab -e`), then stop/delete the VM if it bills you. The old
  renderer, its cron file and its workflows were removed from the repo on 2026-10-01.
- The old channel's upload log stays in `data/posted_videos.json`. New uploads are appended to it.

## 3. Running it

### Locally
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
(cd video/explainer && npm ci)
sudo apt-get install ffmpeg fonts-liberation     # macOS: brew install ffmpeg

# Offline: render the fixture script (no LLM, no upload) — the fastest way to see the look
.venv/bin/python -m agents.explainer_agent tests/fixtures/explainer_script.json --out outputs/test

# Full pipeline, no upload (needs GEMINI_API_KEY in .env)
.venv/bin/python orchestrator.py --dry-run
.venv/bin/python orchestrator.py --dry-run --topic "Running small AI models on a laptop"

# Full pipeline with PRIVATE upload
.venv/bin/python orchestrator.py
```
Output: `outputs/<date>_<id>/` with `video.mp4`, `thumbnail.jpg`, `captions.srt`, `script.json`
(including `fact_flags`), `qa.json`, `render_report.json` and `result.json`.

### GitHub Actions
- **Actions → Explainer Video → Run workflow.** `dry_run` is on by default. Download the result
  from the run's **Artifacts**.
- The daily schedule is on (03:17 UTC). Scheduled runs upload as Private unless the repo variable
  `SCHEDULED_DRY_RUN` is `true`; with `EXPLAINER_PUBLISH_AT_UTC` set, YouTube publishes the video at that time.

## 4. Tests

| What | Command | Runs in CI |
|---|---|---|
| Unit tests (schema, timing, fact check, free-only guard, script agent with a fake LLM, dry-run safety, research filters, QA detectors) | `.venv/bin/python -m pytest -q` | `tests.yml` → python |
| Scene tests: every scene at typical and maximum content; fails on clipped/off-screen text | `cd video/explainer && npm run test:scenes` | `tests.yml` → scenes (stills uploaded as an artifact) |
| Typecheck | `cd video/explainer && npx tsc --noEmit` | `tests.yml` → scenes |
| End-to-end render + QA | `python -m agents.explainer_agent tests/fixtures/explainer_script.json --out outputs/e2e` | `tests.yml` → e2e (video uploaded as an artifact) |
| QA on any video | `python scripts/qa_video.py path/to/video.mp4 --expected 512.3 --min 480` | after every render |

After changing `agents/scene_schema.py`, regenerate the Remotion fixtures:
`python -m agents.scene_schema --fixtures > video/explainer/test/fixtures.json` (a test checks they match).

## 5. Staging checklist (before the schedule goes on)

Run the workflow 5 times with `dry_run: true`. For each video, score 1-5 and write notes:

| # | Topic | Accuracy (facts match sources, `fact_flags` reviewed) | Pacing / voice | Scene fit (visual matches line) | Captions sync | Overall | Notes |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

Fix prompts and scenes until the average is ≥ 4. Then do 5 real runs (`dry_run: false`, still private),
check them in YouTube Studio (processing, thumbnail, captions, "altered content" label), and only then
enable the schedule.

## 6. Troubleshooting
- **"All free LLM options failed"**: a free model was retired or the daily quota is used up. Set the
  `GEMINI_FREE_MODELS` / `GROQ_FREE_MODELS` variables to currently-free models and re-run.
- **"script too short"**: the model returned too little. Re-run; if it keeps happening, try another model first.
- **"video failed QA: …"**: read `qa.json`. A length mismatch or black/frozen video means a render
  problem. A loudness failure usually means the music track is too loud.
- **Remotion `delayRender() … not cleared`**: fonts load inside the compositions (see
  `video/explainer/src/fonts.ts`). Don't move font loading to module level.
- **`fact_flags` in `script.json`**: numbers the narration uses that aren't in the source text.
  Check them before publishing.
- **Captions slightly off**: `render_report.json` → `timing_source`. `proportional` means faster-whisper
  wasn't available, so word times are estimates.

## 7. Known limits (as of 2026-09-29)
- The live LLM path (real Gemini/Groq calls) and faster-whisper alignment have not run yet. The authoring
  sandbox had no API key and couldn't reach Hugging Face. Both are covered by unit tests with fakes, and
  CI's e2e job downloads the whisper model, so the first CI run exercises whisper for real.
- 15 scene types. Watch the staging videos for repetition and grow the catalogue from what's missing.
- Phase B (AI video clips on a free Kaggle GPU) has not started. See the plan.
