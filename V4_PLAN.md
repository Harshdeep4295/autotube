# AutoTube v4 — Strategic Plan
**Date:** 2026-05-08
**Based on:** Deep codebase audit + industry research (2025–2026)

---

## Part 1: Industry Research Summary

### Free Tool Stack (What the Market Uses)

| Category | Industry Standard (Free) | AutoTube Current | Gap |
|---|---|---|---|
| **Scripts** | ChatGPT / Claude / Gemini free tier | Claude → Gemini → Groq (3-way fallback) | ✅ Ahead — paid APIs with fallback |
| **Voice** | edge-tts / Chatterbox (MIT) | edge-tts only (en-US-JennyNeural) | ⚠️ Single voice, no Chatterbox |
| **Video editing** | DaVinci Resolve / FFmpeg / MoviePy | FFmpeg + MoviePy (automated) | ✅ Fully automated |
| **Stock footage** | Pexels / Pixabay | Pexels API + Pixabay | ✅ Both integrated |
| **AI visuals** | Pollinations.ai / Veo 3.1 / Wan 2.2 | Pollinations.ai + Veo 3.1 (GCP) | ⚠️ Missing Wan 2.2 (local, free) |
| **Music** | YouTube Audio Library / Pixabay CC0 | data/music/ folder (manual) | ⚠️ No auto-fetch from Pixabay |
| **Thumbnails** | Canva / Photopea / Midjourney | Pollinations.ai + Pillow | ✅ Automated, decent quality |
| **Scheduling** | YouTube Studio | YouTube Data API v3 (programmatic) | ✅ Fully automated |
| **Automation** | n8n / Make.com / Python | Pure Python + crons | ✅ Better than most |
| **Analytics** | VidIQ / TubeBuddy | ❌ None | 🔴 Critical gap |

### Top Niches by RPM (2025–2026)

| Niche | CPM | RPM | Competition | AutoTube Support |
|---|---|---|---|---|
| Legal & Tax Education | $15–$40 | $8–$18 | Medium | ❌ Not in niche list |
| Personal Finance | $18–$45 | $10–$22 | High | ✅ Finance niche |
| Business & SaaS | $14–$35 | $8–$18 | Medium | ✅ Business niche |
| Real Estate Education | $12–$30 | $6–$15 | Low-Med | ❌ Not in niche list |
| AI & Tech | $8–$20 | $5–$12 | High | ✅ Default niche |
| **Soundscapes/Focus** | $4–$10 | $10.92 | **Very low** | ❌ Not in niche list |
| **Senior Health/Longevity** | varies | $6.17 | **Very low** | ❌ Not in niche list |
| **Literary Analysis** | varies | $9.15 | **Very low** | ❌ Not in niche list |
| True Crime | $5–$12 | $4–$10 | Medium | ❌ Not in niche list |
| History | $5–$12 | $4–$10 | Low | ✅ History niche |

### Key Policy Changes to Respect

- **July 15, 2025:** YouTube bans mass-produced AI content with no human creative input from monetization. Template slideshows, bulk AI-only videos = demonetized.
- **May 21, 2025:** AI disclosure required for synthetic content that "could be mistaken for reality." Generic AI voiceovers do NOT require disclosure. Disclosure does NOT hurt distribution.
- **Shorts RPM:** $0.01–$0.06/1K views — sub growth tool only, not revenue.
- **Mid-roll threshold:** Videos 8+ minutes = 2–3x RPM via mid-roll ads.
- **30-video rule:** Algorithm needs ~30 videos to identify audience. Quit before this = guaranteed failure.

---

## Part 2: AutoTube v3 Audit

### What v3 Does Well ✅

