# AutoTube

Automated, free-only pipeline for the YouTube channel **Run It Local**. It researches a topic,
writes a script with a free-tier LLM, voices it with Kokoro, renders an animated video, checks it,
and uploads it as a private video that YouTube publishes later in the day.

| Style | Video | Renderer | Workflow |
|---|---|---|---|
| `explainer` (default) | 8+ minute animated explainer on a practical-AI topic | Remotion (`video/explainer/`) | `.github/workflows/explainer.yml`, daily 03:17 UTC |
| `kids` | 2–3 minute "Explained Like You're 5" story video | pycairo (`agents/kids/`) | `.github/workflows/kids_explainer.yml`, daily 03:47 UTC |

Everything runs on free tiers and open-source software: Gemini and Groq free tiers, Kokoro TTS,
faster-whisper, Remotion, FFmpeg and the standard GitHub Actions runner.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
sudo apt-get install ffmpeg fonts-liberation fontconfig libcairo2-dev pkg-config
(cd video/explainer && npm ci && npx remotion browser ensure)     # explainer only

.venv/bin/python -m pytest -q                                      # tests

# Render a fixture script offline (no LLM, no upload)
.venv/bin/python -m agents.kids_agent tests/fixtures/kids_stock_market.json --out outputs/kids_test
.venv/bin/python -m agents.explainer_agent tests/fixtures/explainer_script.json --out outputs/test

# Full pipeline without uploading (needs GEMINI_API_KEY or GROQ_API_KEY in .env)
.venv/bin/python orchestrator.py --dry-run
.venv/bin/python orchestrator.py --style kids --dry-run
```

Running `orchestrator.py` without `--dry-run` uploads to the channel.

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — how the repo is laid out, rules, settings, current status
- [`docs/RUNBOOK_EXPLAINER.md`](docs/RUNBOOK_EXPLAINER.md) — setup, credentials, running, troubleshooting
- [`docs/PLAN_EXPLAINER_AND_AI_VIDEO.md`](docs/PLAN_EXPLAINER_AND_AI_VIDEO.md) — explainer design and the AI-clip phase
- [`docs/PLAN_KIDS_EXPLAINER.md`](docs/PLAN_KIDS_EXPLAINER.md) — kids track design and milestones
- [`docs/GROWTH_PLAN.md`](docs/GROWTH_PLAN.md) — what to fix and build next to grow the channel
- [`docs/CHANNEL_SETUP.md`](docs/CHANNEL_SETUP.md) — channel identity and brand files
