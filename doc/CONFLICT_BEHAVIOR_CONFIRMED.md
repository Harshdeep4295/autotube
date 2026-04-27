# Conflict Behavior — User Confirmed ✅

**This is what you asked for. This is what the script does.**

---

## The Script Logic (Simplified)

```python
# Every hour at :00
try_merge = git merge shadow → main

if try_merge succeeds:
    # SUCCESS PATH
    git push origin main
    # Next cron job gets updated code
    # Silent, no email
else:
    # CONFLICT PATH (This is what you want)
    git merge --abort              # ← Skip the merge
    # main branch unchanged
    # old code still running
    
    send_email(user)                # ← Email ONLY
    # "Hey, conflict detected. You need to fix this."
    
    exit()                          # ← Do nothing else
    # Wait for user to manually resolve
    
    # Next hour:
    # Script tries again (after user fixed it)
```

---

## What Happens on Conflict (Exactly as You Specified)

### Timeline

```
09:00 — Auto-merge runs
├─ git pull shadow
├─ Try: git merge shadow → main
├─ ❌ CONFLICT!
├─ ABORT the merge (nothing merged)
├─ 📧 Send email to downloadsforall0@gmail.com
├─ Exit script
└─ ❌ Do NOT auto-commit, do NOT auto-push, do NOT change anything

09:01 — Your old code is still running
├─ No changes made
├─ main branch is unchanged
├─ shadow branch is unchanged
└─ Everything stable

10:00 — Your email arrives
├─ Subject: "AutoTube: MERGE CONFLICT - shadow → main"
├─ Body: conflicted files + how to fix
└─ YOU decide what to do

14:00 — You manually fix (when you want)
├─ SSH into VM
├─ Resolve the conflicts
├─ git add . && git commit
├─ git push origin main
└─ OLD CODE STILL RUNNING until you push

14:05 — After you push main
├─ Old code keeps running (until next merge)
├─ Next auto-merge (15:00): succeeds and uses your fixed code

15:00 — Auto-merge runs again
├─ Now it succeeds (you fixed the conflict)
├─ Merges shadow → main
├─ Pushes to origin
└─ Next cron job (15:00 IST) gets the updated code
```

---

## Key Points (Your Requirements)

✅ **"Unless I do resolve manually, don't do auto-merge"**
→ Script aborts merge on conflict (nothing is merged)

✅ **"Only then merge if there is no conflict"**
→ Script only merges when `git merge` succeeds cleanly

✅ **"Skip git merge and move on with email"**
→ Script does `git merge --abort` then sends email

✅ **"Don't do anything then unless I interview"**
→ Script does NOTHING after email (waits for manual action)

✅ **"Let the old code run"**
→ No changes are committed, old code keeps running

---

## The Script Code (Proof)

```bash
# From auto_merge_shadow_to_main.sh

if git merge shadow --no-edit >> "$LOG_FILE" 2>&1; then
    # SUCCESS: merge worked
    log_message "✓ Merge successful: shadow → main"
    git push origin main
    log_message "✓ Pushed main to origin"

else
    # CONFLICT: merge failed
    log_message "ERROR: Merge conflict detected!"
    log_message "IMPORTANT: Merge is being ABORTED - nothing is committed or pushed"
    
    # Get conflict details for email
    CONFLICTS=$(git diff --name-only --diff-filter=U)
    
    # ABORT THE MERGE (do NOT complete it)
    git merge --abort >> "$LOG_FILE" 2>&1
    log_message "✓ Merge aborted - main branch is unchanged"
    
    # Send email ONLY
    send_email "AutoTube: MERGE CONFLICT - shadow → main" \
        "Conflicted files: $CONFLICTS\n\nAction required: SSH and resolve manually"
    
    # Exit and wait
    log_message "Waiting for manual resolution..."
    exit 0
fi
```

---

## This Is Safe Because

1. **On conflict:** Merge is ABORTED (via `git merge --abort`)
2. **Nothing is committed:** `git merge --abort` reverses any changes
3. **Nothing is pushed:** No `git push` happens if merge fails
4. **Old code keeps running:** No changes to main branch
5. **You get notified:** Email with clear instructions
6. **Next hour:** Script tries again (will succeed after you fix)

---

## Your Render Cron Jobs (Unchanged)

```
09:00 IST → python orchestrator.py --render --count 1
12:00 IST → python orchestrator.py --render --count 1
15:00 IST → python orchestrator.py --render --count 1
18:00 IST → python orchestrator.py --render --count 1
```

These run independently. They don't care about merges.

If main branch hasn't changed (because merge was aborted due to conflict), they just use old code. No problem.

---

## Example Scenario

```
Day 1, 09:00 — Auto-merge happens
└─ Conflict detected
└─ Merge ABORTED
└─ Email sent
└─ Old code runs all day

Day 1, 09:05 — You get email
└─ You see there's a conflict
└─ You have time to fix it (or not)

Day 1, 15:00 — Your render job runs
└─ Uses old code (since merge was aborted)
└─ Works fine

Day 2, 10:00 — You decide to fix
└─ SSH, resolve conflicts, push

Day 2, 11:00 — Next auto-merge
└─ Now succeeds (you fixed it)
└─ Merges shadow → main
└─ Pushes to origin

Day 2, 12:00 — Next render job
└─ Uses updated code
└─ Happy
```

---

## Summary

| Scenario | Behavior |
|----------|----------|
| No conflict | ✓ Merge + Push (automated) |
| Conflict detected | ❌ Abort merge, Email only, Old code runs |
| You manually fix | ✓ Next hour merge succeeds |
| You don't fix | ⏳ Old code keeps running (safe) |

---

**This is exactly what you asked for. Nothing is automated on conflict. You have full control.** ✅
