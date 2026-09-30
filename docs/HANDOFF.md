# Session handoff — AutoTube / "Run It Local" (2026-09-29)

For the next agent picking this up. Read this first, then `CLAUDE.md`,
`docs/RUNBOOK_EXPLAINER.md`, `docs/PLAN_EXPLAINER_AND_AI_VIDEO.md`, `docs/CHANNEL_SETUP.md`.

## 1. The goal
The owner wants a **free-only** (no paid services at all) faceless YouTube channel as a second
income. The old channel ("AutoTube", 131 mixed-topic uploads, ~0 views) was abandoned. The new channel is
**Run It Local** (`runitvideoonlocal@gmail.com`, channel ID `UCvQ4krhheYmVibo3nfVdrJw`): 8+ minute
**animated explainer** videos about free / open-source AI tools you can run yourself.

**The owner has no computer**, only a phone. Everything must run in GitHub Actions or a Claude
session. They can only paste things into GitHub or Google settings pages.

## 2. What's done (merged to `main`)
- **PR #1**, the Phase A explainer pipeline: research (niche filter, source URLs) → grounded
  script (Gemini free → Groq free, outline + one call per chapter) → scene validate/repair (15 scene types) →
  Kokoro TTS per shot → faster-whisper word timings → Remotion render (`video/explainer/`) → automated QA
  (`scripts/qa_video.py`) → **private** upload with `containsSyntheticMedia`.
  - `FREE_ONLY=true` guard (`config.assert_free_only()`).
  - Dry-run upload bug fixed; topics are recorded only after a successful upload.
  - Legacy crons and prefetch schedule retired.
- **PR #2**, the brand kit: logo, banner, watermark in `branding/`, a brand mark in every frame and
  thumbnail, `CHANNEL_NAME` defaults to "Run It Local".
- CI `.github/workflows/tests.yml` is green on `main`: 44 pytest tests, 30 scene overflow fixtures,
  and an end-to-end render of `tests/fixtures/explainer_script.json` that passes all 11 QA checks
  (and uses real whisper timings in CI).

## 3. Current state / where it broke
- **GitHub secrets set by the owner:** `YOUTUBE_TOKEN_JSON` (OAuth token for Run It Local, verified to
  refresh) and `GEMINI_API_KEY`. `GROQ_API_KEY` is **not** set. No repo variables are set.
