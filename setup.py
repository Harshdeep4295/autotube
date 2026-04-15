"""
AutoTube Setup Wizard — run this ONCE to configure everything.

Usage:
    python setup.py           → full interactive setup (.env + YouTube OAuth)
    python setup.py --auth    → YouTube OAuth only (re-run if token expires)
    python setup.py --check   → verify all credentials work
    python setup.py --music   → download free CC0 background music
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def banner(text: str) -> None:
    print(f"\n{'='*60}\n  {text}\n{'='*60}")


def ok(text: str) -> None:
    print(f"    ✓ {text}")


def warn(text: str) -> None:
    print(f"    ! {text}")


def err(text: str) -> None:
    print(f"    ✗ {text}")
    sys.exit(1)


# ── Directories ────────────────────────────────────────────────────────────────

def setup_directories() -> None:
    dirs = [
        "data", "data/music", "outputs", "outputs/videos",
        "outputs/thumbnails", "outputs/audio", "logs",
        ".github/workflows", "agents", "templates",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    Path("agents/__init__.py").touch()
    Path("templates/__init__.py").touch()
    ok("Directories created")


# ── .env file ──────────────────────────────────────────────────────────────────

def setup_env() -> None:
    banner("API Key Configuration")

    env_file = Path(".env")
    existing: dict = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

    print("\nEnter your API keys (press Enter to keep existing value):\n")

    keys = [
        ("ANTHROPIC_API_KEY",
         "Claude API key [REQUIRED]\n  Get it at: console.anthropic.com → API Keys",
         True),
        ("GEMINI_API_KEY",
         "Google Gemini API key [OPTIONAL — needed only if you switch to Gemini later]\n  Get it at: aistudio.google.com → Get API key",
         False),
        ("PEXELS_API_KEY",
         "Pexels API key [OPTIONAL — for stock photo thumbnails]\n  Get it at: pexels.com/api",
         False),
    ]

    for key, desc, required in keys:
        current = existing.get(key, "")
        masked = f"...{current[-6:]}" if len(current) > 6 else "(not set)"
        print(f"\n  {desc}")
        val = input(f"  Current: {masked}\n  New value (Enter to keep): ").strip()
        if val:
            existing[key] = val
        elif required and not current:
            warn(f"{key} not set — Claude script generation will fail. Add it later in .env")

    # Default model provider
    if "SCRIPT_MODEL_PROVIDER" not in existing:
        existing["SCRIPT_MODEL_PROVIDER"] = "claude"

    with open(".env", "w") as f:
        f.write("# AutoTube environment variables\n")
        f.write("# This file is gitignored — never commit it.\n\n")
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    ok(".env saved")
    print("\n  NOTE: For GitHub Actions, add these same keys as GitHub Secrets:")
    print("  Settings → Secrets and variables → Actions → New repository secret")


# ── YouTube OAuth ──────────────────────────────────────────────────────────────

def setup_youtube_auth() -> None:
    banner("YouTube OAuth2 Setup")

    print("""
To upload videos, you need a Google Cloud OAuth credential:

1. Go to: https://console.cloud.google.com/
2. Create a new project: "AutoTube"
3. Enable YouTube Data API v3:
   APIs & Services → Library → search "YouTube Data API v3" → Enable
4. Create OAuth credentials:
   APIs & Services → Credentials → + Create Credentials → OAuth client ID
   Application type: Desktop app → Name: "AutoTube" → Create
5. Download the JSON file → rename it to: client_secrets.json
6. Place it in this directory (same folder as this setup.py)
7. OAuth consent screen → Add test users → add your Gmail

Press Enter once client_secrets.json is in this folder…
""")
    input()

    if not Path("client_secrets.json").exists():
        err("client_secrets.json not found. Cannot continue.")

    print("\n  Opening browser for Google authorization…")
    print("  (If browser doesn't open, copy the URL shown in the terminal)\n")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secrets.json",
            scopes=[
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube",
            ],
        )
        creds = flow.run_local_server(port=0, open_browser=True)

        Path("data").mkdir(exist_ok=True)
        token_data = json.loads(creds.to_json())
        with open("data/youtube_token.json", "w") as f:
            json.dump(token_data, f, indent=2)

        ok("YouTube OAuth token saved to data/youtube_token.json")
        print("\n  IMPORTANT: Add token to GitHub Secrets for automated runs:")
        print("  Secret name: YOUTUBE_TOKEN_JSON")
        print("  Value: paste the entire contents of data/youtube_token.json")
        print("\n  Also add: YOUTUBE_CLIENT_SECRETS (contents of client_secrets.json)")

    except Exception as e:
        err(f"OAuth failed: {e}")


# ── Check credentials ──────────────────────────────────────────────────────────

def check_credentials() -> None:
    banner("Credential Check")
    from dotenv import load_dotenv
    load_dotenv()

    # Check Claude
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        warn("ANTHROPIC_API_KEY not set")
    else:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say: OK"}],
            )
            ok(f"Claude API works ({msg.content[0].text.strip()})")
        except Exception as e:
            warn(f"Claude API error: {e}")

    # Check Gemini (optional)
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content("Say: OK")
            ok(f"Gemini API works ({resp.text.strip()[:20]})")
        except Exception as e:
            warn(f"Gemini API error: {e}")
    else:
        print("    - GEMINI_API_KEY not set (optional — only needed if switching to Gemini)")

    # Check YouTube token
    if not Path("data/youtube_token.json").exists():
        warn("YouTube token not found — run: python setup.py --auth")
    else:
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            with open("data/youtube_token.json") as f:
                token_data = json.load(f)
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
            )
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                ok("YouTube token refreshed successfully")
            else:
                ok("YouTube token valid")
        except Exception as e:
            warn(f"YouTube token error: {e}")


# ── Free background music ──────────────────────────────────────────────────────

def setup_music() -> None:
    banner("Free Background Music")
    print("Downloading a sample CC0 ambient track…")
    print("(Replace with your own tracks from pixabay.com/music or freemusicarchive.org)\n")

    Path("data/music").mkdir(parents=True, exist_ok=True)
    dest = Path("data/music/ambient_01.mp3")

    if dest.exists():
        ok(f"ambient_01.mp3 already exists")
    else:
        try:
            urllib.request.urlretrieve(
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                str(dest),
            )
            ok(f"Downloaded: ambient_01.mp3")
        except Exception as e:
            warn(f"Could not download sample music: {e}")

    print("\n  Add your own CC0 music (.mp3 or .wav) to data/music/")
    print("  Sources: pixabay.com/music · freemusicarchive.org · ccmixter.org")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="AutoTube setup wizard")
    parser.add_argument("--auth",  action="store_true", help="YouTube OAuth only")
    parser.add_argument("--check", action="store_true", help="Verify all credentials")
    parser.add_argument("--music", action="store_true", help="Download free background music")
    args = parser.parse_args()

    if args.auth:
        setup_youtube_auth()
        return
    if args.check:
        check_credentials()
        return
    if args.music:
        setup_music()
        return

    # Full setup
    banner("AutoTube Full Setup")
    setup_directories()
    setup_env()
    setup_music()
    setup_youtube_auth()

    banner("Setup Complete!")
    print("\nNext steps:")
    print("  1. pip install -r requirements.txt")
    print("  2. Test locally (no upload):")
    print('     python orchestrator.py --dry-run --topic "Artificial Intelligence"')
    print("  3. Check outputs/ folder for the generated video")
    print("  4. Push to GitHub + add Secrets → pipeline runs daily at 7:30 AM IST")
    print()


if __name__ == "__main__":
    main()
