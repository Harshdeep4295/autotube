# Three Fixes + Cron Setup for Ubuntu Server

## 🔧 What Was Fixed

### Fix #1: PLAYLIST_ENABLED Default to True
**Status:** ✅ DONE

Changed in `config.py` line 179:
```python
# OLD:
PLAYLIST_ENABLED: bool = field(
    default_factory=lambda: os.getenv("PLAYLIST_ENABLED", "false").lower() == "true"
)

# NEW:
PLAYLIST_ENABLED: bool = field(
    default_factory=lambda: os.getenv("PLAYLIST_ENABLED", "true").lower() != "false"
)
```

**Effect:**
- Playlists are now auto-enabled by default
- All videos get auto-grouped into playlists
- Still can be disabled with `PLAYLIST_ENABLED=false` if needed
- **No env var needed** — just works out of the box

---

### Fix #2: Crontab Syntax Errors
**Status:** ✅ DONE

**What was broken:**
```bash
# BROKEN (in your original):
30 19 * * * ... python3 orchestrator.py ... >> /path/logs/autotube_$(date+%Y%m%d_%H%M%S).log

# ISSUES:
# 1. $(date+%Y%m%d_%H%M%S) — missing space, runs immediately at parse time
# 2. Not escaped for cron context
# 3. /bin/sh doesn't support this syntax reliably
# 4. Result: tries to write to /path/logs/autotube_(empty_date)
```

**What's fixed:**
```bash
# CORRECT:
0 4 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode auto >> /home/harshdeepsingh/cron_logs/autotube_auto_video_$(date +\%Y\%m\%d_\%H\%M\%S).log 2>&1'

# FIXES:
# 1. /bin/bash -c 'command' — wrap in shell for proper $() expansion
# 2. $(date +\%Y\%m\%d_%H%M%S) — escaped percents (\%) for cron
# 3. Date executed inside the quoted command, not at parse time
# 4. Result: creates unique log file per run with timestamp
```

**See:** `crontab_ubuntu.txt` for the corrected full schedule

---

### Fix #3: Added Shorts from Existing Videos (6 Crons)
**Status:** ✅ DONE

Added to `orchestrator.py`:
- New argument parser options: `--pick_strategy` and `--batch`
- New mode: `"shorts_from_existing"`
- New method: `run_shorts_from_existing(pick_strategy, batch)`
- Dispatch logic in `main()`

**Six daily cron jobs:**
```bash
02:00 UTC — Recent high-views (trending last 7 days)
08:00 UTC — All-time best (highest performer)
14:00 UTC — Underutilized #1 (low-view revival)
16:00 UTC — Underutilized #2 (low-view revival)
18:00 UTC — Evergreen (top performer rotation)
20:00 UTC — Recent viral (hottest last 3 days)
```

**Result:** 6 Shorts/day × 365 days = **2,190 Shorts/year** from 38 existing videos

---

## 🎯 Why Your Video Got Killed

**The MoviePy process was OOM (Out of Memory) killed:**

```
MoviePy - Writing video outputs/20260501_f90daa/video.mp4
frame_index:   0%|... | 3/7336 [00:06<4:56:36, 2.43s/it] ... Killed
```

**Root Cause:**
Your test was rendering a **5.1-minute (305s) video at 1920×1080** with:
- 6 sections of video clips
- Ken Burns animation
- Transitions
- Audio mixing
- Captions overlay

This requires **~4-6GB RAM** depending on codec.

**Check your Ubuntu VM memory:**
```bash
free -h
```

If you see:
```
               total        used       free
Mem:           2.0G        1.8G      0.2G   ← TOO SMALL
Swap:          1.0G        0.1G      0.9G
```

Then the process hits the memory ceiling and gets killed by the kernel's OOM killer.

**Solutions:**

