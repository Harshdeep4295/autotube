# Final: Commit & Deploy Shadow Merge Setup

**Everything is ready. Just 2 steps.**

---

## STEP 1: Commit New Files to GitHub

```bash
# From your local machine:

# Review what's new
git status

# Add all new files
git add auto_merge_shadow_to_main.sh \
         SHADOW_MERGE_SETUP.md \
         BRANCH_STRATEGY.md \
         VM_SETUP_2MINUTE.md \
         READY_TO_COMMIT.md \
         orchestrator.py \
         agents/video_agent.py

# Commit with a clear message
git commit -m "feat: implement shadow → main auto-merge with conflict detection

- Add auto_merge_shadow_to_main.sh script for hourly shadow → main merge
- Detect merge conflicts and send email to downloadsforall0@gmail.com
- Add memory logging to orchestrator.py for OOM debugging
- Add GCP integration (optional, disabled by default)
- Implement shadow branch development workflow
- Cost: $0 additional (VM only)

Setup: Follow SHADOW_MERGE_SETUP.md (5 minutes on VM)
Branch strategy: See BRANCH_STRATEGY.md"

# Push to GitHub
git push origin main
```

---

## STEP 2: Deploy to VM (5 minutes)

Run these commands on your LOCAL machine (copy-paste friendly):

### 2.1 Copy merge script to VM

```bash
scp -i ~/.ssh/autotube_github auto_merge_shadow_to_main.sh \
  root@VM_IP:/root/autotube/
```

Replace `VM_IP` with your actual VM IP.

### 2.2 SSH into VM and set up

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP

# Make script executable
chmod +x /root/autotube/auto_merge_shadow_to_main.sh

# Install mail utility (for email notifications)
apt-get update && apt-get install -y mailutils

# Edit crontab
crontab -e

# Replace the old git pull line with this:
0 * * * * /root/autotube/auto_merge_shadow_to_main.sh >> /tmp/autotube_merge.log 2>&1

# Save and exit (Ctrl+X, Y, Enter in nano)

# Verify setup
crontab -l
ls -lh /root/autotube/auto_merge_shadow_to_main.sh

# Exit SSH
exit
```

---

## DONE! ✓

Your setup is now:

```
GitHub (Code Repository)
  ├─ main branch (auto-updated from shadow)
  └─ shadow branch (where you push changes)

GCP VM (Your Pipeline)
  ├─ Every hour: Auto-merge shadow → main
  ├─ If conflict: Email you
  └─ Cron jobs: Run at 09/12/15/18 IST
```

---

## YOUR NEW WORKFLOW

### Make Changes

```bash
# On LOCAL machine
git checkout shadow
vim agents/video_agent.py
git add .
git commit -m "feat: something"
git push origin shadow

# Done! VM merges automatically next hour.
```

### Check Merge Status

```bash
# SSH into VM
ssh -i ~/.ssh/autotube_github root@VM_IP

# View merge logs
tail -20 /tmp/autotube_merge.log

# If conflict, you'll get an email with instructions
```

---

## COST

- **VM:** $10-20/month (already running)
- **Additional:** $0

---

## DOCUMENTATION

- **`BRANCH_STRATEGY.md`** — How to use shadow/main branches
- **`SHADOW_MERGE_SETUP.md`** — Detailed setup (already done)
- **`VM_SETUP_2MINUTE.md`** — Quick reference for cron job
- **`auto_merge_shadow_to_main.sh`** — The merge script

---

## QUICK REFERENCE

| Command | Purpose |
|---------|---------|
| `git checkout shadow` | Start work on development branch |
| `git push origin shadow` | Push changes (VM merges to main automatically) |
| `ssh root@VM_IP` | SSH into VM to check logs |
| `tail /tmp/autotube_merge.log` | Check merge status on VM |
| `crontab -l` | View scheduled jobs on VM |

---

**All set! You're running the simplest, cheapest, most automated setup possible.** 🎉

- Develop on `shadow`
- VM merges to `main` hourly
- Conflicts emailed to you
- Everything else automatic

Total cost: **$10-20/month** (just the VM)  
Manual work: **Minimal** (only when conflicts occur)