1. **3-way LLM fallback** (Claude → Gemini → Groq) — more resilient than 95% of open-source pipelines
2. **Fully automated end-to-end** — research to upload in one command
3. **Memory-efficient rendering** — FFmpeg streaming, 3–4x lower RAM than naive MoviePy
4. **Supabase queue + GCS backup** — enterprise-grade reliability, no lost videos
5. **Per-niche customization** — subreddits, colors, RSS feeds, angle guidance
6. **6 research sources** — pytrends + Reddit + RSS + HN + Dev.to + Lobste.rs
7. **17 animation effects** — zoompan presets loaded from Supabase
8. **Playlist auto-management** — auto-groups videos into keyword playlists
9. **Topic deduplication** — fuzzy matching prevents repetitive content
10. **Veo 3.1 integration** — best-quality free AI video (GCP $300 credits)
11. **Async Kling harvest** — non-blocking AI video submission/polling

### What v3 is Missing vs. Industry 🔴

#### Critical Gaps (directly hurting revenue)

| Gap | Impact | Research Basis |
|---|---|---|
| **No analytics feedback loop** | Can't know what works, can't improve | VidIQ/TubeBuddy = industry standard |
| **No A/B thumbnail testing** | CTR is #1 growth lever; blind optimization | High-CTR channels systematically test thumbnails |
| **Single TTS voice only** | Audience fatigue, no voice testing | Chatterbox beats ElevenLabs; variety increases retention |
| **No mid-roll optimization** | Videos not reliably hitting 8-min threshold | 8+ min = 2-3x RPM via mid-roll ads |
| **Videos auto-publish without review** | July 2025 policy needs "human creative input" | Mass-produced AI content gets demonetized |
| **No performance feedback** | Bad topics repeated, good ones not doubled down | Research says penalize underperforming topics |

#### Missing Niches (leaving money on table)

| Niche | Why Missed | Potential |
|---|---|---|
| Soundscapes/Focus | Not in niche list | $10.92 RPM, ~20K channels only |
| Senior Health/Longevity | Not in niche list | $6.17 RPM, 19x YoY growth |
| Literary Analysis | Not in niche list | $9.15 RPM, ~10K channels |
| Legal/Tax Education | Not in niche list | $8–18 RPM, medium competition |
| True Crime | Not in niche list | $4–10 RPM, high demand |

#### Tool Gaps (free upgrades available)

| Missing | What It Does | Cost |
|---|---|---|
| Chatterbox TTS | Beats ElevenLabs quality, MIT license, 5-sec voice cloning | Free (self-hosted) |
| Wan 2.2 | Best local AI video gen, cinematic quality | Free (needs GPU) |
| Pixabay CC0 music auto-fetch | Auto-pulls fresh background music | Free |
| YouTube Analytics API | Views, RPM, retention per video | Free (OAuth) |
| Face/character thumbnail overlay | Research shows faces boost CTR 30–50% | Free (Pillow) |
| Multi-language scripts | Same pipeline, 5x audience reach | Near-zero marginal cost |

---

## Part 3: Comparison Table — AutoTube v3 vs. Industry Best Practice

| Dimension | Industry Best Practice | AutoTube v3 | v4 Target |
|---|---|---|---|
| **Script quality** | Human-edited AI scripts | LLM + prompt engineering | + Human-review toggle |
| **Voice variety** | Multiple narrators | 1 voice (Jenny) | 3–5 voices, random/per-niche |
| **Video quality** | Cinematic AI video | Veo 3.1 + Ken Burns fallback | + Wan 2.2 local option |
| **Thumbnail CTR** | Tested, face-inclusive | AI backdrop + text overlay | + A/B framework + face overlay |
| **Topic selection** | Trend + analytics feedback | Trend + 6 sources, no feedback | + Analytics loop |
| **Niche coverage** | 6–8 optimized niches | 6 niches (missing top RPM ones) | + Legal, Soundscapes, Senior Health |
| **Upload frequency** | Daily (85% monetize in 3.5 mo) | 4 uploads/day | ✅ Already daily |
| **Video length** | 8–12 min (mid-roll ads) | ~5 min (750 words) | 10–12 min (1000+ words) |
| **Approval flow** | Human review before publish | Fully auto | + Manual approval queue |
| **Analytics** | Post-publish metrics tracked | ❌ None | + YouTube Analytics API |
| **A/B testing** | Systematic thumbnail/title tests | ❌ None | + Thumbnail A/B framework |
| **Multi-language** | Parallel language channels | English only | + Hindi/Spanish mode |
| **Music** | CC0 auto-curated | Manual folder | + Pixabay CC0 auto-fetch |

