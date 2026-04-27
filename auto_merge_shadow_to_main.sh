#!/bin/bash
# Auto-merge shadow branch to main with conflict notification
# Run this via cron: 0 * * * * /root/autotube/auto_merge_shadow_to_main.sh

set -e

cd /root/autotube

# Log file
LOG_FILE="/tmp/autotube_merge.log"
EMAIL="downloadsforall0@gmail.com"
HOSTNAME=$(hostname)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Function to send email
send_email() {
    local subject="$1"
    local body="$2"

    echo "Sending email: $subject"
    echo -e "$body" | mail -s "$subject" "$EMAIL"
}

# Function to log
log_message() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log_message "=== Starting shadow → main merge ==="

# Fetch latest from remote
git fetch origin >> "$LOG_FILE" 2>&1
log_message "✓ Fetched from origin"

# Check out shadow branch
git checkout shadow >> "$LOG_FILE" 2>&1
log_message "✓ Checked out shadow branch"

# Pull latest shadow
git pull origin shadow >> "$LOG_FILE" 2>&1
log_message "✓ Pulled latest shadow"

# Check out main branch
git checkout main >> "$LOG_FILE" 2>&1
log_message "✓ Checked out main branch"

# Try to merge shadow into main
if git merge shadow --no-edit >> "$LOG_FILE" 2>&1; then
    log_message "✓ Merge successful: shadow → main"

    # Push merged main back to origin
    if git push origin main >> "$LOG_FILE" 2>&1; then
        log_message "✓ Pushed main to origin"
        log_message "SUCCESS: shadow branch merged to main"
    else
        log_message "ERROR: Failed to push main to origin"
        send_email "AutoTube: Push failed (shadow → main)" \
            "Merge succeeded but push failed.\n\nHost: $HOSTNAME\nTime: $TIMESTAMP\n\nPlease check manually:\nssh $HOSTNAME\ncd /root/autotube\ngit log --oneline -5\ngit push origin main"
    fi
else
    log_message "ERROR: Merge conflict detected!"
    log_message "IMPORTANT: Merge is being ABORTED - nothing is committed or pushed"

    # Get conflict details
    CONFLICTS=$(git diff --name-only --diff-filter=U)
    CURRENT_COMMIT=$(git log -1 --oneline)
    MAIN_LOG=$(git log main --oneline -5)
    SHADOW_LOG=$(git log shadow --oneline -5)

    # ABORT THE MERGE - do NOT complete the merge, just notify user
    log_message "Aborting merge to wait for manual resolution..."
    git merge --abort >> "$LOG_FILE" 2>&1
    log_message "✓ Merge aborted - main branch is unchanged"

    EMAIL_BODY="MERGE CONFLICT DETECTED - MANUAL INTERVENTION REQUIRED

Host: $HOSTNAME
Time: $TIMESTAMP

Conflicted Files:
$CONFLICTS

Current main commit:
$CURRENT_COMMIT

Last 5 commits on main:
$MAIN_LOG

Last 5 commits on shadow:
$SHADOW_LOG

ACTION REQUIRED:
1. SSH into VM: ssh $HOSTNAME
2. Go to repo: cd /root/autotube
3. Check status: git status
4. Resolve conflicts manually: vim <conflicted-file>
5. After resolving: git add . && git commit -m 'Merge shadow into main (manual)'
6. Push: git push origin main

Log file: $LOG_FILE"

    send_email "AutoTube: MERGE CONFLICT - shadow → main (MANUAL ACTION REQUIRED)" "$EMAIL_BODY"

    log_message "CONFLICT: Email sent to $EMAIL"
fi

log_message "=== Merge process complete ==="
