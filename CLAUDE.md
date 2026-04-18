# AutoTube — Claude Code Instructions

Autonomous faceless YouTube channel pipeline. Runs 4×/day on GitHub Actions, producing 1 video per run. No server required — GitHub IS the infrastructure.

---

## Git Workflow — IMPORTANT

**Never run `git add`, `git commit`, or `git push` without explicit instruction from the user.**

After completing code changes, tell the user:
- Which files were changed and what was changed
- That they should review with `git diff` before committing
- Suggest a commit message, but let them run the command

The user reviews all changes before committing. Do not automate git operations.

---

## How to Run Locally

```bash
# Dry run (no upload) — always test this first
.venv/bin/python3 orchestrator.py --dry-run --topic "Artificial Intelligence in 2025"

# Or via convenience script
./run_local.sh --topic "some topic"          # dry run
./run_local.sh --upload --topic "some topic" # live upload
```

Output lands in `outputs/<date>_<id>/video.mp4`. Open with `open outputs/`.

---

## Key Files

| File | Purpose |
|---|---|
| `config.py` | Single source of truth for all settings — edit here first |
| `orchestrator.py` | Pipeline entry point — wires agents together |
| `agents/research_agent.py` | pytrends + Reddit + RSS → scored topic list |
| `agents/script_agent.py` | Claude or Gemini → structured script JSON |
| `agents/voice_agent.py` | edge-tts (primary) + pyttsx3 (fallback) → audio.mp3 |
| `agents/video_agent.py` | Pexels B-roll + Pillow captions → 1920×1080 MP4 |
| `agents/thumbnail_agent.py` | Pillow → 1280×720 JPEG thumbnail |
| `agents/upload_agent.py` | YouTube Data API v3, OAuth2, resumable upload |
| `templates/prompts.py` | All LLM prompt templates — script structure defined here |
| `.github/workflows/daily_pipeline.yml` | 4 cron triggers (09/12/15/18 IST) |

---

## Critical Tech Notes

### MoviePy version is 2.x — NOT 1.x
The installed version is `moviepy==2.2.1`. The API is completely different from 1.x:
- Imports: `from moviepy import VideoFileClip` (not `from moviepy.editor import ...`)
- Chaining: `.with_duration()`, `.with_audio()`, `.with_position()`, `.with_opacity()`, `.with_start()`
- Trim: `.subclipped(start, end)` (not `.subclip()`)
- Resize: `.resized(new_size=(w, h))` (not `.resize()`)
- Crop: `.cropped(x1=, y1=, x2=, y2=)` (not `.crop()`)
- Volume: `from moviepy.audio.fx import MultiplyVolume` then `.with_effects([MultiplyVolume(0.06)])`
- Never use `.set_duration()`, `.set_audio()`, `.set_position()` — these are 1.x methods and will fail silently or crash

### Google Generative AI package
Use `google-genai` (new), NOT `google-generativeai` (deprecated):
```python
from google import genai
from google.genai import types
client = genai.Client(api_key=config.GEMINI_API_KEY)
client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(system_instruction=..., max_output_tokens=4096)
)
```

### IST → UTC conversion
`config.py` auto-converts `UPLOAD_TIMES_IST` to UTC. Edit times in IST only — never touch UTC manually. The `_ist_to_utc()` helper subtracts 330 minutes.

### Script JSON structure
`script_agent.py` requires these keys: `title`, `description`, `tags`, `sections`, `thumbnail_text`.
`video_agent.py` also uses: `visual_queries` (list of 6 cinematic Pexels search terms, one per section) and `hook_title_text` (bold opener text). These are optional with fallbacks.

### Pexels clip caching
Downloaded clips are cached in `outputs/video_cache/` by URL hash. If you change search queries, clear the cache: `rm -rf outputs/video_cache/*`

---

## Config Fields That Matter Most

```python
CHANNEL_NICHE = "AI & Tech"      # Options: AI & Tech | Finance | Business | Health | History | English Learning
                                  # Changing niche auto-switches: subreddits, RSS feeds, accent colors, script angle guidance
CHANNEL_NAME = "AutoTube"        # shown in top-left watermark
SCRIPT_WORD_COUNT = 650          # ~4.5 min — don't increase beyond 800
SCRIPT_MODEL_PROVIDER            # "claude" or "gemini" — set via env var
VIDEO_BACKGROUND_MODE            # "ai_images" (V2, default) or "pexels" (V1) — set via env var / GitHub Variable
VIDEO_ANIMATION_MODE             # "ken_burns" (default), "leiapix", or "pika" — switch without code change via env var
MUSIC_ENABLED                    # "true" (default) or "false" — IMPORTANT: only use CC0 music, YouTube deducts 55% for licensed music
DARK_OVERLAY_OPACITY = 0.52      # how dark the footage overlay is (0.4–0.65)
PEXELS_CLIPS_PER_VIDEO = 6       # 1 per section — matches 6-section script (V1/pexels mode only)
```

---

## Video Animation Modes

**Default (Recommended):** Ken Burns — completely free, no API setup needed

| Mode | Approach | Cost | Speed | Quality | Fallback |
|---|---|---|---|---|---|
| **ken_burns** (default ✓) | Pollinations AI images + FFmpeg zoom/pan | FREE | 1-2 min | Good | Always available |
| **pika** (optional) | Native video from text (via fal.ai) | PAID | 5-10 min | Excellent | Falls back to Ken Burns |

