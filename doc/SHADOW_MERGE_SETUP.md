# Shadow → Main Auto-Merge Setup

**Purpose:** Automatically merge `shadow` branch to `main` every hour. If conflict, email you.  
**Email:** downloadsforall0@gmail.com  
**Setup time:** 5 minutes

---

## How It Works (IMPORTANT!)

```
Every hour:
  ↓
1. Pull latest shadow branch
  ↓
2. Try to merge shadow → main
  ↓
3a. Success? 
    → Commit merge ✓
    → Push main to origin ✓
    → Silent (no email)
  ↓
3b. Conflict detected?
    → ❌ ABORT merge (do NOT complete)
    → main branch unchanged
    → 📧 Email you with conflict details
    → Waiting for YOU to resolve manually
```

**KEY POINT:** If conflict happens, the merge is **ABORTED**. 
Nothing is committed, nothing is pushed. 
You get an email and must resolve it manually.
Next hour's auto-merge will try again (after you fix it).


---

## Step 1: Copy Script to VM (2 min)

```bash
# From your LOCAL machine:
scp -i ~/.ssh/autotube_github auto_merge_shadow_to_main.sh \
  root@VM_IP:/root/autotube/

# Verify on VM
ssh -i ~/.ssh/autotube_github root@VM_IP "ls -l /root/autotube/auto_merge_shadow_to_main.sh"
```

## Step 2: Make Script Executable (30 sec)

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP
chmod +x /root/autotube/auto_merge_shadow_to_main.sh
exit
```

## Step 3: Install `mail` Command (1 min)

The script uses `mail` to send emails. Install it:

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP

# Install mail utility
apt-get update
apt-get install -y mailutils

exit
```

## Step 4: Update Cron Job (1.5 min)

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP

# Edit crontab
crontab -e

# REPLACE this line:
# 0 * * * * cd /root/autotube && git pull origin main >> /tmp/git_pull.log 2>&1

# WITH this line:
0 * * * * /root/autotube/auto_merge_shadow_to_main.sh >> /tmp/autotube_merge.log 2>&1

# Save and exit
```

## Step 5: Verify Setup (30 sec)

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP

# Check crontab
crontab -l
# Should show: 0 * * * * /root/autotube/auto_merge_shadow_to_main.sh ...

# Check script exists
ls -lh /root/autotube/auto_merge_shadow_to_main.sh

# Check mail is installed
which mail

exit
```

---

## Your New Workflow

### For Regular Changes (No Conflicts)

```bash
# On LOCAL machine:

# 1. Make changes on shadow branch
git checkout shadow
vim agents/video_agent.py
# ... edit ...

# 2. Commit to shadow
git add agents/video_agent.py
git commit -m "feat: improve something"

# 3. Push to shadow
git push origin shadow

# 4. Done!
# VM will auto-merge shadow → main every hour
# No email = successful merge ✓
```

### If Conflict Happens

**You'll get an email like:**

```
Subject: AutoTube: MERGE CONFLICT - shadow → main (MANUAL ACTION REQUIRED)

Conflicted Files:
  agents/video_agent.py
  config.py

Last 5 commits on main:
  ...

ACTION REQUIRED:
1. SSH into VM: ssh root@VM_IP
2. Go to repo: cd /root/autotube
3. Check status: git status
4. Resolve conflicts: vim agents/video_agent.py
   (remove <<<<<<, ======, >>>>>>)
5. After resolving: git add . && git commit -m 'Merge shadow into main'
6. Push: git push origin main
```

**Then resolve manually and the merge will succeed next hour.**

---

## What Gets Logged

```bash
# Check merge logs
tail -50 /tmp/autotube_merge.log

# Sample output:
[2026-04-28 10:00:01] === Starting shadow → main merge ===
[2026-04-28 10:00:02] ✓ Fetched from origin
[2026-04-28 10:00:02] ✓ Checked out shadow branch
[2026-04-28 10:00:03] ✓ Pulled latest shadow
[2026-04-28 10:00:03] ✓ Checked out main branch
[2026-04-28 10:00:04] ✓ Merge successful: shadow → main
[2026-04-28 10:00:05] ✓ Pushed main to origin
[2026-04-28 10:00:05] SUCCESS: shadow branch merged to main
```

---

## Testing the Email

To test email before relying on it:

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP

# Send test email
echo "Test email from AutoTube" | mail -s "AutoTube Test" downloadsforall0@gmail.com

# Check if sent
tail -20 /var/log/mail.log

exit
```

---

## FAQ

**Q: What if merge succeeds but push fails?**  
A: You'll get an email about the push failure. SSH and `git push origin main` manually.

**Q: Can I manually push to main without merging shadow?**  
A: Yes, anytime. The script will just merge shadow on top of your changes (or skip if no new shadow changes).

**Q: What if I want to cancel the auto-merge?**  
A: Remove the cron job: `crontab -e` and delete the line.

**Q: How often does it try to merge?**  
A: Every hour at :00 (0 * * * *). Change the frequency by editing crontab:
- Every 30 minutes: `*/30 * * * *`
- Every 6 hours: `0 */6 * * *`

---

## Quick Checklist

- [ ] Script copied to VM (`/root/autotube/auto_merge_shadow_to_main.sh`)
- [ ] Script is executable (`chmod +x`)
- [ ] `mail` utility installed (`apt-get install mailutils`)
- [ ] Cron job updated (points to the script)
- [ ] Crontab verified (`crontab -l`)
- [ ] Email tested (optional but recommended)

---

## Your Development Workflow Summary

```
Local Machine:
  1. git checkout shadow
  2. Make changes
  3. git push origin shadow

VM (Automatic, hourly):
  1. Pull shadow
  2. Merge shadow → main
  3. Push main to origin
  4. If conflict: Email you

Result:
  - main branch always has latest shadow code
  - Conflicts are caught immediately
  - You're notified only when action needed
```

---

**Done!** Now whenever you push to `shadow`, it automatically merges to `main` on the VM (or emails you if conflict).
