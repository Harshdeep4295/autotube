#!/bin/bash
# Generate Hindi video
export LANGUAGE=hi
export VIDEO_FORMAT=${VIDEO_FORMAT:-landscape}
.venv/bin/python3 orchestrator.py "$@"
