# TODO — Action Items

**Everything is ready. Just execute these steps.**

---

## ✅ STEP 1: Commit to GitHub (Copy-Paste Ready)

```bash
cd /Users/harshdeepsingh/Projects/git_projects/autotube

git add auto_merge_shadow_to_main.sh \
        SHADOW_MERGE_SETUP.md \
        BRANCH_STRATEGY.md \
        VM_SETUP_2MINUTE.md \
        READY_TO_COMMIT.md \
        COMMIT_AND_DEPLOY.md \
        orchestrator.py \
        agents/video_agent.py

git commit -m "feat: shadow → main auto-merge with conflict email alerts

- Add hourly auto-merge script (shadow → main)
- Email conflicts to downloadsforall0@gmail.com
- Add memory logging for OOM debugging
- Add optional GCP integration (disabled by default)
- Cost: $0 additional

Setup: Follow SHADOW_MERGE_SETUP.md (5 min)"

git push origin main
```

**⏱️ Time: 1 minute**

---

## ✅ STEP 2: Deploy Script to VM

Copy merge script to VM:

```bash
scp -i ~/.ssh/autotube_github auto_merge_shadow_to_main.sh root@VM_IP:/root/autotube/
```

**Replace `VM_IP` with your actual VM IP address**

**⏱️ Time: 30 seconds**

---

## ✅ STEP 3: Set Up VM (SSH Commands)

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP
```

Then run these commands on VM:

```bash
# 1. Make script executable
chmod +x /root/autotube/auto_merge_shadow_to_main.sh

# 2. Install mail utility
apt-get update
apt-get install -y mailutils

# 3. Edit crontab
crontab -e
```

**When crontab editor opens:**
- Find and remove: `0 * * * * cd /root/autotube && git pull origin main...`
- Add this new line:
  ```
  0 * * * * /root/autotube/auto_merge_shadow_to_main.sh >> /tmp/autotube_merge.log 2>&1
  ```
- Save and exit (Ctrl+X, Y, Enter)

Then verify:

```bash
# Check crontab
crontab -l

# Check script exists
ls -lh /root/autotube/auto_merge_shadow_to_main.sh

# Exit SSH
exit
```

**⏱️ Time: 3 minutes**

---

## ✅ STEP 4: Test Setup (Optional but Recommended)

```bash
ssh -i ~/.ssh/autotube_github root@VM_IP

# Test email
echo "Test from AutoTube" | mail -s "Test email" downloadsforall0@gmail.com

# Check if mailutils works
which mail

# Exit
exit
```

**⏱️ Time: 1 minute**

---

## 🎉 YOU'RE DONE!

Total time: **5-6 minutes**

Now your setup is:

```
You write code on: git checkout shadow
                   git push origin shadow
                   
VM auto-merges:    shadow → main (every hour at :00)
                   
Email alerts:      If conflict occurs → downloadsforall0@gmail.com
                   
Cost:              $10-20/month (just VM, already running)
```

---

## 📖 Read These (To Understand Your New Setup)

After deployment, read in this order:

1. **BRANCH_STRATEGY.md** (10 min read)
   - Explains shadow/main workflow
   - Shows when conflicts happen
   - Troubleshooting guide

2. **SHADOW_MERGE_SETUP.md** (5 min reference)
   - Detailed setup steps (already done)
   - FAQ

3. **VM_SETUP_2MINUTE.md** (Quick reference)
   - Keep for future reference

---

## 🚦 Traffic Light Status

**Right now:**
- ✅ All code ready
- ✅ All scripts ready
- ✅ All documentation ready

**After Step 1 (Commit):**
- ✅ Code on GitHub
- ⏳ VM still running old code

**After Step 3 (Deploy to VM):**
- ✅ Deployment complete
- ✅ Auto-merge active
- ✅ Ready for production

---

## 📝 Your New Development Workflow

### Daily Workflow

```bash
# 1. Make sure you're on shadow
git checkout shadow

# 2. Pull latest (in case VM merged something)
git pull origin shadow

# 3. Make your changes
vim agents/video_agent.py

# 4. Test (optional)
.venv/bin/python3 orchestrator.py --dry-run --count 1

# 5. Commit
git add agents/video_agent.py
git commit -m "feat: improve animation"

# 6. Push to shadow
git push origin shadow

# 7. Done! VM merges to main in next hour
```

### If Conflict Occurs

```bash
# You'll get email with subject line:
# "AutoTube: MERGE CONFLICT - shadow → main (MANUAL ACTION REQUIRED)"

# Follow the steps in the email:
ssh -i ~/.ssh/autotube_github root@VM_IP
cd /root/autotube
git status  # See what's conflicted
vim agents/video_agent.py  # Fix the conflict
git add .
git commit -m "Merge shadow into main (manual)"
git push origin main
exit
```

---

## 📞 Support

If something doesn't work:

1. Check merge logs: `ssh root@VM_IP tail -50 /tmp/autotube_merge.log`
2. Check crontab: `ssh root@VM_IP crontab -l`
3. Check if mail is installed: `ssh root@VM_IP which mail`
4. Read SHADOW_MERGE_SETUP.md (FAQ section)

---

**Execute these 4 steps now, and you're live!** ✨
