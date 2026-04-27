# GitHub Action → GCP VM Code Deployment

Deploy latest AutoTube code to your GCP VM via GitHub Actions on every push to `main` branch.

---

## Prerequisites (What You Need to Provide)

Before setting up the GitHub Action, gather this information:

```
VM_IP               = [Your GCP VM Public IP]
VM_SSH_USER         = [SSH username: root, ubuntu, admin, etc.]
VM_DEPLOYMENT_PATH  = [Path where code lives: /root/autotube or /home/user/autotube]
VM_SSH_PRIVATE_KEY  = [Your SSH private key - will be stored as GitHub Secret]
```

---

## Step 1: Generate SSH Key (If You Don't Have One)

Run on your **local machine** (or VM):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/autotube_github -C "github-actions-autotube"
# Press Enter twice (no passphrase)
```

This creates:
- `~/.ssh/autotube_github` (PRIVATE KEY — secret)
- `~/.ssh/autotube_github.pub` (PUBLIC KEY — goes on VM)

---

## Step 2: Add Public Key to VM

Run on your **GCP VM**:

```bash
# Option A: If you still have local access to VM
mkdir -p ~/.ssh
cat >> ~/.ssh/authorized_keys << 'EOF'
[PASTE_CONTENTS_OF_autotube_github.pub_HERE]
EOF
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh

# Option B: Use GCP Console
# Compute Engine → VM Instances → [your-vm] → Edit → SSH Keys → Add Item
# Paste the public key there
```

---

## Step 3: Add GitHub Secrets

Go to: **GitHub Repo → Settings → Secrets and Variables → Actions → New Repository Secret**

Add these 3 secrets:

| Secret Name | Value |
|-------------|-------|
| `GCP_VM_IP` | Your VM's public IP (e.g., `35.192.123.45`) |
| `GCP_VM_SSH_USER` | SSH username (e.g., `root` or `ubuntu`) |
| `GCP_VM_SSH_KEY` | Full contents of `~/.ssh/autotube_github` (private key) |
| `GCP_VM_DEPLOY_PATH` | Deployment path (e.g., `/root/autotube`) |

**To get private key content:**
```bash
cat ~/.ssh/autotube_github
# Copy entire output (including -----BEGIN..., -----END...)
```

---

## Step 4: GitHub Action Workflow

The workflow file will be created automatically at:
```
.github/workflows/deploy-to-gcp-vm.yml
```

**What it does on every push to `main`:**
1. Checkout latest code
2. SSH into GCP VM
3. Pull latest changes (or clone if first time)
4. Install/update dependencies
5. Restart pipeline services (if configured)

**Deployment flow:**
```
User pushes to main
    ↓
GitHub Action triggers
    ↓
SSH into VM
    ↓
git pull origin main (or git clone if new)
    ↓
Update .env files if needed
    ↓
Installation complete
    ↓
Cron jobs pick up new code on next run
```

---

## Step 5: Verify Deployment

After first push:

**Check GitHub Actions:**
- Go to repo → Actions tab
- Look for workflow: "Deploy to GCP VM"
- Check logs for "✅ Deployment successful"

**Check on GCP VM:**
```bash
ssh -i ~/.ssh/autotube_github [user]@[VM_IP]

# Check if code was deployed
ls -la [DEPLOYMENT_PATH]/
git -C [DEPLOYMENT_PATH]/ log --oneline | head -5

# Verify latest version
cat [DEPLOYMENT_PATH]/requirements.txt | head -3
```

---

## Step 6: Future Deployments

**Automatic on every push:**
- Push code to GitHub
- Workflow auto-triggers
- Code deployed to VM in ~30-60 seconds
- Next cron job run uses new code

**Manual trigger (if needed):**
- Go to Actions → Deploy to GCP VM → Run workflow

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Permission denied (publickey)" | SSH public key not in VM's `~/.ssh/authorized_keys` |
| "Could not connect to VM" | Check GitHub Secret `GCP_VM_IP` is correct |
| "git clone fails" | Check `GCP_VM_DEPLOY_PATH` exists and is writable |
| "code not updating" | Check workflow ran successfully in Actions tab |

---

## What You Need to Do Now

Provide these 4 values:

```
GCP_VM_IP               = ?
GCP_VM_SSH_USER         = ?
GCP_VM_DEPLOYMENT_PATH  = ?
GCP_VM_SSH_PRIVATE_KEY  = [generated from Step 1]
```

Once provided, I'll create the `.github/workflows/deploy-to-gcp-vm.yml` file automatically.

---

## Notes

- Cron jobs on VM remain unchanged (no dependency on GitHub Action)
- Deployment takes ~30-60 seconds
- No downtime — code swapped in at next cron job execution
- SSH key stored securely in GitHub Secrets (never visible in logs)
