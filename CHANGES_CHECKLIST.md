# Changes Checklist - Avatar Channel Implementation

**Quick reference for all modifications to existing files**

---

## FILE 1: `config.py`

### Location: After line 140 (after VIDEO_ANIMATION_MODE section)

### ADD THESE FIELDS:

```python
# ── Avatar Channel Mode ───────────────────────────────────────────────────────
VIDEO_CHANNEL_MODE: str = field(
    default_factory=lambda: os.getenv("VIDEO_CHANNEL_MODE", "traditional")
)
# Options:
#   "traditional" = pure Veo (current, unchanged)
#   "avatar_pure" = HeyGen only, no B-roll
#   "avatar_hybrid" = HeyGen + Veo B-roll

# ── HeyGen Settings ───────────────────────────────────────────────────────────
HEYGEN_API_KEY: str = field(
    default_factory=lambda: os.getenv("HEYGEN_API_KEY", "")
)

HEYGEN_AVATAR_ID: str = field(
    default_factory=lambda: os.getenv("HEYGEN_AVATAR_ID", "11000001")
)
# Get this from HeyGen dashboard; default is a professional avatar
# Can change per-session by setting env var

HEYGEN_API_URL: str = "https://api.heygen.com/v1"
# Don't change; official HeyGen API endpoint

HEYGEN_WEBHOOK_URL: str = field(
    default_factory=lambda: os.getenv("HEYGEN_WEBHOOK_URL", "")
)
# Optional: webhook for async notifications (can leave empty for polling)

HEYGEN_TIMEOUT_SECONDS: int = 600  # 10 minutes max wait for video generation
```

### WHAT THIS DOES:
- Allows switching channel mode via `VIDEO_CHANNEL_MODE` env var
- Stores HeyGen credentials
- No code changes needed to switch modes — just change env var

---

## FILE 2: `orchestrator.py`

### Location: Line 66 (in `Orchestrator.__init__()`)

### AFTER existing agent initialization, ADD:

```python
# Line 65: self.uploader = None
# ADD BELOW:

self.avatar_mode = config.VIDEO_CHANNEL_MODE
self.avatar_generator = None

# Lazy-load avatar generator if needed
if self.avatar_mode in ["avatar_pure", "avatar_hybrid"]:
    from agents.avatar_agent import AvatarGenerator
    self.avatar_generator = AvatarGenerator()
    self.logger.info(f"Avatar mode: {self.avatar_mode}")
```

### Location: Around line 180 (in `run_pipeline()` method, video generation section)

### REPLACE:

```python
# OLD CODE (around line 180):
# video_path = self.video.render(script, run_id=self.run_id)

# NEW CODE:
if self.avatar_mode == "avatar_pure":
    self.logger.info("Generating pure avatar video...")
    video_path = self.avatar_generator.generate_pure_avatar(script, run_id=self.run_id)
elif self.avatar_mode == "avatar_hybrid":
    self.logger.info("Generating hybrid avatar + Veo video...")
    video_path = self.avatar_generator.generate_hybrid_avatar(script, self.video, run_id=self.run_id)
else:
    # Traditional Veo mode
    self.logger.info("Generating traditional Veo video...")
    video_path = self.video.render(script, run_id=self.run_id)

if not video_path:
    self.logger.error("Video generation failed")
    return None
```

### WHAT THIS DOES:
- Initializes avatar generator if avatar mode is active
- Routes to correct video generation method based on mode
- Gracefully falls back to Veo if avatar fails

---

## FILE 3: `agents/voice_agent.py`

### Location: Line 1-30 (in `VoiceAgent.generate()` method)

### ADD AT VERY START OF METHOD:

```python
def generate(self, script: dict, section_idx: int = 0) -> str | None:
    """Generate voiceover for script section.
    
    Note: Skipped in avatar modes (HeyGen generates audio internally).
    """
    # AVATAR MODE CHECK — ADD THIS:
    if hasattr(config, 'VIDEO_CHANNEL_MODE') and \
       config.VIDEO_CHANNEL_MODE in ["avatar_pure", "avatar_hybrid"]:
        self.logger.info(f"Skipping voice generation (avatar mode generates audio internally)")
        return None
    
    # REST OF EXISTING CODE CONTINUES BELOW...
    # (everything else stays the same)
```

### WHAT THIS DOES:
- Prevents duplicate audio generation
- HeyGen creates audio; no need for edge-tts
- Saves processing time

---

## FILE 4: `.github/workflows/daily_pipeline.yml`

### Location: Line 30-40 (in `env:` section)

### ADD:

```yaml
env:
  ...existing vars...
  VIDEO_CHANNEL_MODE: ${{ vars.VIDEO_CHANNEL_MODE }}
  HEYGEN_API_KEY: ${{ secrets.HEYGEN_API_KEY }}
```

### Location: Secrets & Variables section (GitHub UI)

### Add these in GitHub Actions:

