# GCP Account Migration Guide — Complete Step-by-Step

**Goal:** Set up a new Google Cloud Platform (GCP) free trial account and switch AutoTube to use it instead of the current account (which has $270 spent).

**Time estimate:** 15-20 minutes

---

## PART 1: Create New GCP Free Trial Account

### Step 1.1: Sign in with a New Google Account

You need a **different Google account** than the one that created the original trial.

**Options:**
- Create a new Gmail: https://accounts.google.com/signup
- Use an existing Gmail that hasn't used GCP free trial
- Use a different email (Gmail, work email, etc.)

**Record the email:**
```
New GCP Account Email: ___________________________
```

### Step 1.2: Claim the $300 Free Trial

1. Go to https://cloud.google.com/free
2. Click **"Get Started for Free"**
3. Sign in with your new Google account
4. Fill out billing info (card required for verification, but won't be charged)
5. Accept the $300 free trial terms
6. You should see: **"Welcome to Google Cloud"** ✅

**Record your new Account ID:**
```
New Account ID: ___________________________
(Found in: Google Cloud Console → Top left → Billing → Account ID)
```

---

## PART 2: Create a New GCP Project

### Step 2.1: Create Project

1. Go to https://console.cloud.google.com
2. At the top, click the **Project dropdown** (next to "Google Cloud")
3. Click **"NEW PROJECT"**
4. Fill in:
   - **Project name:** `autotube-trial-2` (or any name)
   - **Organization:** (leave default or select yours)
5. Click **"CREATE"**
6. Wait 30 seconds for project to be created
7. The dropdown should now show your new project selected ✅

**Record your Project ID:**
```
Project ID: ___________________________
(Format: autotube-trial-2-abc123xyz)
(Found in: Project dropdown → Copy the ID shown under project name)
```

---

## PART 3: Enable Required APIs

You need to enable 2 APIs for Veo and GCS to work.

### Step 3.1: Enable Vertex AI API

1. In Google Cloud Console, go to **APIs & Services** (search at top)
2. Click **"+ ENABLE APIS AND SERVICES"**
3. Search for: `Vertex AI API`
4. Click on it
5. Click **"ENABLE"**
6. Wait for it to say **"API enabled"** ✅

### Step 3.2: Enable Cloud Storage API

1. Go back to **APIs & Services** → **"+ ENABLE APIS AND SERVICES"**
2. Search for: `Cloud Storage API`
3. Click on it
4. Click **"ENABLE"**
5. Wait for it to say **"API enabled"** ✅

**Verification:**
- Go to **APIs & Services** → **Enabled APIs**
- You should see both listed ✓

---

## PART 4: Create GCS Bucket

A **bucket** is where generated videos will be stored temporarily.

### Step 4.1: Create Bucket via Console

1. In Google Cloud Console, go to **Cloud Storage** (search at top)
2. Click **"CREATE BUCKET"**
3. Fill in:
   - **Name:** `autotube-veo-output-trial` (must be globally unique, lowercase, no spaces)
   - **Location type:** `Region`
   - **Location:** `us-central1` (same region as Veo)
   - **Default storage class:** `Standard`
   - **Public access prevention:** `Enforce public access prevention` (selected)
4. Click **"CREATE"**
5. Wait for bucket to be created ✅

**Record your Bucket Name:**
```
GCS Bucket Name: ___________________________
(Format: autotube-veo-output-trial)
```

### Step 4.2: Verify Bucket Created

1. Go to **Cloud Storage** → **Buckets**
2. You should see `autotube-veo-output-trial` listed ✅

---

## PART 5: Create Service Account & Generate JSON Key

A **service account** is like a "robot user" that has permissions to use Veo and GCS.

### Step 5.1: Create Service Account

1. In Google Cloud Console, go to **IAM & Admin** (search at top)
2. Click **"Service Accounts"** (left sidebar)
3. Click **"+ CREATE SERVICE ACCOUNT"**
4. Fill in:
   - **Service account name:** `autotube-veo-sa`
   - **Service account ID:** (auto-fills, looks like: `autotube-veo-sa@autotube-trial-2.iam.gserviceaccount.com`)
   - **Description:** `AutoTube Veo video generation service account`
5. Click **"CREATE AND CONTINUE"**

### Step 5.2: Grant Permissions (IAM Roles)

On the "Grant this service account access to project" page:

1. Click **"SELECT A ROLE"** dropdown
2. Search and select: **`Vertex AI User`**
3. Click **"+ ADD ANOTHER ROLE"**
4. Search and select: **`Storage Object Creator`**
5. Click **"+ ADD ANOTHER ROLE"**
6. Search and select: **`Storage Object Viewer`**

You should now have 3 roles assigned:
- ✅ Vertex AI User
- ✅ Storage Object Creator
- ✅ Storage Object Viewer

7. Click **"CONTINUE"**
8. Click **"DONE"**

### Step 5.3: Generate and Download JSON Key

1. In **IAM & Admin** → **Service Accounts**, you should see `autotube-veo-sa` listed
2. Click on it
3. Go to the **"KEYS"** tab
4. Click **"ADD KEY"** → **"Create new key"**
5. Select **"JSON"** and click **"CREATE"**
6. A JSON file will auto-download to your computer
7. **KEEP THIS FILE SAFE** — it contains your credentials

**Save the JSON key:**
```
Save the downloaded JSON file as: /tmp/autotube-veo-sa-key.json
(or any safe location you can access)
```

The JSON file looks like this (DO NOT SHARE):
```json
{
  "type": "service_account",
  "project_id": "autotube-trial-2-abc123",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "autotube-veo-sa@autotube-trial-2.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

**Record your Service Account Email:**
```
Service Account Email: ___________________________
(Format: autotube-veo-sa@autotube-trial-2.iam.gserviceaccount.com)
```

---

## PART 6: Convert JSON Key to Environment Variable Format

The JSON key needs to be converted to a **single-line string** for the `.env` file.

### Step 6.1: Extract the JSON Key Content

1. Open the JSON file you downloaded with a text editor
2. **Select ALL** (Ctrl+A or Cmd+A)
3. **Copy** the entire content

### Step 6.2: Convert to Single-Line Format

You have two options:

**Option A: Using Python (Easiest)**
```bash
python3 << 'EOF'
import json

# Read the JSON file
with open('/tmp/autotube-veo-sa-key.json', 'r') as f:
    key_dict = json.load(f)

# Convert to single-line JSON string
json_string = json.dumps(key_dict)
print(json_string)
EOF
```

Copy the output (it will be one very long line).

**Option B: Online Tool (Alternative)**
1. Go to https://jsoncrush.com/
2. Paste your JSON
3. Click "Crush"
4. Copy the output

**Record the single-line JSON:**
```
AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
(This will be a VERY long single line)
```

---

## PART 7: Update .env File (Local Development)

### Step 7.1: Open or Create `.env` File

In your project root `/Users/harshdeepsingh/Projects/git_projects/autotube/`:

1. Create or edit `.env` file
2. Find/add these three lines:

**OLD VALUES (to REPLACE):**
```bash
GCP_PROJECT_ID=old-project-id
GCP_GCS_BUCKET=autotube-veo-output
AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON={...old JSON...}
```

**NEW VALUES (use the ones you recorded):**
```bash
GCP_PROJECT_ID=autotube-trial-2-abc123
GCP_GCS_BUCKET=autotube-veo-output-trial
AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"autotube-trial-2-abc123",...}
```

### Step 7.2: Save the File

1. Save `.env`
2. Make sure it's in `.gitignore` (so secrets don't get committed)

```bash
# Verify .env is in .gitignore
grep ".env" /Users/harshdeepsingh/Projects/git_projects/autotube/.gitignore
# Should output: .env (if not, add it)
```

---

## PART 8: Update GitHub Secrets (If Using GitHub Actions)

If you deploy via GitHub Actions, update these secrets:

### Step 8.1: Go to GitHub Repository Settings

1. Go to your GitHub repo
2. **Settings** → **Secrets and variables** → **Actions**

### Step 8.2: Create/Update Secrets

**Delete old secrets (optional):**
- (Optional) Delete old `AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON` if using different name

**Create new Variables (not Secrets):**

| Name | Type | Value |
|------|------|-------|
| `GCP_PROJECT_ID` | Variable | `autotube-trial-2-abc123` |
| `GCP_GCS_BUCKET` | Variable | `autotube-veo-output-trial` |

1. Click **"New repository variable"**
2. Name: `GCP_PROJECT_ID`
3. Value: (your new project ID)
4. Click **"Add variable"**

Repeat for `GCP_GCS_BUCKET`.

**Create/Update Secret:**

| Name | Type | Value |
|------|------|-------|
| `AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON` | Secret | (entire JSON key as single line) |

1. Click **"New repository secret"**
2. Name: `AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON`
3. Value: (the full JSON from Step 6.2)
4. Click **"Add secret"**

---

## PART 9: Test the Configuration

### Step 9.1: Test Local

Run a dry-run to verify everything works:

```bash
cd /Users/harshdeepsingh/Projects/git_projects/autotube

