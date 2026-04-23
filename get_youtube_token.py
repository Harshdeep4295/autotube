import json
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]

# Try to load OAuth credentials from client_secrets.json
client_secrets_path = Path("client_secrets.json")

if not client_secrets_path.exists():
    print("❌ Error: client_secrets.json not found!")
    print("Please create it with your OAuth Client ID and Secret")
    exit(1)

# Load credentials from file
with open(client_secrets_path) as f:
    config = json.load(f)

# Create OAuth flow
flow = InstalledAppFlow.from_client_config(
    config,
    scopes=SCOPES
)

# Get credentials (opens browser automatically)
creds = flow.run_local_server(port=8080, open_browser=True)

# Extract and save refresh token
token_data = {
    "access_token": creds.token,
    "refresh_token": creds.refresh_token,
    "scope": " ".join(SCOPES),
    "token_type": "Bearer",
    "expires_in": 3599
}

# Save to data/youtube_token.json
import os
os.makedirs("data", exist_ok=True)
with open("data/youtube_token.json", "w") as f:
    json.dump(token_data, f, indent=2)

print("✅ Token saved to data/youtube_token.json")
print(json.dumps(token_data, indent=2))
