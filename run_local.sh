#!/usr/bin/env bash
# run_local.sh — Run AutoTube pipeline from your local machine.
#
# Usage:
#   ./run_local.sh                              → dry-run, 1 video, auto research
#   ./run_local.sh --upload                     → live upload to YouTube
#   ./run_local.sh --topic "AI news"            → force a specific topic (still dry-run)
#   ./run_local.sh --upload --topic "AI news"   → force topic + live upload
#   ./run_local.sh --upload --count 2           → upload 2 videos
#   ./run_local.sh --gemini                     → use Gemini instead of Claude (dry-run)
#
# Requirements:
#   - .env file with ANTHROPIC_API_KEY (run: python setup.py to create it)
#   - data/youtube_token.json for --upload (run: python setup.py --auth)
#   - pip install -r requirements.txt
#   - brew install ffmpeg (Mac) or sudo apt install ffmpeg (Linux)

set -e
cd "$(dirname "$0")"

# ── Load .env ──────────────────────────────────────────────────────────────────
if [ -f .env ]; then
  # Export vars from .env (skip comments and empty lines)
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# ── Activate virtualenv if present ────────────────────────────────────────────
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -d "venv" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

# ── Parse arguments ────────────────────────────────────────────────────────────
DRY_RUN="--dry-run"
EXTRA_ARGS=""

for arg in "$@"; do
  case "$arg" in
    --upload)
      DRY_RUN=""
      ;;
    --gemini)
      export SCRIPT_MODEL_PROVIDER="gemini"
      ;;
    --claude)
      export SCRIPT_MODEL_PROVIDER="claude"
      ;;
    *)
      EXTRA_ARGS="$EXTRA_ARGS $arg"
      ;;
  esac
done

# Default provider if not set
PROVIDER="${SCRIPT_MODEL_PROVIDER:-claude}"

# ── Banner ─────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║         AutoTube Local Runner            ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Provider : ${PROVIDER}"
if [ -z "$DRY_RUN" ]; then
  echo "║  Mode     : LIVE UPLOAD"
else
  echo "║  Mode     : DRY RUN (no upload)"
fi
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Run pipeline ───────────────────────────────────────────────────────────────
# shellcheck disable=SC2086
python orchestrator.py $DRY_RUN $EXTRA_ARGS

echo ""
if [ -z "$DRY_RUN" ]; then
  echo "Done! Check YouTube Studio for your uploaded video."
else
  echo "Done! Check the outputs/ folder for your local video."
  echo "  open outputs/   (Mac — opens in Finder)"
fi