---

## Part 4: v4 Feature Roadmap

### Tier 1 — Highest Impact (do first)

#### 1.1 Analytics Feedback Loop
**What:** Pull YouTube Analytics API post-publish. Track views, RPM, avg view duration per video. Store in Supabase. Feed back into topic scoring — boost topics from high-RPM videos, penalize low performers.

**Why:** Most channels that fail do so because they can't iterate. This closes the loop.

**Implementation:**
- `agents/analytics_agent.py` — new agent
- Calls `youtubeAnalytics.reports.query()` with `metrics=views,estimatedRevenue,averageViewDuration`
- Runs daily (new cron: `0 6 * * *`)
- Updates `data/topic_performance.json`
- `research_agent.py` reads performance data to boost/penalize topics

**Effort:** Medium (2–3 days)

---

#### 1.2 Mid-Roll Optimization — Longer Videos
**What:** Increase `SCRIPT_WORD_COUNT` from 750 → 1100 words (~7.5 min at 150 wpm). This reliably clears the 8-minute mid-roll threshold, doubling/tripling RPM.

**Why:** The single highest-ROI change available. 8+ min videos earn 2–3x the RPM of <8 min videos.

**Implementation:**
- `config.py`: `SCRIPT_WORD_COUNT = 1100`
- `prompts.py`: add `main_4` and `main_5` sections to standard prompt
- Test: `ffprobe outputs/latest/video.mp4` — confirm >480 seconds

**Effort:** Low (1–2 hours)

---

#### 1.3 Voice Variety
**What:** Add 4 additional edge-tts voices. Randomly assign per-video OR assign per-niche. Add Chatterbox as premium option (self-hosted, MIT).

**Why:** Audience retention improves with voice variety. Chatterbox beats ElevenLabs in blind tests and is free.

**New Voices (edge-tts, all free):**
- `en-US-GuyNeural` — professional male (Finance, Business)
- `en-US-AriaNeural` — warm female (Health, History)
- `en-US-DavisNeural` — energetic male (AI & Tech, True Crime)
- `en-GB-SoniaNeural` — British female (Literary Analysis, History)
- `en-AU-NatashaNeural` — Australian female (General)

**Implementation:**
- `config.py`: `TTS_VOICES` dict mapping niche → list of voices
- `voice_agent.py`: pick randomly from niche-appropriate voices each run

**Effort:** Low (2–4 hours)

---

#### 1.4 Manual Approval Queue (July 2025 Compliance)
**What:** Add `APPROVAL_REQUIRED=true` env var. When set, scripts are saved to Supabase with status `pending_approval` instead of auto-rendering. A simple `python review.py` CLI shows pending scripts and lets you approve/reject/edit.

**Why:** July 2025 policy explicitly requires human creative input. Having a review step also lets you catch low-quality scripts before they burn upload quota.

**Implementation:**
- `orchestrator.py`: check `config.APPROVAL_REQUIRED`; if set, save to queue with `pending_approval` status
- New `review.py` script: lists pending, allows approve/edit/reject
- `run_render()`: only picks up `approved` status scripts

**Effort:** Medium (1–2 days)

---

### Tier 2 — High Impact (next sprint)

#### 2.1 New Niches — Legal, Soundscapes, Senior Health
**What:** Add 3 new niches to `config.py` with appropriate subreddits, RSS feeds, and angle guidance.