**Fallback Chain (always free):**
`Ken Burns → Pexels clips → Gradient background`

**To use Pika (optional, requires payment):**
```bash
# Set in .env or GitHub Variable
VIDEO_ANIMATION_MODE=pika
FAL_API_KEY=your_paid_fal_key
```

**Note:** LeiaPix removed (requires OAuth2 client credentials). Ken Burns is the reliable default.

**How to switch:**
```bash
# Local testing
VIDEO_ANIMATION_MODE=leiapix python orchestrator.py --dry-run --topic "Test"
VIDEO_ANIMATION_MODE=pika python orchestrator.py --dry-run --topic "Test"

# GitHub Actions: set Variable VIDEO_ANIMATION_MODE to "leiapix" or "pika" (Settings → Variables)
```

**Ken Burns** (current): Uses FFmpeg zoompan with 17 animation presets (zoom, pan, drift effects). Fastest, completely free.

**LeiaPix**: Converts static images to 3D-depth animated videos. Adds parallax depth illusion. Free API, no key needed. More cinematic than Ken Burns.

**Pika**: Generates videos directly from visual_queries prompts. Best quality but limited free tier (~25 videos/month). Requires `PIKA_API_KEY` secret in GitHub.

**Caching**: All modes cache videos by hash in `outputs/video_cache/` (prefixed `pika_*`, `leiapix_*`, `fx_*`). Prefetch job builds cache over time; render job reuses.

**Fallback chain**: If active mode fails (API down, quota hit, network error) → gracefully falls back to gradient background for that section. Video continues playing with text overlays.

---

## Critical Lesson: Integration Testing Before Commit

**LESSON LEARNED (2026-04-17):** A typo in the Pika API endpoint (`queuee` instead of `queue`) went undetected during implementation and wasn't caught until videos were failing in production. This bug should have been caught immediately.

### Rule: Never commit external API integration code without testing it

Before committing ANY code that makes API calls:
1. **Verify the endpoint URL** against official API documentation — do not assume or copy blindly
2. **Test with a real API call** in dry-run mode — at least one successful request before commit
3. **Check error logs carefully** — typos in URLs are obvious in 404/403 responses
4. **Review URLs character-by-character** — `queue` vs `queuee`, `v1` vs `v2`, typos are easy to miss

### Specific to this codebase:
- **Pika endpoint** (MUST be exact): `https://api.fal.ai/v1/queue/text-to-video` 
  - NOT `queuee` (double-e typo)
  - NOT `v2` or other versions — always check fal.ai docs
- **Pollinations endpoint** (no key required): `https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&nologo=true&model=flux`
- **Supabase endpoints** (from config.SUPABASE_URL): Always use the exact URL from your Supabase project settings

### How to test before commit:
```bash
# For Pika integration:
python orchestrator.py --dry-run --topic "Test Topic" 2>&1 | grep -i "pika\|fal.ai\|error"

# Check for these patterns in logs:
# ✓ "Pika video (via fal.ai) downloaded" = working
# ✗ "403 Client Error" or "404 Client Error" = URL/auth problem
# ✗ "Pika/fal.ai video generation failed" = something is wrong
```

If you see ANY API error in logs before committing, **trace back to the endpoint URL first** — typos are the most common cause.

---

## Common Pitfalls

- **`multiply_volume` AttributeError** — use `MultiplyVolume` effect, not `.multiply_volume()` method
- **`google-generativeai` import** — wrong package; use `google-genai`
- **`python` not found on Mac** — use `.venv/bin/python3` explicitly
- **Pexels returns AI robot clips** — the `visual_queries` field in the script JSON controls this; queries should be cinematic, not topic-literal (e.g. "aerial cityscape" not "artificial intelligence")
- **Video too long** — `SCRIPT_WORD_COUNT` in config.py controls length; 650 = ~4.5 min
- **Font not found** — `video_agent.py` tries multiple system font paths; falls back to PIL default if none found; add your font path to the `candidates` list in `_load_fonts()`

---

## GitHub Actions

- **4 cron triggers**: 03:30, 06:30, 09:30, 12:30 UTC (= 09/12/15/18 IST)
- Each run: 1 video, ~20 min, then commits history files back to repo
- Manual trigger available via Actions tab with `count`, `dry_run`, `force_topic`, `model_provider` inputs
- `SCRIPT_MODEL_PROVIDER` is a GitHub **Variable** (not Secret) — changeable via UI without code push
- `VIDEO_BACKGROUND_MODE` is a GitHub **Variable** — `ai_images` (V2, default) or `pexels` (V1 fallback)
- Logs uploaded as artifact for 14 days even on failure

## Secrets required in GitHub
`ANTHROPIC_API_KEY`, `YOUTUBE_TOKEN_JSON`, `YOUTUBE_CLIENT_SECRETS`, `PEXELS_API_KEY`

**Optional (for Pika video generation mode):**
`FAL_API_KEY` — Only needed if `VIDEO_ANIMATION_MODE=pika` is set.

**To set up Pika mode:**
1. Go to https://fal.ai (free tier available)
2. Create account and sign in
3. Copy API key from dashboard
4. Add to GitHub Secrets as `FAL_API_KEY`
5. Set GitHub Variable `VIDEO_ANIMATION_MODE=pika`

**Why fal.ai?** Pika Labs officially moved to fal.ai infrastructure in 2025. This provides better reliability, official support, and proper billing.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
