#!/bin/bash
"""
AutoTube Batch Upload Launcher
Runs batch_upload.py in a persistent tmux session with live logging.

Usage:
    ./run_batch.sh                                          # Default: 5 videos, 5h apart, start in 5.5h
    ./run_batch.sh --count 10 --publish-delay 24           # 10 videos, daily
    ./run_batch.sh --count 3 --dry-run                     # Test mode
    ./run_batch.sh --count 5 --start-offset 0              # First video publishes NOW
"""

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config
SESSION_NAME="autotube-batch"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/batch_upload.log"

# Default args
COUNT=5
PUBLISH_DELAY=5
START_OFFSET=5.5
DRY_RUN=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --count) COUNT="$2"; shift 2 ;;
        --publish-delay) PUBLISH_DELAY="$2"; shift 2 ;;
        --start-offset) START_OFFSET="$2"; shift 2 ;;
        --dry-run) DRY_RUN="--dry-run"; shift ;;
        --help) show_help; exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

show_help() {
    echo "Usage: ./run_batch.sh [options]"
    echo ""
    echo "Options:"
    echo "  --count N              Number of videos (default: 5)"
    echo "  --publish-delay H      Hours between publishes (default: 5)"
    echo "  --start-offset H       First publish delay (default: 5.5)"
    echo "  --dry-run              Test mode (no upload)"
    echo "  --help                 Show this help"
    echo ""
    echo "Examples:"
    echo "  ./run_batch.sh --count 10 --publish-delay 24"
    echo "  ./run_batch.sh --count 3 --dry-run"
}

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ python3 not found${NC}"
    exit 1
fi

# Check tmux
if ! command -v tmux &> /dev/null; then
    echo -e "${YELLOW}⚠️  tmux not found. Installing...${NC}"
    if command -v brew &> /dev/null; then
        brew install tmux
    else
        echo -e "${RED}✗ Please install tmux: brew install tmux${NC}"
        exit 1
    fi
fi

# Kill old session if exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "${YELLOW}Killing existing session: $SESSION_NAME${NC}"
    tmux kill-session -t "$SESSION_NAME"
fi

# Create new session
echo -e "${BLUE}Creating tmux session: $SESSION_NAME${NC}"
tmux new-session -d -s "$SESSION_NAME" -c "$SCRIPT_DIR"

# Build command
CMD=".venv/bin/python3 batch_upload.py --count $COUNT --publish-delay $PUBLISH_DELAY --start-offset $START_OFFSET $DRY_RUN"

# Run in session with logging
echo -e "${BLUE}Starting batch upload...${NC}"
tmux send-keys -t "$SESSION_NAME" "$CMD | tee $LOG_FILE" Enter

# Wait a bit for output
sleep 2

# Show status
echo ""
echo -e "${GREEN}✓ Batch upload started in tmux session!${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Videos: $COUNT"
echo "  Publish delay: ${PUBLISH_DELAY}h"
echo "  First publish: ${START_OFFSET}h from now"
echo "  Mode: $([ -z "$DRY_RUN" ] && echo "LIVE (upload to YouTube)" || echo "DRY RUN (test only)")"
echo ""
echo -e "${BLUE}Session Management:${NC}"
echo "  View live output:     tmux attach -t $SESSION_NAME"
echo "  Detach (Ctrl+B → D):  Keep session running in background"
echo "  Kill session:         tmux kill-session -t $SESSION_NAME"
echo "  Check logs:           tail -f $LOG_FILE"
echo ""
echo -e "${GREEN}Starting terminal view...${NC}"
echo ""

# Auto-attach to session
tmux attach -t "$SESSION_NAME"
