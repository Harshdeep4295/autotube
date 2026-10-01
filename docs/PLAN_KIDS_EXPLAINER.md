# Kids track — "Explained Like You're 5"

2–3 minute animated story videos that explain one big finance or tech idea using a
kid-world analogy (a lemonade stand, pizza slices, a letter to Grandma). Same channel,
own playlist, **for all ages — not made for kids** (keeps comments + normal ads).

## How it works

```
KidsTopicAgent      headlines (BBC business/tech, The Verge, TechCrunch — KIDS_FEEDS)
                    → LLM picks the evergreen idea behind them ("rate cut" → "What is interest?")
                    → fallback: data/kids_topics.json (90 questions), finance ↔ tech alternate daily
KidsScriptAgent     plan (one analogy + concept map, props from the kit only)
                    → scenes script (catalogue below, lines + cue words)
                    → length guard (240–360 words ≈ 2–2.5 min) → checker (+1 fix round)
KidsAgent           validate/repair → voice per line (Kokoro af_heart, Piper fallback)
                    → word timings (whisper, falls back) → timeline (beats on lines / cue words)
                    → pycairo frames + ffmpeg (music bed: data/music or generated) → QA (≤ 180 s)
                    → thumbnail + SRT + contact sheet
Orchestrator        --style kids → private upload, publishAt = KIDS_PUBLISH_AT_UTC, playlist
```

**Why a story kit instead of free animation:** an LLM can't reliably draw, but it can fill
in a fixed kit. The kit is a recurring cast (Mia, Leo, Zoe + 4 friends), 36 props, and
16 scene types. Each scene type has *beats*: line 1 of a scene fires beat 1, line 2 fires
beat 2, and a `cue` word moves a beat onto that exact word. That keeps the picture matched
to the words for any topic.

**Why pycairo, not Remotion:** it renders 2 minutes in about 2 minutes on the 2-core
runner, with no browser or Node, and every scene is unit-tested in pytest. The explainer
stays on Remotion; the two styles share voice, timing, QA, upload and history code.

## Files

| File | What |
|---|---|
| `agents/kids_scene_schema.py` | Scene catalogue (props, beats, line limits) + `validate_and_repair` — single source of truth |
| `agents/kids/` | Renderer: `draw.py` primitives, `cast.py`, `props.py`, `scenes.py` (one fn per scene), `timeline.py`, `render.py`, `voice.py`, `music.py`, bundled Fredoka font (OFL) |
| `agents/kids_agent.py` | Render agent; `python -m agents.kids_agent <script.json>` renders offline |
| `agents/kids_script_agent.py` + `templates/kids_prompts.py` | Plan → script → length → checker |
| `agents/kids_topic_agent.py` + `data/kids_topics.json` | Topics; history in `data/kids_topics_history.json` |
| `.github/workflows/kids_explainer.yml` | Daily 03:47 UTC; **dry run until `KIDS_SCHEDULED_DRY_RUN=false`** |
| `tests/test_kids.py`, `tests/fixtures/kids_*.json` | Schema, timeline, every scene at every beat, agents with a fake LLM |

## Run

```bash
# Offline render of a fixture (no LLM, no upload)
python -m agents.kids_agent tests/fixtures/kids_stock_market.json --out outputs/kids_test
# Full pipeline, no upload (needs GEMINI_API_KEY or GROQ_API_KEY)
python orchestrator.py --style kids --dry-run [--topic "What is interest?"] [--script path.json]
# No Kokoro? Use Piper:  KIDS_TTS=piper PIPER_MODEL=/path/voice.onnx
```

## Settings (env / repo variables)

`KIDS_TARGET_WORDS=300` · `KIDS_MIN_SECONDS=90` · `KIDS_MAX_SECONDS=180` · `KIDS_WPM=140` ·
`KIDS_KOKORO_VOICE=af_heart` · `KIDS_KOKORO_SPEED=0.92` · `KIDS_TOPIC_MODE=mixed|feed|bank` ·
`KIDS_FEEDS` (comma list) · `KIDS_PUBLISH_AT_UTC` (e.g. `19:30`) · `KIDS_PLAYLIST` ·
`KIDS_SCHEDULED_DRY_RUN` (workflow; default `true`)

## Milestones

- [x] **M1 — Story kit + renderer.** Cast, 36 props, 16 scenes, beat/cue timeline, captions,
  thumbnail, contact sheet, QA with a 3-minute cap. Two fixtures (stock market, internet) render and pass QA.
- [x] **M2 — Script agent.** Analogy planner → scenes → length guard → checker/fix round (free LLM).
- [x] **M3 — Topics + entry point + deploy.** Headline→idea + bank, `--style kids`, config, daily workflow (dry run by default).
- [ ] **M4 — Go live.** Run the workflow manually 3–5 times, review the contact sheets, then set
  `KIDS_SCHEDULED_DRY_RUN=false` and `KIDS_PUBLISH_AT_UTC`.
- [ ] **M5 — Polish.** Vertical 9:16 cut from the same timeline (a Short ≤ 3 min), more scene types
  (`timeline`, `balance`), per-topic colour themes, analytics feedback into topic choice.

## Guardrails

No advice, no real brands, companies, people or coins, nothing scary; the checker enforces it,
and the description says "not financial advice". Uploads are private + AI-disclosed +
`selfDeclaredMadeForKids=false`. Topics are recorded only after a successful upload.
