# Memory Tracking & Detailed Logging Implementation

## Date: 2026-04-27
## Purpose: Debug OOM failures during video composition on GCP VM (e2-small 2GB RAM)

---

## Changes Made to `agents/video_agent.py`

### 1. **psutil Import Added** (Line 31)
```python
import psutil
```
- Enables real-time memory usage monitoring
- Added to requirements.txt for dependency tracking

### 2. **Memory Status Helper Function** (Lines 42-51)
```python
def _get_memory_status(label: str = ""):
    """Log current memory usage (RSS, available, percent). Helper for OOM debugging."""
```
- Reports Process RSS (Resident Set Size in MB)
- Reports System Available Memory (MB)
- Reports Total System Memory Usage (%)
- Called at strategic checkpoints throughout render pipeline

---

## Memory Tracking Checkpoints

### Phase 1: Initial Setup
- **RENDER_START** — Entry point to render() method
- **BEFORE_FETCH** — Before fetching section videos
- **AFTER_FETCH** — After all videos downloaded/generated

### Phase 2: Base Video Construction
- **BEFORE_BUILD_BASE** — Before _build_base_video()
- **AFTER_BUILD_BASE** — After base video created
- **SECTION_1_START through SECTION_N_START** — Before loading each section
- **BEFORE_LOAD_CACHED_MP4_SECTION_X** — Before VideoFileClip(cached_mp4)
- **AFTER_LOAD_CACHED_MP4_SECTION_X** — After loading cached MP4
- **BEFORE_LOAD_PEXELS_SECTION_X** — Before VideoFileClip(pexels_clip)
- **AFTER_LOAD_PEXELS_SECTION_X** — After loading Pexels clip
- **BEFORE_ADD_TRANSITIONS** — Before adding dip-to-black transitions
- **BEFORE_CONCATENATE** — Right before concatenate_videoclips() call
- **AFTER_CONCATENATE** — After concatenation completes

### Phase 3: Composition & Audio
- **BEFORE_COMPOSITE** — Before creating CompositeVideoClip
- **BEFORE_COMPOSITEvideoclip** — Before CompositeVideoClip() instantiation
- **AFTER_COMPOSITEvideoclip** — After CompositeVideoClip created
- **AFTER_AUDIO_ATTACH** — After audio attached via with_audio()
- **AFTER_MIX_MUSIC** — After background music mixed

### Phase 4: Encoding
- **BEFORE_WRITE_VIDEOFILE** — Before final FFmpeg encoding
- **AFTER_WRITE_VIDEOFILE** — After video successfully written

### Error Capture
- **OOM_IN_CONCATENATE** — If MemoryError during concatenate_videoclips()
- **OOM_DETECTED** — If MemoryError during write_videofile()
- **ERROR_DURING_WRITE** — Other exceptions during encoding

---

## How to Read the Logs

Look for lines containing `[MEMORY ...]`:
```
2026-04-27 19:52:15,123 [INFO] agents.video_agent: [MEMORY BEFORE_BUILD_BASE] Process RSS: 245.3 MB | System available: 1521.4 MB | Usage: 25.6%
```

**Key Metrics:**
- **Process RSS** = Only AutoTube code using this much memory
- **System available** = Free RAM left on entire machine (includes OS, other processes)
- **Usage** = Total system memory used (25% = 512MB of 2GB on e2-small)

**Interpretation:**
- If Process RSS keeps growing while System available shrinks → Memory leak
- If both stay constant → Likely hitting FFmpeg memory limits, not Python
- Jump in Process RSS after load → Video clip successfully loaded into memory

---

## Expected Memory Profile (e2-small 2GB VM)

