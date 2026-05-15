#!/usr/bin/env python3
"""
Generate YouTube Token JSON for GitHub Secrets

Run this script to authorize YouTube upload access and generate YOUTUBE_TOKEN_JSON
Uses YOUTUBE_CLIENT_SECRETS from .env file
"""

import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
except ImportError:
    print("❌ Missing required packages. Install with:")
    print("   pip install google-auth-oauthlib google-auth-httplib2 python-dotenv")
    sys.exit(1)

# Configuration
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

def main():
    print("🎬 YouTube Token Generator")
    print("=" * 50)

    # Load .env file
    load_dotenv()
    client_secrets_json = os.getenv("YOUTUBE_CLIENT_SECRETS")

    if not client_secrets_json:
        print("❌ YOUTUBE_CLIENT_SECRETS not found in .env file")
        print("   Make sure your .env has: YOUTUBE_CLIENT_SECRETS={...json...}")
        sys.exit(1)

    print("\n✅ Using YOUTUBE_CLIENT_SECRETS from .env")
    print("\n🌐 Opening browser for authorization...")
    print("   (If browser doesn't open, copy the URL shown below)\n")

    try:
        # Parse client secrets JSON from env
        try:
            client_secrets_dict = json.loads(client_secrets_json)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in YOUTUBE_CLIENT_SECRETS: {e}")
            sys.exit(1)

        # Create OAuth2 flow from client secrets dict
        flow = InstalledAppFlow.from_client_config(
            client_secrets_dict,
            SCOPES
        )

        # Run local server to capture auth code
        creds = flow.run_local_server(port=0)

        # Extract token info
        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
            "type": "authorized_user"
        }

        # Generate JSON string
        json_output = json.dumps(token_data)

        print("\n" + "=" * 50)
        print("✅ Authorization successful!")
        print("=" * 50)
        print("\n📋 Copy this entire token and add to GitHub Secrets:\n")
        print(json_output)
        print("\n" + "=" * 50)
        print("\n📝 Next steps:")
        print("   1. Copy the token above")
        print("   2. Go to GitHub repo → Settings → Secrets and variables → Actions")
        print("   3. Click 'New repository secret'")
        print("   4. Name: YOUTUBE_TOKEN_JSON")
        print("   5. Value: (paste the token above)")
        print("   6. Click 'Add secret'")
        print("   7. Or save locally with 'y' below\n")

        # Optional: save to file
        save_local = input("💾 Save to local file? (y/n): ").strip().lower()
        if save_local == 'y':
            local_path = "data/youtube_token.json"
            os.makedirs("data", exist_ok=True)
            with open(local_path, 'w') as f:
                json.dump(token_data, f, indent=2)
            print(f"✅ Saved to: {local_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