**Secrets (Settings → Secrets and variables → Actions → New repository secret):**
```
Name: HEYGEN_API_KEY
Value: [your HeyGen API key from https://www.heygen.com/api-key]
```

**Variables (Settings → Secrets and variables → Actions → New repository variable):**
```
Name: VIDEO_CHANNEL_MODE
Value: avatar_pure  (or avatar_hybrid, or traditional)
```

---

## FILE 5: `.env` (Local Testing Only)

### ADD TO YOUR LOCAL `.env` FILE:

```bash
# Avatar channel mode (local testing)
VIDEO_CHANNEL_MODE=avatar_pure

# HeyGen API key (get from https://www.heygen.com/api-key)
HEYGEN_API_KEY=your_api_key_here

# Optional: Custom avatar ID (default: 11000001)
HEYGEN_AVATAR_ID=11000001
```

### WHAT THIS DOES:
- Enables avatar mode for local testing
- No need to change code; just env vars

---

## DEPENDENCY INSTALLATION

### Add to `requirements.txt`:

```
heygen-sdk==1.2.0
```

### OR install directly:

```bash
pip install heygen-sdk==1.2.0
```

---

## FILES TO CREATE (New)

These are entirely NEW files — don't modify existing ones:

| File | Size | Purpose |
|------|------|---------|
| `agents/avatar_agent.py` | ~500 lines | Core avatar generation |
| `agents/heygen_client.py` | ~200 lines | HeyGen API wrapper |
| `agents/avatar_compositor.py` | ~300 lines | MoviePy compositing |
| `templates/avatar_prompts.py` | ~150 lines | Prompt templates |
| `tests/test_avatar_pipeline.py` | ~300 lines | Unit tests |

(Full code for these is in IMPLEMENTATION_PLAN_AVATAR_CHANNELS.md — Parts 2.3, 3.3, etc.)

---

## SUMMARY: CHANGES BY FILE

### Modified Files (4 files)
| File | Changes | Lines |
|------|---------|-------|
| `config.py` | Add avatar fields | +25 lines |
| `orchestrator.py` | Add avatar init + mode branching | +20 lines |
| `agents/voice_agent.py` | Add avatar mode check | +7 lines |
| `.github/workflows/daily_pipeline.yml` | Add env vars + secrets | +3 lines |

### New Files (5 files)
| File | Lines |
|------|-------|
| `agents/avatar_agent.py` | ~500 |
| `agents/heygen_client.py` | ~200 |
| `agents/avatar_compositor.py` | ~300 |
| `templates/avatar_prompts.py` | ~150 |
| `tests/test_avatar_pipeline.py` | ~300 |

### Unchanged Files (No changes needed)
- `agents/research_agent.py`
- `agents/script_agent.py`
- `agents/video_agent.py`
- `agents/thumbnail_agent.py`
- `agents/upload_agent.py`
- `agents/gcp_veo_agent.py`
- `agents/kling_video_agent.py`

---

## TESTING CHECKLIST

Before going live:

- [ ] Install heygen-sdk
- [ ] Get HeyGen API key
- [ ] Set `VIDEO_CHANNEL_MODE=avatar_pure` in .env
- [ ] Run `pytest tests/test_avatar_pipeline.py::test_heygen_client_auth`
- [ ] Run dry-run: `python orchestrator.py --dry-run --topic "Test"`
- [ ] Verify video generated in outputs/
- [ ] Play video, check quality
- [ ] Check logs for errors

---

## CONFIG VERIFICATION

After changes, verify config loads correctly:

```bash
python -c "from config import config; print(f'Mode: {config.VIDEO_CHANNEL_MODE}')"
```

Expected output:
```
Mode: avatar_pure
```

---

## ROLLBACK INSTRUCTIONS

If something breaks, to rollback to Veo-only:

```bash
# Set env var back to traditional
export VIDEO_CHANNEL_MODE=traditional

# Or remove the env var entirely (defaults to "traditional")
unset VIDEO_CHANNEL_MODE

# Run pipeline
python orchestrator.py --dry-run
```

No code changes needed — just env var change.

---

## VERSION CONTROL

**Recommended commit message:**

```
feat: add avatar channel support (Pure HeyGen + Hybrid modes)

- Implement HeyGen API client (heygen_client.py)
- Add avatar generation agent (avatar_agent.py)
- Add MoviePy compositing for hybrid mode (avatar_compositor.py)
- Modify config.py to support VIDEO_CHANNEL_MODE
- Modify orchestrator.py to branch on avatar mode
- Skip voice generation in avatar modes
- Add comprehensive tests

Supports:
- avatar_pure: HeyGen only (fast, simple)
- avatar_hybrid: HeyGen + Veo B-roll (cinematic)
- traditional: Veo only (existing behavior)

All modes switchable via env var.
```

---

**Next: Review this document + IMPLEMENTATION_PLAN_AVATAR_CHANNELS.md, then proceed to implementation.**