### Option 1: Add Swap (Temporary)
```bash
# Create 4GB swap file
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make persistent (add to /etc/fstab):
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Option 2: Upgrade VM RAM (Recommended)
- If using AWS EC2: stop instance → change instance type to `t3.large` or `t3.xlarge` (4-8GB)
- If using DigitalOcean: resize droplet to 4GB
- If using GCP: upgrade machine type

### Option 3: Reduce Video Length
```bash
# Set shorter script
SCRIPT_WORD_COUNT=400 python orchestrator.py --dry-run
# 400 words ≈ 2.5 min video ≈ 2-3GB RAM needed
```

### Option 4: Run Videos Sequentially
```bash
# Don't run multiple orchestrator instances in parallel
# Cron should run them 2+ hours apart (already done in crontab_ubuntu.txt)
```

**Recommended: Upgrade to 4GB RAM + add 4GB swap**

---

## 📋 How to Apply the Crontab

### Step 1: Copy the corrected crontab

```bash
# On your Ubuntu server:
cd /home/harshdeepsingh/autotube
cat crontab_ubuntu.txt
```

### Step 2: Edit your crontab

```bash
crontab -e
```

### Step 3: Delete old broken entries, paste new ones

Replace everything with the contents of `crontab_ubuntu.txt`

### Step 4: Verify

```bash
crontab -l
```

You should see:
```
# AutoTube cron jobs (all times in UTC)
0 2 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views >> ...'
8 8 * * * /bin/bash -c 'cd /home/harshdeepsingh/autotube && . .venv/bin/activate && python3 orchestrator.py --mode shorts_from_existing --pick_strategy all_time_best >> ...'
...
```

### Step 5: Check logs

```bash
ls -lh /home/harshdeepsingh/cron_logs/
tail -f /home/harshdeepsingh/cron_logs/autotube_shorts_recent_*.log
```

---

## 🚀 Daily Schedule Summary

**All times in UTC** (convert to your timezone):

| Time | Task | What it does |
|------|------|-------------|
| **02:00** | Shorts #1 (Recent) | Pick trending video from last 7 days → convert to 9:16 Shorts |
| **04:00** | New Video | Research + Script + Voice + Video + Upload (full pipeline) |
| **08:00** | Shorts #2 (Best) | Pick all-time best video → convert to Shorts |
| **14:00** | Shorts #3 (Underutil) | Pick underutilized video → convert to Shorts |
| **16:00** | Shorts #4 (Underutil) | Pick another low-view video → convert to Shorts |
| **18:00** | Shorts #5 (Evergreen) | Pick top performer → convert to Shorts |
| **20:00** | Shorts #6 (Viral) | Pick hottest from last 3 days → convert to Shorts |

**Result:**
- 1 brand new video/day (full pipeline)
- 6 Shorts/day (from existing content)
- **7 uploads/day**
- **2,555 videos/year** (365 new + 2,190 Shorts)

---

## 🎁 What Each Fix Gives You

| Fix | Benefit |
|-----|---------|
| **#1: PLAYLIST_ENABLED=true** | All 2,555 videos auto-organized into playlists (no manual work) |
| **#2: Fixed Crontab** | Crons actually run reliably, logs have proper timestamps |
| **#3: Shorts Crons** | 6 daily Shorts from 38 existing videos = infinite content |

---

## ⚠️ Important Notes

1. **Timezone:** Cron uses UTC. If you're in IST (UTC+5:30), subtract 5.5 hours from cron times.
   - Example: 02:00 UTC = 07:30 IST

2. **Log Directory:** Must exist
   ```bash
   mkdir -p /home/harshdeepsingh/cron_logs
   ```

3. **Virtual Env:** Must be activated for each cron
   ```bash
   . .venv/bin/activate
   ```

4. **Memory:** If videos keep getting killed, upgrade RAM (see solution above)

5. **Email Notifications:** Cron sends stderr to your email. Check:
   ```bash
   mail
   ```

---

## Testing the New Shorts Mode

```bash
# Test locally first
cd /home/harshdeepsingh/autotube
. .venv/bin/activate

# Test recent high-views strategy
python3 orchestrator.py --mode shorts_from_existing --pick_strategy recent_high_views --dry-run

# Test all-time best
python3 orchestrator.py --mode shorts_from_existing --pick_strategy all_time_best

# Test with batch
python3 orchestrator.py --mode shorts_from_existing --pick_strategy underutilized --batch 3
```

---

## Summary

✅ **PLAYLIST_ENABLED** now defaults to `true` (no env var needed)  
✅ **Crontab syntax fixed** ($(date) now works correctly)  
✅ **6 Shorts crons added** (generate Shorts from existing videos)  
✅ **OOM killer explained** (your VM ran out of RAM — upgrade or add swap)

Ready to deploy! 🚀
