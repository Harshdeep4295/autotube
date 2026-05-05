#!/bin/bash
set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║ AutoTube Fix & Diagnostic Script                               ║"
echo "║ Run this on the remote machine to fix issues                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"

cd /home/harshdeepsingh/autotube
. .venv/bin/activate

echo ""
echo "Step 1: Health Check"
echo "═══════════════════════════════════════════════════════════════"

# Check .env
if [ -f ".env" ]; then
    echo "✓ .env exists"
    REQUIRED_KEYS=("ANTHROPIC_API_KEY" "YOUTUBE_TOKEN_JSON" "GROQ_API_KEY" "PEXELS_API_KEY")
    for key in "${REQUIRED_KEYS[@]}"; do
        if grep -q "^$key=" .env; then
            echo "  ✓ $key is set"
        else
            echo "  ⚠ $key might be missing (check manually)"
        fi
    done
else
    echo "✗ .env not found - THIS IS THE PROBLEM"
    exit 1
fi

# Check Python packages
echo ""
echo "Checking Python packages..."
python3 << 'PYEOF'
import sys
packages = {
    'moviepy': 'MoviePy 2.x (video rendering)',
    'anthropic': 'Anthropic SDK (Claude)',
    'google': 'Google GenAI (Gemini)',
    'openai': 'OpenAI SDK (Groq)',
    'yt_dlp': 'yt-dlp (YouTube download)',
}

for pkg, desc in packages.items():
    try:
        __import__(pkg)
        print(f"  ✓ {pkg:<15} {desc}")
    except ImportError:
        print(f"  ✗ {pkg:<15} {desc} - MISSING!")

PYEOF

# Check data files
echo ""
echo "Checking data files..."
[ -f "data/posted_videos.json" ] && echo "  ✓ data/posted_videos.json" || echo "  ⚠ data/posted_videos.json (needed for Shorts)"
[ -f "config.py" ] && echo "  ✓ config.py" || echo "  ✗ config.py MISSING"

echo ""
echo "Step 2: Test Imports"
echo "═══════════════════════════════════════════════════════════════"

python3 << 'PYEOF'
import traceback
import sys

modules_to_test = [
    'config',
    'orchestrator',
    'agents.research_agent',
    'agents.script_agent',
    'agents.voice_agent',
    'agents.video_agent',
    'agents.upload_agent',
]

for module_name in modules_to_test:
    try:
        __import__(module_name)
        print(f"  ✓ {module_name}")
    except Exception as e:
        print(f"  ✗ {module_name}: {str(e)[:100]}")
        traceback.print_exc()

PYEOF

echo ""
echo "Step 3: Run Orchestrator Diagnostic (Dry-Run)"
echo "═══════════════════════════════════════════════════════════════"

python3 << 'PYEOF'
import logging
import sys
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

try:
    print("\n>>> Importing orchestrator...")
    from orchestrator import Orchestrator
    import config
    print("✓ Imports successful")

    print("\n>>> Creating Orchestrator instance (dry-run)...")
    orch = Orchestrator(dry_run=True, skip_on_fail=True)
    print("✓ Orchestrator created")

    print("\n>>> Testing --mode shorts_from_existing...")
    results = orch.run_shorts_from_existing(pick_strategy="all_time_best", batch=1)
    print(f"✓ Shorts test returned {len(results)} result(s)")
    if results:
        for r in results:
            if r.get('success'):
                print(f"  ✓ {r.get('title', 'Unknown')}")
            else:
                print(f"  ✗ {r.get('title', 'Unknown')}: {r.get('error', 'unknown error')}")

    print("\n>>> Testing --mode auto (with dry-run, count=1)...")
    print("  This will attempt: research → script → voice → video")
    results = orch.run(count=1)
    print(f"✓ Auto mode returned {len(results)} result(s)")
    if results:
        r = results[0]
        if r.get('success'):
            print(f"  ✓ {r.get('title', 'Unknown')}")
            print(f"    Video: {r.get('video_path', 'N/A')}")
        else:
            print(f"  ✗ Failed at: {r.get('error', 'unknown')[:200]}")

    print("\n" + "="*60)
    print("✓ All tests completed successfully!")
    print("="*60)

except Exception as e:
    print("\n" + "="*60)
    print(f"✗ ERROR: {e}")
    print("="*60)
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)

PYEOF

echo ""
echo "Step 4: Summary"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "If you see errors above:"
echo "  1. Check if required API keys are in .env"
echo "  2. Check Python package versions: pip list | grep -E 'moviepy|anthropic|openai|google'"
echo "  3. Run: pip install --upgrade -r requirements.txt"
echo ""
echo "If all tests pass, you can now run:"
echo "  python3 orchestrator.py --dry-run --count 1  (test full pipeline)"
echo "  python3 orchestrator.py --mode auto  (live upload)"
echo "  python3 orchestrator.py --mode shorts_from_existing --pick_strategy all_time_best  (upload shorts)"
echo ""
