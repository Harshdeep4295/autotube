#!/bin/bash
# Generate Spanish video
export LANGUAGE=es
export VIDEO_FORMAT=${VIDEO_FORMAT:-landscape}
.venv/bin/python3 orchestrator.py "$@"
