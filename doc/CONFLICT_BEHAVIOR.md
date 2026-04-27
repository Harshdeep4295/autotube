# Conflict Behavior — Crystal Clear

**TL;DR:** If conflict occurs, **NOTHING happens automatically**. Just an email.

---

## What Happens When There's a Conflict

### Timeline

```
Hour 10:00 — Auto-merge tries
─────────────────────────────
git merge shadow → main
  ❌ CONFLICT DETECTED
  
The script does:
  ❌ Does NOT commit the merge
  ❌ Does NOT push anything
  ❌ Does NOT update main branch
  
  ✅ ABORTS the merge
  ✅ main branch stays unchanged
  ✅ Sends you an email
  
Result:
  ✗ main is exactly as it was before
  ✗ shadow is exactly as it was before
  📧 Email in your inbox


Hour 10:01 — You receive email
─────────────────────────────
Subject: AutoTube: MERGE CONFLICT - shadow → main (MANUAL ACTION REQUIRED)

Body:
  Conflicted Files:
    agents/video_agent.py
    
  ACTION REQUIRED:
    1. SSH into VM
    2. Resolve conflicts
    3. git add . && git commit -m "fix: merge"
    4. git push origin main


Hour 10:30 — You manually resolve
─────────────────────────────────
ssh root@VM_IP
cd /root/autotube
vim agents/video_agent.py  # Remove <<<<<<, ======, >>>>>>
git add .
git commit -m "fix: merge conflict (manual)"
git push origin main


Hour 11:00 — Auto-merge tries again
─────────────────────────────────
git merge shadow → main
  ✅ SUCCESS (you fixed the conflict)
  ✅ Commits the merge
  ✅ Pushes main to origin
  ✅ Email: None (silent success)
```

---

## What Does NOT Happen on Conflict

❌ Auto-merge does NOT automatically resolve conflicts  
❌ Auto-merge does NOT force-push main  
❌ Auto-merge does NOT delete shadow  
❌ Auto-merge does NOT create a messy merge commit  
❌ Auto-merge does NOT silently fail  

---

## What DOES Happen on Conflict

✅ Auto-merge detects the conflict  
✅ Auto-merge ABORTS the merge  
✅ Auto-merge sends you an email  
✅ Auto-merge waits for your manual resolution  
✅ Next hour, it automatically tries again  

---

## The Script Logic (Simplified)

```bash
git merge shadow → main

if merge succeeds:
  git push origin main
  exit (silent, no email)

else:  # Conflict!
  git merge --abort  # Undo the merge attempt
  
  # Email the user
  send_email("MERGE CONFLICT", <<instructions>>)
  
  # Exit and wait for manual action
  exit
```

**No automatic commit on conflict. Ever.**

---

## Real-World Example

### Scenario: You and Someone Else Edit Same File

```
File: agents/video_agent.py

main has:
  Line 100: def render(self):
  Line 101:   return "v1"

shadow has:
  Line 100: def render(self):
  Line 101:   return "v2"

Auto-merge runs at 11:00:
  ❌ Conflict! Both versions of line 101
  ❌ Aborts merge
  📧 Emails you

You manually fix at 11:15:
  vim agents/video_agent.py
  Choose: v1 or v2? (your decision)
  git add . && git commit && git push

Auto-merge runs at 12:00:
  ✅ Now it succeeds (conflict resolved)
  ✅ Merges and pushes
```

---

## What You Need to Do When Conflict Happens

**Step 1: Check your email** (from downloadsforall0@gmail.com)
- Subject line tells you it's a merge conflict
- Body has exact file names that conflict

**Step 2: SSH into VM**
```bash
ssh -i ~/.ssh/autotube_github root@VM_IP
cd /root/autotube
```

**Step 3: Resolve conflicts**
```bash
# See conflicted files
git status

# Edit the file(s)
vim agents/video_agent.py
# Remove lines like: <<<<<<, ======, >>>>>>
# Keep the version you want
```

**Step 4: Complete the merge**
```bash
git add .
git commit -m "fix: merge conflict (manual)"
git push origin main
exit
```

**Step 5: Done!**
- Main branch is now updated
- Next hour, auto-merge will succeed (no more conflict)

---

## FAQ

**Q: How long do I have to fix conflicts?**  
A: As long as you want. Next auto-merge will retry every hour until you fix it.

**Q: What if I don't fix it for days?**  
A: Shadow and main just diverge. You'll keep getting emails each hour. Fix whenever you're ready.

**Q: Can I manually push to main while a conflict is pending?**  
A: Yes! Just do it. Next hour, auto-merge will merge shadow on top of your push.

**Q: What if the conflict is complex?**  
A: You have full Git access. Use `git merge --abort` if needed, start over, whatever works for you.

**Q: Will auto-merge break anything if I don't resolve conflicts?**  
A: No. It just keeps aborting every hour until you fix it. No damage.

---

## Summary

| Event | Auto-Merge Behavior |
|-------|-------------------|
| No conflict | ✅ Auto-merge succeeds, auto-push, silent |
| Conflict occurs | ❌ Auto-merge aborts, sends email, waits for you |
| You resolve | ✅ Next hour auto-merge succeeds |
| You don't resolve | ⏳ Keeps aborting hourly, sends email each time |

**You are always in control. Auto-merge never commits anything if there's any doubt.**

---

**Everything is safe. Conflicts just mean "hey, you need to review this manually."**