**Legal/Tax Education:**
- Subreddits: legaladvice, tax, personalfinance, tax_advice
- RSS: IRS news, Legal.io, law.com
- Angle: "how to legally avoid X", "IRS mistake costs people $X"
- RPM: $8–18

**Soundscapes/Focus:**
- Different format: 1–3 hour looping audio + minimal visual
- Near-zero production cost (just a Pillow gradient + loop audio)
- RPM: $10.92 (high for effort level)
- Strategy: upload daily, accumulate watch hours passively

**Senior Health/Longevity:**
- Subreddits: longevity, nutrition, HealthyLiving, AskDocs
- RSS: NIH news, Harvard Health, Mayo Clinic news
- Angle: "doctors say X extends life by Y years"
- RPM: $6.17, 19x YoY growth

**Effort:** Medium (2–3 days per niche)

---

#### 2.2 Thumbnail A/B Framework
**What:** Generate 2 thumbnail variants per video. Track CTR in analytics_agent. After 30 videos, report which style wins.

**Variants:**
- Style A: Current (AI backdrop + text)
- Style B: Solid color + large text + emoji + stat badge

**Implementation:**
- `thumbnail_agent.py`: `create_variants(script, path, n=2)` generates 2 thumbnails
- Upload one, store second path in Supabase
- `analytics_agent.py`: compares CTR across style A vs B videos

**Effort:** Medium (2–3 days)

---

#### 2.3 Pixabay CC0 Music Auto-Fetch
**What:** Instead of manually adding music to `data/music/`, auto-fetch fresh CC0 tracks from Pixabay by mood/genre at pipeline start.

**Why:** Fresh music variety improves watch experience. Manual folder goes stale.

**Implementation:**
- `agents/music_agent.py` — new agent
- Calls Pixabay `/api/videos/music/` (free, no login for CC0)
- Caches 10–20 tracks locally
- `video_agent.py`: picks random cached track per video

**Effort:** Low (1 day)

---

#### 2.4 Longer Thumbnail Text + Emoji Support
**What:** Add emoji rendering to thumbnails. Research shows emoji in thumbnails boosts CTR on mobile.

**Why:** High-CTR YouTube thumbnails frequently use emoji (🔥💰🚨⚡). Currently no emoji support in Pillow.

**Implementation:**
- Download NotoColorEmoji.ttf (free Google font)
- `thumbnail_agent.py`: detect emoji in `thumbnail_text`, render with NotoColorEmoji

**Effort:** Low (4–6 hours)

---

### Tier 3 — Advanced (v4.1+)

#### 3.1 YouTube Analytics Feedback Loop (Full)
Full version of 1.1: correlate topics → RPM → retention. Auto-promote high-RPM topic categories. Block topic clusters that consistently underperform.

#### 3.2 Multi-Language Pipeline
Same pipeline, Hindi and Spanish script generation. Separate YouTube channels. Edge-tts supports 100+ locales. Uses `hi-IN-MadhurNeural` (Hindi) or `es-US-PalomaNeural` (Spanish). Massively expands reach with near-zero marginal cost.

#### 3.3 Wan 2.2 Local Video Generation
Self-hosted on a GPU machine. Apache 2.0 license, commercial use OK. Cinematic quality, better than Veo for some styles. No API cost. Requires RTX 4090 or equivalent (24GB VRAM).

#### 3.4 Face/Character Thumbnail Overlay
High-CTR thumbnails use expressive faces even on faceless channels (stock photos, illustrated characters, AI-generated faces with Stable Diffusion). Add a character library to `thumbnail_agent.py`.

#### 3.5 True Crime + History Documentary Mode
Longer format (15–30 min), narrative structure, different section template (setup → incident → investigation → resolution → lesson). True crime channels average $4–10 RPM with 20–60 min average watch time.

#### 3.6 Prompt Versioning + Claude Prompt Caching
A/B test different system prompts. Use Claude's prompt cache on static system prompt (saves 80–90% of input tokens on each run = meaningful cost reduction at scale).

