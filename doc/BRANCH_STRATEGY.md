# Branch Strategy: Shadow → Main

**Purpose:** Keep `main` clean while developing on `shadow`, with automatic conflict detection.

---

## Branch Roles

```
main
  ├─ Production-ready code
  ├─ Always merged from shadow (auto-merge hourly)
  ├─ Used by: VM cron jobs (render at 09/12/15/18 IST)
  └─ Manual push: Only if resolving conflicts

shadow
  ├─ Development branch
  ├─ Where you push all changes
  ├─ Auto-merged to main every hour
  ├─ Used by: You, for testing code changes
  └─ Manual push: After each code change

(future branches)
  ├─ feature/something — for features
  ├─ bugfix/something — for fixes
  └─ All merge to shadow, shadow merges to main
```

---

## Git Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Your Local Machine                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. git checkout shadow                                         │
│  2. vim agents/video_agent.py  (make changes)                   │
│  3. git add agents/video_agent.py                               │
│  4. git commit -m "fix: something"                              │
│  5. git push origin shadow                                      │
│                                                                 │
│                    │                                            │
│                    ↓                                            │
│  ┌─────────────────────────────────┐                           │
│  │ GitHub                          │                           │
│  │ ┌─────────────┬─────────────┐   │                           │
│  │ │ shadow      │ main        │   │                           │
│  │ │ branch      │ branch      │   │                           │
│  │ │ (your code) │ (auto-sync) │   │                           │
│  │ └─────────────┴─────────────┘   │                           │
│  └─────────────────────────────────┘                           │
│                    │                                            │
│                    ↓ (Every hour)                               │
│  ┌─────────────────────────────────┐                           │
│  │ GCP VM (auto_merge_shadow_*.sh)  │                           │
│  │                                 │                           │
│  │ 1. git fetch origin              │                           │
│  │ 2. git pull origin shadow        │                           │
│  │ 3. git merge shadow → main       │                           │
│  │    ├─ Success? → git push main   │                           │
│  │    └─ Conflict? → Email you 📧   │                           │
│  └─────────────────────────────────┘                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## When to Use Each Branch

### `shadow` Branch (Your Development)

**Use for:**
- New features
- Bug fixes
- Code improvements
- Testing changes

**Example:**
```bash
git checkout shadow
vim agents/video_agent.py
git add .
git commit -m "feat: add better animation"
git push origin shadow
# Done! VM merges automatically next hour
```

### `main` Branch (Production)

**Use for:**
- Reviewing merged code
- Checking render job logs
- Rolling back if needed

**You rarely push directly to main** (only to resolve conflicts)

---

## Conflict Resolution Examples

### Example 1: No Conflict (Common Case)

```bash
Time: 09:00
─────────────────────────────────────

shadow branch has:
  agents/video_agent.py (your changes)
  
main branch has:
  (previous code)

Merge result:
  ✓ Auto-merged successfully
  ✓ Email: None (silent success)
  ✓ main updated automatically
```

### Example 2: Conflict (Rare Case)

```bash
Time: 10:00 (Auto-merge runs)
─────────────────────────────────────

shadow branch has:
  agents/video_agent.py (line 500: def foo())
  
main branch has:
  agents/video_agent.py (line 500: def bar()) ← Different!

Merge result:
  ✗ Conflict detected!
  ❌ Merge ABORTED (nothing committed, nothing pushed)
  main branch is UNCHANGED
  📧 Email sent to you with:
     - List of conflicted files
     - Recent commits on both branches
     - Step-by-step instructions

Your action (MANUAL, within 1 hour):
  1. SSH into VM
  2. Resolve the conflicting files in editor
  3. git add . && git commit -m "fix: merge conflict (manual)"
  4. git push origin main
  
Result:
  5. Next hour: auto-merge tries again ✓
  6. This time: succeeds (no conflict anymore)
  7. Automatic push to main ✓
```

**IMPORTANT:** Nothing is auto-committed if conflict happens. 
You manually resolve, then VM auto-merges next hour.


### Example 3: You Push Directly to Main

```bash
Time: 11:00
─────────────────────────────────────

You manually do:
  git checkout main
  git push origin main

At 12:00 (next merge):
  ✓ Auto-merge detects main is ahead
  ✓ Still merges shadow (overwrites your manual push if newer)
  
Note: Avoid this. Use shadow instead.
```

---

## Commands You'll Use

### Regular Development (Every Day)

```bash
# Start work
git checkout shadow

# Make changes
vim agents/video_agent.py
.venv/bin/python3 orchestrator.py --dry-run --count 1

# Commit and push
git add agents/video_agent.py
git commit -m "fix: something"
git push origin shadow

# Done! VM merges automatically.
```

### Handling Conflicts (Rare)

```bash
# You'll get an email. Then:

# SSH into VM
ssh -i ~/.ssh/autotube_github root@VM_IP

# Check what's conflicting
cd /root/autotube
git status

# Edit the file(s)
vim agents/video_agent.py

# After resolving (remove <<<<<<, ======, >>>>>> lines)
git add .
git commit -m "Merge shadow into main (manual)"
git push origin main

exit
```

### Checking Merge Logs

```bash
# SSH into VM
ssh -i ~/.ssh/autotube_github root@VM_IP

# View merge history
tail -50 /tmp/autotube_merge.log

# Or check git log
git log main --oneline -10

exit
```

---

## Safety Features

✓ **Automatic backups** — main is always on GitHub  
✓ **Conflict detection** — Merge aborts if conflict, sends email  
✓ **Never force-push** — Safe merge strategy  
✓ **Hourly syncs** — Latest shadow code reaches main quickly  
✓ **Email alerts** — You're notified of issues immediately  

---

## Tips

**Tip 1:** Always work on `shadow`
```bash
git checkout shadow  # Do this first
```

**Tip 2:** Never manually push to main
```bash
# Don't do this:
git checkout main && git push origin main

# Do this instead:
git checkout shadow && git push origin shadow
# VM merges automatically
```

**Tip 3:** Pull shadow before starting work
```bash
git checkout shadow
git pull origin shadow  # Get latest from VM
# Then make your changes
```

**Tip 4:** Check merge logs after pushing
```bash
# After pushing to shadow, wait ~1 hour then check:
ssh root@VM_IP tail -20 /tmp/autotube_merge.log
```

---

## Troubleshooting

**Q: I pushed to shadow but main didn't update?**  
A: Wait up to 1 hour (cron runs at :00). Check merge logs: `ssh root@VM_IP tail /tmp/autotube_merge.log`

**Q: Merge conflict happened. What do I do?**  
A: Check your email (has step-by-step instructions). SSH into VM and resolve manually.

**Q: Can I have multiple feature branches?**  
A: Yes! Create `feature/xyz`, push to that, then PR to `shadow`, then `shadow` auto-merges to `main`.

**Q: What if I accidentally pushed to main?**  
A: No problem. Next auto-merge will sync shadow on top. Just use shadow for future changes.

---

**Summary:**
- **You push to:** `shadow`
- **VM auto-merges:** `shadow` → `main` (hourly)
- **If conflict:** You get an email and resolve manually
- **Cost:** $0 (just your VM)
- **Automation:** ~100% (conflicts are caught immediately)

Simple, safe, automatic. 🎯
