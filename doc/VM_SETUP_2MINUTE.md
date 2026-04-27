# AutoTube VM Setup — 2 Minutes Only

**Goal:** Auto-pull code from GitHub every hour + run existing cron jobs  
**Cost:** $0 (runs on existing VM)  
**Setup time:** 2 minutes

---

## ONE-TIME SETUP (5 Minutes)

### Step 1: Copy merge script to VM (2 min)

From your LOCAL machine:

```bash
scp -i ~/.ssh/autotube_github auto_merge_shadow_to_main.sh \
  root@VM_IP:/root/autotube/
```

### Step 2: SSH and prepare VM (2 min)

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP

# Make script executable
chmod +x /root/autotube/auto_merge_shadow_to_main.sh

# Install mail (for conflict notifications)
apt-get update && apt-get install -y mailutils

exit
```

### Step 3: Add merge cron job (1 min)

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP

# Open crontab
crontab -e

# Add this ONE line:
0 * * * * /root/autotube/auto_merge_shadow_to_main.sh >> /tmp/autotube_merge.log 2>&1

# Save and exit (Ctrl+X, Y, Enter in nano)
```

### Step 4: Verify setup (30 sec)

```bash
# Check crontab was added
crontab -l
# Should show the merge script line

# Check script exists
ls -lh /root/autotube/auto_merge_shadow_to_main.sh

exit
```

Done! ✓

---

## YOUR NEW WORKFLOW

### Making Code Changes

```bash
# On your LOCAL machine:

# 1. Switch to shadow branch
git checkout shadow

# 2. Make changes
vim agents/video_agent.py

# 3. Test locally (optional)
.venv/bin/python3 orchestrator.py --dry-run --count 1

# 4. Commit and push to shadow
git add agents/video_agent.py
git commit -m "feat: improve something"
git push origin shadow

# 5. That's it! 
# VM will auto-merge shadow → main in next hour.
```

### VM Automatic Execution

```
Every hour at :00 → VM runs: auto-merge shadow → main
                    └─ If conflict: sends email to you
                    └─ If success: pushes main to origin
                    
09:00 IST         → Cron runs render job
12:00 IST         → Cron runs render job
15:00 IST         → Cron runs render job
18:00 IST         → Cron runs render job
```

### If Merge Conflict Occurs

**You'll receive an email with:**
- List of conflicted files
- Recent commits on both branches
- Instructions to resolve manually

**Resolution:**
```bash
ssh -i ~/.ssh/autotube_github root@VM_IP
cd /root/autotube
git status  # See conflicts
vim <conflicted-file>  # Fix conflicts
git add .
git commit -m "Merge shadow into main (manual)"
git push origin main
```

---

## VERIFY IT'S WORKING

### Check last git pull

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP "tail -20 /tmp/git_pull.log"
```

### Check render job logs

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP "tail -50 /root/autotube/logs/pipeline_*.log"
```

### Check next render time

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP "crontab -l | grep orchestrator"
```

---

## IF YOU NEED TO CHANGE TIMES

Edit your render cron job times:

```bash
# SSH into VM
ssh -i ~/.ssh/autotube_github root@VM_IP

# Edit crontab
crontab -e

# Change these lines (times in IST):
0 9 * * * cd /root/autotube && python3 orchestrator.py --render --count 1
0 12 * * * cd /root/autotube && python3 orchestrator.py --render --count 1
0 15 * * * cd /root/autotube && python3 orchestrator.py --render --count 1
0 18 * * * cd /root/autotube && python3 orchestrator.py --render --count 1
```

---

## IF AUTO-PULL IS TOO SLOW

If you want code changes immediately (don't want to wait 1 hour):

```bash
# Manual pull (do this after pushing code)
ssh -i ~/.ssh/autotube_github root@VM_IP "cd /root/autotube && git pull origin main"
```

Or change auto-pull frequency to every 15 minutes:

```bash
# Instead of: 0 * * * * ...
# Use:        */15 * * * * ...
# This runs at :00, :15, :30, :45 of every hour
```

---

## QUICK CHECKLIST

- [x] VM has existing cron jobs (09/12/15/18 IST)
- [ ] Added git pull cron job (0 * * * * ...)
- [ ] Tested: `crontab -l` shows both
- [ ] Tested: Code change → git push → VM pulls within 1 hour

---

## COST BREAKDOWN

| Item | Cost | Status |
|------|------|--------|
| GCP VM (e2-small or e2-medium) | $10-20/month | Already running ✓ |
| GitHub (code storage) | FREE | Already have ✓ |
| Cron jobs (render) | FREE | Running on VM ✓ |
| Auto git pull | FREE | Added this ✓ |
| **TOTAL** | **$10-20/month** | **Done!** |

---

## IMPROVEMENTS INCLUDED

These are already in `orchestrator.py` (no additional cost):

✓ **Memory logging** — Shows [MEMORY ...] checkpoints to debug OOM  
✓ **GCP integration ready** — If you ever want to use GCS/Firestore (optional)  
✓ **Backward compatible** — Works on existing VM with no changes  
✓ **GitHub Action ready** — Can add later if GitHub minutes available

Just `git pull` and they're live on your VM.

---

## DONE! 🎉

That's it. Your pipeline is set up and automatic.

- Push code to GitHub
- VM pulls automatically
- Cron jobs run at scheduled times
- Logs in `/root/autotube/logs/`

No additional costs. No additional services. Just your existing VM.