When running successfully:
```
RENDER_START:           Process: ~100 MB, System available: ~1800 MB
BEFORE_FETCH:           Process: ~120 MB, System available: ~1750 MB (audio loaded)
AFTER_FETCH:            Process: ~600 MB, System available: ~1300 MB (video files downloaded)
BEFORE_BUILD_BASE:      Process: ~650 MB, System available: ~1250 MB
BEFORE_LOAD_VIDEO_1:    Process: ~650 MB, System available: ~1250 MB
AFTER_LOAD_VIDEO_1:     Process: ~900 MB, System available: ~1000 MB (clip 1 in memory)
AFTER_LOAD_VIDEO_2:     Process: ~1100 MB, System available: ~800 MB (clips 1+2 in memory)
...
BEFORE_CONCATENATE:     Process: ~1400 MB, System available: ~500 MB (all 6-8 clips in memory)
AFTER_CONCATENATE:      Process: ~900 MB, System available: ~1100 MB (released individual clips, now consolidated)
BEFORE_COMPOSITE:       Process: ~950 MB, System available: ~1050 MB
BEFORE_WRITE_VIDEOFILE: Process: ~1000 MB, System available: ~1000 MB
AFTER_WRITE_VIDEOFILE:  Process: ~300 MB, System available: ~1750 MB (cleanup)
```

---

## Troubleshooting Guide

### Scenario 1: OOM Before Concatenation
```
[MEMORY BEFORE_LOAD_VIDEO_5] Process: 1250 MB | System available: 150 MB
[OOM_IN_CONCATENATE] MemoryError during concatenate_videoclips
```
**Diagnosis:** Too many large video clips in memory simultaneously
**Solution:** Switch to Ken Burns mode (free, no large videos), reduce SCRIPT_WORD_COUNT, or upgrade VM

### Scenario 2: OOM During Encoding
```
[MEMORY BEFORE_WRITE_VIDEOFILE] Process: 1400 MB | System available: 100 MB
[OOM_DETECTED] MemoryError during write_videofile
```
**Diagnosis:** FFmpeg encoding needs headroom for temporary buffers
**Solution:** Reduce bitrate from 4000k to 2000k, switch to faster preset, or upgrade VM

### Scenario 3: Memory Leak (Process RSS keeps growing)
```
[MEMORY SECTION_1_END] Process: 950 MB | System available: 1050 MB
[MEMORY SECTION_2_END] Process: 1050 MB | System available: ~950 MB
[MEMORY SECTION_3_END] Process: 1150 MB | System available: ~850 MB
[MEMORY SECTION_4_END] Process: 1250 MB | System available: ~750 MB
```
**Diagnosis:** VideoFileClip objects not being garbage collected
**Solution:** Add `del clip` and `gc.collect()` after appending to section_clips, or run on more RAM

### Scenario 4: Success (Memory stable)
```
[MEMORY BEFORE_CONCATENATE] Process: 1100 MB | System available: 900 MB
[MEMORY AFTER_CONCATENATE] Process: 950 MB | System available: 1050 MB
[MEMORY BEFORE_COMPOSITE] Process: 1050 MB | System available: ~950 MB
[MEMORY AFTER_WRITE_VIDEOFILE] Process: 300 MB | System available: 1750 MB
✓ Video saved: outputs/...
```
**Result:** Pipeline completed successfully

---

## Next Steps

1. **Run test:** `python3 orchestrator.py --dry-run --topic "AI topic"`
2. **Collect logs:** Save full output
3. **Analyze memory checkpoints:** Compare actual vs expected profile above
4. **Identify failure point:** grep for OOM or highest memory usage
5. **Report findings:** Share exact checkpoint and memory values
6. **Choose solution:**
   - **If OOM before concatenate:** Reduce video count or size
   - **If OOM during encoding:** Reduce bitrate or use Ken Burns
   - **If memory stable but video quality poor:** Keep Veo but optimize parameters
   - **If consistently stable:** Problem solved! Ship it.

---

## Code Locations Modified

| File | Method | Lines | Change |
|------|--------|-------|--------|
| `agents/video_agent.py` | `_get_memory_status()` | 42-51 | New function |
| `agents/video_agent.py` | `render()` | 142-268 | Added 15 memory checkpoints |
| `agents/video_agent.py` | `_build_base_video()` | 980-1170 | Added 12 memory checkpoints |
| `requirements.txt` | (global) | 35 | Added `psutil>=5.9.0` |

---

## Memory Efficiency Tips (Future Optimization)

If memory remains problematic even with detailed logging:

1. **Explicit cleanup:** Add `gc.collect()` after major operations
2. **Context managers:** Use `with VideoFileClip(...) as clip:` for auto-cleanup
3. **Sequential processing:** Process sections one at a time instead of all in memory
4. **Temporary files:** Store intermediate clips to disk instead of RAM
5. **Streaming encode:** Use FFmpeg's memory-efficient pipes instead of moviepy buffering

