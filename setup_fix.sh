#!/bin/bash
set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║ AutoTube Setup & Dependency Fix                                ║"
echo "║ Fixes common issues: missing packages, Python version, etc.    ║"
echo "╚════════════════════════════════════════════════════════════════╝"

cd /home/harshdeepsingh/autotube

# Step 1: Upgrade Python (if needed)
echo ""
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Current: Python $PYTHON_VERSION"
if [[ "$PYTHON_VERSION" == "3.10"* ]]; then
    echo "⚠ Python 3.10 will reach EOL 2026-10-04"
    echo "  (Google will drop support in google.api_core)"
    echo "  Consider upgrading to Python 3.11+ for long-term support"
fi

# Step 2: Activate venv
echo ""
echo "Activating virtual environment..."
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi
. .venv/bin/activate

# Step 3: Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Step 4: Install/upgrade requirements
echo ""
echo "Installing dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    # First, ensure key packages are present
    pip install --upgrade \
        moviepy==2.2.1 \
        anthropic \
        "google-genai" \
        openai \
        yt-dlp \
        pexels-api \
        python-dotenv \
        requests \
        google-cloud-storage \
        google-cloud-aiplatform

    # Then install full requirements
    pip install --upgrade -r requirements.txt
else
    echo "✗ requirements.txt not found"
    exit 1
fi

# Step 5: Check critical packages
echo ""
echo "Verifying critical packages..."
python3 << 'PYEOF'
import subprocess
import sys

packages = {
    'moviepy': '2.2',
    'anthropic': 'latest',
    'openai': 'latest',
    'google-genai': 'latest',
    'yt-dlp': 'latest',
}

for pkg, version in packages.items():
    try:
        result = subprocess.run(
            ['pip', 'show', pkg],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = [l for l in result.stdout.split('\n') if l.startswith('Version:')]
            if version_line:
                installed = version_line[0].split(': ')[1]
                print(f"  ✓ {pkg:<20} {installed}")
        else:
            print(f"  ✗ {pkg:<20} NOT INSTALLED")
    except Exception as e:
        print(f"  ? {pkg:<20} Error checking: {e}")

PYEOF

# Step 6: Create/check data directory
echo ""
echo "Checking data directory..."
mkdir -p data
if [ -f "data/posted_videos.json" ]; then
    echo "  ✓ data/posted_videos.json exists"
else
    echo "  ⚠ data/posted_videos.json not found (needed for Shorts mode)"
    echo "    Creating empty file..."
    echo "[]" > data/posted_videos.json
fi

if [ -f "data/topics_history.json" ]; then
    echo "  ✓ data/topics_history.json exists"
else
    echo "  Creating data/topics_history.json..."
    echo "[]" > data/topics_history.json
fi

# Step 7: Check .env
echo ""
echo "Checking .env configuration..."
if [ -f ".env" ]; then
    echo "  ✓ .env file exists"

    # Check for required keys
    REQUIRED_KEYS=("ANTHROPIC_API_KEY" "YOUTUBE_TOKEN_JSON")
    MISSING_KEYS=()

    for key in "${REQUIRED_KEYS[@]}"; do
        if grep -q "^${key}=" .env; then
            echo "    ✓ $key is set"
        else
            echo "    ✗ $key is MISSING"
            MISSING_KEYS+=("$key")
        fi
    done

    if [ ${#MISSING_KEYS[@]} -gt 0 ]; then
        echo ""
        echo "  ⚠ Missing required keys in .env:"
        for key in "${MISSING_KEYS[@]}"; do
            echo "    - $key"
        done
        echo ""
        echo "  Add these to .env before running orchestrator.py"
    fi
else
    echo "  ✗ .env file not found!"
    echo "  Create .env with required API keys:"
    echo "    ANTHROPIC_API_KEY=sk-..."
    echo "    YOUTUBE_TOKEN_JSON={...}"
    echo "    GROQ_API_KEY=gsk-... (optional)"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║ Setup complete!                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Verify .env has all required API keys"
echo "  2. Run: bash fix_and_diagnose.sh"
echo "  3. If diagnostics pass, run: python3 orchestrator.py --dry-run"
echo ""
