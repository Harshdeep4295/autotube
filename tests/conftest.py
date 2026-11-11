import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("FREE_ONLY", "true")
os.environ.setdefault("VIDEO_STYLE", "explainer")
os.environ.setdefault("EXPLAINER_TRENDS", "false")   # no network in tests; test_trends turns it on
os.environ.setdefault("TOPIC_INDEX", "false")        # no model download; test_week_plan uses a fake embedder
os.environ.setdefault("WEEK_PLAN", "false")          # the repo's real plan must not steer other tests
os.environ.setdefault("TOPIC_JUDGE", "false")        # no AI calls; test_topic_judge turns it on with a fake