# Test with dry-run (no upload)
python3 orchestrator.py --dry-run --topic "Test AI Topic"
```

**Expected output (look for these):**
```
✅ Submitting Veo generation: ...
✅ Generation submitted: operations/...
✅ Veo video generated: ... (.mp4, ...)
```

**If you see errors:**
- `403 Forbidden` → Check IAM roles assigned to service account
- `SERVICE_DISABLED` → Go back to Step 3 and verify APIs are enabled
- `Invalid project ID` → Check `GCP_PROJECT_ID` is correct
- `Bucket not found` → Check `GCP_GCS_BUCKET` name is exact

### Step 9.2: Check GCS Bucket

Verify videos are being uploaded to GCS:

```bash
# List bucket contents
gsutil ls gs://autotube-veo-output-trial/

# Should show something like:
# gs://autotube-veo-output-trial/veo_output/
```

---

## PART 10: Commit Code Changes (Optional)

You've already made code fixes (retry logic, visual queries). Commit those now:

```bash
cd /Users/harshdeepsingh/Projects/git_projects/autotube
git add agents/gcp_veo_agent.py agents/video_agent.py templates/prompts.py
git commit -m "fix: reduce Veo retries to 1, improve visual queries, add Ken Burns fallback"
```

---

## Summary Checklist

- [ ] Created new Google account
- [ ] Claimed $300 free trial
- [ ] Created new GCP project
- [ ] Enabled Vertex AI API
- [ ] Enabled Cloud Storage API
- [ ] Created GCS bucket
- [ ] Created service account with 3 roles
- [ ] Downloaded JSON key
- [ ] Converted JSON to single-line format
- [ ] Updated `.env` file with 3 new values
- [ ] Updated GitHub Secrets/Variables (if applicable)
- [ ] Tested with `orchestrator.py --dry-run`
- [ ] Verified videos upload to GCS bucket

---

## Quick Reference Table

| Item | Old Account | New Account |
|------|-------------|-------------|
| **Project ID** | _______ | autotube-trial-2-abc123 |
| **GCS Bucket** | autotube-veo-output | autotube-veo-output-trial |
| **Service Account** | _______ | autotube-veo-sa@autotube-trial-2.iam.gserviceaccount.com |
| **JSON Key File** | ✅ (saved) | ✅ (save new one) |
| **Budget** | $270 spent | $300 fresh ✨ |

---

## Need Help?

If you get stuck on any step:
1. Run the dry-run and copy the **exact error message**
2. Check the GCP Console for any red flags (API disabled, bucket not found, etc.)
3. Verify all 3 env vars are set correctly in `.env`:
   ```bash
   echo $GCP_PROJECT_ID
   echo $GCP_GCS_BUCKET
   echo $AI_VIDEO_GCP_SERVICE_ACCOUNT_JSON | head -c 100  # First 100 chars
   ```

---

**Last Updated:** 2026-04-23