- **Explainer dry run #2 failed**
  ([run 36542601435](https://github.com/Harshdeep4295/autotube/actions/runs/36542601435)) at the script
  step. Google retired the default models for new users: `gemini-2.5-flash-lite` → 404 "use
  models/gemini-3.5-flash-lite", and `gemini-2.5-flash` → 404 "use models/gemini-3.8-flash".
  Research worked: it picked "Combining Machine Learning and Homomorphic Encryption in the Apple
  Ecosystem" and fetched 6,000 characters of source text.
- **Fix: on branch `claude/busy-planck-wuvyw9`, NOT merged.** This commit changes the default
  `GEMINI_FREE_MODELS` to `gemini-3.5-flash-lite,gemini-3.8-flash` (config.py + explainer.yml), makes
  `agents/llm.py` follow the "use models/X" successor in a 404 automatically, and remembers the working
  model for later calls. There are 2 new tests; 46 pass locally. **Next step:** open a PR, let CI pass, merge,
  then re-run *Explainer Video* with `dry_run: true`.
  - Workaround without code: repo variable `GEMINI_FREE_MODELS=gemini-3.5-flash-lite,gemini-3.8-flash`.

## 4. Known issues and risks (the owner says "lots of issues"; be skeptical)
1. **The real LLM path has never completed a script.** Unknowns:
   - Will gemini-3.x return valid JSON for the outline and chapter prompts?
   - Is the output long enough (target 1,150 words)?
   - The newest Flash free tier reportedly allows only ~20 requests/day. One video uses about 7-9 calls
     (1 outline + 5-6 chapters + repairs), and retries could exhaust that.

   Watch the first run's `script.json` (`fact_flags`, `script_repairs`, word count).
2. **No LLM fallback.** Groq isn't configured, and the Groq model names in `GROQ_FREE_MODELS`
   (`openai/gpt-oss-120b,qwen/qwen3-32b`) are **unverified guesses**. Groq dropped Llama from its free
   tier in Aug 2026.
3. **YouTube upload has never run live.** The token is verified (right channel, refresh works), but
   `videos.insert` with `containsSyntheticMedia`, the thumbnail upload (needs a phone-verified channel)
   and the captions upload are untested. Unknown whether the Google OAuth consent screen is "In
   production". If it's still "Testing", the refresh token expires after 7 days.
4. **Security: the YouTube token was shown in chat** at the owner's request, so they could paste it into
   GitHub. If in doubt, revoke it (myaccount.google.com → Security → Third-party connections → "Run It
   Local Uploader") and regenerate. The token can be made from a phone with the two-step loopback trick:
   generate an auth URL with redirect `http://localhost:8080/`; the owner signs in on the phone and pastes
   back the failing `localhost` URL, which contains the code; exchange it with the saved PKCE verifier.
   `client_secrets.json` is not in the repo (gitignored) and was only in the old session's container. The
   owner has the file.
5. **Render time:** CI rendered an 89 s video in about 5.6 min on a 2-vCPU runner (whisper included). An
   8-min video will take roughly 25-35 min. `explainer.yml` has `timeout-minutes: 90`. The repo is private
   (2,000 free Actions minutes/month).
6. **Content quality is unproven.** 15 scene types may feel repetitive. The prompts in
   `templates/explainer_prompts.py` have never been tuned on real output. The staging checklist in
   RUNBOOK §5 (5 dry runs, scored by the owner) hasn't started.
7. **Topic history:** `explainer.yml` commits `data/topics_history.json` back to `main` after a
   successful non-dry run (`contents: write`). This is untested. `data/posted_videos.json` still holds
   the old channel's uploads.
8. **Large legacy code** (`agents/video_agent.py` with 2.8k lines, Kling/Veo stubs, WhatsApp/Supabase
   queue) is still in the repo behind `VIDEO_STYLE=legacy`. It's not cleaned up.
9. **Phase B (AI video clips on a free Kaggle GPU) hasn't started.** `poc/ai_video/wan_clips.py` is an
   untested sketch.

## 5. Environment gotchas (Claude Code web sandbox)
- Outbound network is restricted. Pollinations, Pexels, Pixabay, Hugging Face and the edge-tts servers
  are blocked. GitHub, PyPI, npm and Google APIs (OAuth, YouTube, Gemini) are reachable. Use CI for anything
  needing blocked hosts.
- Local setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt`,
  `apt-get install ffmpeg`, `(cd video/explainer && npm ci)`. Kokoro model: set `KOKORO_DIR` or let it
  download from GitHub releases. Remotion here needs
  `REMOTION_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell`.
- The owner's `CLAUDE.md` says: **no git add/commit/push without explicit instruction.** The owner has
  approved PRs and merges in this session. Ask again in a new one.
- There are no tools to set GitHub secrets or variables; the owner must paste them. Workflows can be
  triggered with the GitHub MCP `actions_run_trigger` (`explainer.yml`, ref `main`, inputs `dry_run`,
  `topic`, `script`).

## 6. Suggested next steps
1. Merge the Gemini model fix (branch `claude/busy-planck-wuvyw9`), then re-run the dry run.
2. Read the run's artifact (`script.json`, `qa.json`, `render_report.json`, `logs/`), fix what breaks, and
   repeat until one full dry run produces an 8+ min video that passes QA.
3. Ask the owner to add a `GROQ_API_KEY` (free) and verify the current Groq free model names.
4. Do one real private upload (`dry_run: false`) and check it in YouTube Studio.
5. Then the RUNBOOK §5 staging loop, and only after that enable the daily schedule.

## 7. Script-writer hardening (2026-09-29, Cowork session)
Dry runs #2-#4 on `main` failed in step 2: gemini-2.5 → 404 (fixed by the model names above);
then `gemini-3.8-flash` always 503 "high demand" (not retried) and `gemini-3.5-flash-lite`
returned list-shaped / cut-off JSON and chapters at ~half the requested length
("only 117 words, need about 260"). Changes:
- `agents/llm.py`: 503/overload errors retried with backoff; Gemini thinking capped
  (`GEMINI_THINKING_LEVEL`, default `low`, auto-dropped if a model rejects it); MAX_TOKENS logged.
- `agents/explainer_script_agent.py`: bare-list JSON accepted; complete shots salvaged from cut-off
  answers; explicit shot counts; up to 2 repairs; short chapters topped up with continuation calls
  (`CONTINUE_USER`, CTA kept last); script rejected *before* render if it can't reach
  `EXPLAINER_MIN_SECONDS` at `EXPLAINER_WPM` (160, measured on the fixture).
- `config.py`: length now set from a real run: dry run #6 (Groq `gpt-oss-120b`, Gemini key blocked with 403)
  PASSED: 1426 words → 699 s narration ≈ **122 wpm**, 43 min total, 167 MB artifact. So
  `EXPLAINER_WPM` = 125 and `EXPLAINER_TARGET_WORDS` = 1100 (≈ 8.5-9 min, ~30% shorter render).
- `agents/explainer_agent.py`: Remotion output is streamed; a progress line is logged about once a
  minute (the render used to be silent for ~30 min) and the tail is kept for error messages.
- Budget: a lazy model that writes half the asked length now needs ~20 calls per video.