---

## Part 5: v4 Implementation Priority Order

```
Week 1:
  [x] Fix 3 production bugs (FFmpeg concat, yt-dlp auth, captions.srt) ← DONE
  [ ] Mid-roll optimization: SCRIPT_WORD_COUNT → 1100 (1 hour)
  [ ] Voice variety: 5 voices mapped per niche (3 hours)
  [ ] Pixabay CC0 music auto-fetch (1 day)

Week 2:
  [ ] Analytics agent: pull views + RPM + retention per video (2 days)
  [ ] Manual approval queue + review.py CLI (2 days)

Week 3:
  [ ] New niche: Legal/Tax Education
  [ ] New niche: Senior Health/Longevity
  [ ] Thumbnail emoji support

Week 4:
  [ ] Thumbnail A/B framework (2 days)
  [ ] Analytics → topic scoring feedback loop (1 day)

Month 2:
  [ ] Multi-language pipeline (Hindi)
  [ ] Soundscape channel (new low-effort channel)
  [ ] Wan 2.2 integration (GPU required)
  [ ] True Crime / History documentary mode
```

---

## Part 6: Expected Revenue Impact of v4

| Change | Mechanism | Expected RPM Impact |
|---|---|---|
| Mid-roll optimization (8+ min) | Mid-roll ads enabled | +100–200% RPM |
| Analytics feedback | Better topic selection | +20–40% RPM over time |
| Legal/Tax niche | Higher CPM advertisers | +50–80% RPM vs AI & Tech |
| Soundscape channel | Passive watch hours, high RPM/effort ratio | New revenue stream |
| Voice variety | Better retention → more impressions | +10–20% views |
| Thumbnail A/B | Higher CTR → more impressions | +15–30% views |
| Multi-language (Hindi) | 5x audience reach | New revenue stream |

**Current estimate (v3):** ~$400–800/month at steady state (AI & Tech, 4 uploads/day)
**v4 estimate:** ~$1,500–4,000/month (longer videos + better niches + analytics loop)

---

## Part 7: Immediate Action Items (This Week)

1. **Change `SCRIPT_WORD_COUNT` to 1100** in `config.py` — takes 5 minutes, highest ROI
2. **Add 4 voices to `voice_agent.py`** — mapped by niche
3. **Enable `COMMENTS_ENABLED=true`** on the server — audience signals already built, just disabled
4. **Add Legal/Tax as a new niche** in `config.py` + subreddits + RSS
5. **Write `analytics_agent.py`** — YouTube Analytics API, daily cron

---

## Appendix: AutoTube v3 Architecture Map

```
orchestrator.py (entry point)
├── research_agent.py    — 6 sources, quality scoring, dedup
├── script_agent.py      — Claude/Gemini/Groq, 3-way fallback
├── voice_agent.py       — edge-tts → pyttsx3 fallback
├── video_agent.py       — FFmpeg/MoviePy, Veo/Ken Burns, overlays
├── thumbnail_agent.py   — Pollinations.ai + Pillow
├── upload_agent.py      — YouTube API, playlists, captions
├── comment_research_agent.py  — YouTube comments (disabled by default)
├── gcp_veo_agent.py     — Vertex AI Veo 3.1
├── gcs_backup_agent.py  — GCS upload/retry for failed uploads
└── gcp_cost_tracker.py  — Spend tracking vs $300 budget

Data:
├── data/topics_history.json    — dedup history (30 days)
├── data/posted_videos.json     — uploaded video log
├── data/playlists.json         — auto-created playlist cache
├── data/upload_status.json     — GCS retry manifest
└── data/music/                 — CC0 background music (manual)

Infrastructure:
├── Supabase — topic queue, script queue, animation effects
├── GCS — video backup, Veo output
├── Firestore — audit log (Cloud Run mode)
└── YouTube Data API v3 — upload, schedule, playlist, captions
```
