# FFmpeg Filter Recipes for AutoTube

Ready-to-use FFmpeg filter expressions for implementing video improvements.

---

## Table of Contents

1. [Motion Effects (Zoompan)](#motion-effects-zoompan)
2. [Color Grading (Curves)](#color-grading-curves)
3. [Transitions (Xfade)](#transitions-xfade)
4. [Audio Processing](#audio-processing)
5. [Composite Filters](#composite-filters)

---

## Motion Effects (Zoompan)

All expressions assume:
- `N` = total frame count (replace at runtime: `N = int(fps * duration)`)
- `iw` / `ih` = input width/height
- `d` = frame count per section
- `fps` = frames per second (usually 30)

### Basic Zoom

```ffmpeg
# Zoom in (1.0x → 1.15x)
zoompan=z='min(1+0.15*on/N,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30

# Zoom out (1.15x → 1.0x)
zoompan=z='max(1.15-0.15*on/N,1.0)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30
```

### Corner Zooms

```ffmpeg
# Zoom in + stay top-left
zoompan=z='min(1+0.15*on/N,1.15)':x='0':y='0':d=N:s=1920x1080:fps=30

# Zoom in + stay top-right
zoompan=z='min(1+0.15*on/N,1.15)':x='iw-iw/zoom':y='0':d=N:s=1920x1080:fps=30

# Zoom in + stay bottom-left
zoompan=z='min(1+0.15*on/N,1.15)':x='0':y='ih-ih/zoom':d=N:s=1920x1080:fps=30

# Zoom in + stay bottom-right
zoompan=z='min(1+0.15*on/N,1.15)':x='iw-iw/zoom':y='ih-ih/zoom':d=N:s=1920x1080:fps=30
```

### Linear Pans

```ffmpeg
# Pan right (1.15x zoom, move from left to right)
zoompan=z='1.15':x='(on/N)*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30

# Pan left
zoompan=z='1.15':x='(1-on/N)*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30

# Pan up
zoompan=z='1.15':x='iw/2-(iw/zoom/2)':y='(1-on/N)*(ih-ih/zoom)':d=N:s=1920x1080:fps=30

# Pan down
zoompan=z='1.15':x='iw/2-(iw/zoom/2)':y='(on/N)*(ih-ih/zoom)':d=N:s=1920x1080:fps=30

# Pan right (slow)
zoompan=z='1.08':x='(on/N)*(iw-iw/zoom)*0.5':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30
```

### Diagonal Drifts

```ffmpeg
# Drift top-right
zoompan=z='1.15':x='(on/N)*(iw-iw/zoom)*0.5':y='(1-on/N)*(ih-ih/zoom)*0.5':d=N:s=1920x1080:fps=30

# Drift bottom-left
zoompan=z='1.15':x='(1-on/N)*(iw-iw/zoom)*0.5':y='(on/N)*(ih-ih/zoom)*0.5':d=N:s=1920x1080:fps=30

# Drift top-left
zoompan=z='1.15':x='(1-on/N)*(iw-iw/zoom)*0.5':y='(1-on/N)*(ih-ih/zoom)*0.5':d=N:s=1920x1080:fps=30

# Drift bottom-right
zoompan=z='1.15':x='(on/N)*(iw-iw/zoom)*0.5':y='(on/N)*(ih-ih/zoom)*0.5':d=N:s=1920x1080:fps=30
```

### **NEW: Swing Pan (Sine-wave Oscillation)**

```ffmpeg
# Swing pan right (sine wave motion)
zoompan=z='1.12':x='iw/2-(iw/zoom/2)+sin(on/80)*80':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30

# Swing pan left
zoompan=z='1.12':x='iw/2-(iw/zoom/2)+sin(on/80)*-80':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30

# Swing pan up-down
zoompan=z='1.12':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)+sin(on/100)*60':d=N:s=1920x1080:fps=30
```

### **NEW: Spiral / Lissajous Curves**

```ffmpeg
# Spiral out (combine x + y sine/cosine at different frequencies)
zoompan=z='min(1+0.12*on/N,1.12)':x='iw/2-(iw/zoom/2)+cos(2*pi*on/N)*80':y='ih/2-(ih/zoom/2)+sin(3*pi*on/N)*60':d=N:s=1920x1080:fps=30

# Spiral inward (reverse zoom + spiral)
zoompan=z='max(1.12-0.12*on/N,1.0)':x='iw/2-(iw/zoom/2)+cos(2*pi*on/N)*80':y='ih/2-(ih/zoom/2)+sin(3*pi*on/N)*60':d=N:s=1920x1080:fps=30

# Lissajous (3:2 ratio, more complex shape)
zoompan=z='1.15':x='iw/2-(iw/zoom/2)+cos(3*pi*on/N)*100':y='ih/2-(ih/zoom/2)+sin(2*pi*on/N)*80':d=N:s=1920x1080:fps=30
```

### **NEW: Reverse Zoom (Zoom Out)**

```ffmpeg
# Zoom out slow (1.2x → 1.0x)
zoompan=z='max(1.2-0.08*on/N,1.0)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30

# Zoom out dramatic (2.0x → 1.0x, reveals larger context)
zoompan=z='max(2.0-1*on/N,1.0)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30
```

### **NEW: Parallax-like (Multi-speed Motion)**

```ffmpeg
# Pan slow + zoom in slow (feel of depth)
zoompan=z='min(1+0.08*on/N,1.08)':x='(on/N)*(iw-iw/zoom)*0.3':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30

# Pan fast + zoom in slow
zoompan=z='min(1+0.08*on/N,1.08)':x='(on/N)*(iw-iw/zoom)*0.8':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30
```

### Combined Zoom + Pan

```ffmpeg
# Zoom in + drift right
zoompan=z='min(1+0.12*on/N,1.12)':x='iw/2-(iw/zoom/2)+(on/N)*50':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30

# Zoom out + drift left
zoompan=z='max(1.12-0.12*on/N,1.0)':x='iw/2-(iw/zoom/2)+(1-on/N)*50':y='ih/2-(ih/zoom/2)':d=N:s=1920x1080:fps=30
```

---

## Color Grading (Curves)

### Curves Filter Syntax

```ffmpeg
# Basic curves: control exposure by lifting/darkening tones
curves=all='0/y0 0.5/ymid 1/y1'

# RGB channels separately
curves=r='0/r0 1/r1':g='0/g0 1/g1':b='0/b0 1/b1'

# Lift blacks, hold whites (standard S-curve)
curves=all='0/0.05 0.5/0.5 1/1'
```

### Niche-Specific Color Chains

```ffmpeg
# AI & Tech (cool, electric, high contrast)
curves=all='0/0 0.5/0.4 1/1',saturation=1.15,hue=15

# Finance (warm, trustworthy, professional)
curves=b='0/0.1 0.5/0.5 1/1',saturation=1.05,hue=-10

# Health (bright, clean, energetic)
curves=all='0/0 0.5/0.55 1/1',saturation=1.25,brightness=0.05

# History (slightly warm, vintage, desaturated)
curves=all='0/0.05 0.5/0.5 1/1',saturation=0.95,hue=10

# Business (neutral, professional)
curves=all='0/0 0.5/0.5 1/1',saturation=1.10,hue=5

# English Learning (vibrant, engaging)
curves=all='0/0 0.5/0.5 1/1',saturation=1.20,hue=0
```

### Individual Curves Components

```ffmpeg
# Lift blacks (make image brighter, less crushed)
curves=all='0/0.1 1/1'

# Darken shadows
curves=all='0/0 0.5/0.4 1/1'

# Standard S-curve (increase contrast)
curves=all='0/0.05 0.5/0.5 1/0.95'

# Boost blue (cool)
curves=b='0/0 1/1.1'

# Boost red (warm)
curves=r='0/0 1/1.1'

# Reduce blue (warm/yellow shift)
curves=b='0/0 1/0.9'

# Reduce red (cool/cyan shift)
curves=r='0/0 1/0.9'
```

### Saturation and Hue

```ffmpeg
# Increase saturation (+15%)
saturation=1.15

# Decrease saturation (desaturate)
saturation=0.8

# Hue shift (positive = shift towards red, negative = shift towards cyan)
hue=15        # Shift towards red/warm
hue=-10       # Shift towards cyan/cool

# Brightness
brightness=0.05     # Make 5% brighter
brightness=-0.05    # Make 5% darker

# Contrast
contrast=1.2        # Increase contrast by 20%
contrast=0.8        # Decrease contrast
```

### Complete Color Grade Examples

```ffmpeg
# Professional color grade (high quality)
curves=all='0/0.02 0.5/0.48 1/0.98',saturation=1.08,hue=2,contrast=1.05

# Cinematic warm
curves=all='0/0 0.5/0.5 1/1',saturation=1.15,hue=-15,brightness=0.02

# Cinematic cool (sci-fi)
curves=all='0/0.05 0.5/0.4 1/1',saturation=1.15,hue=20,brightness=-0.02
```

---

## Transitions (Xfade)

### Basic Cross-Fade

```ffmpeg
# Cross-fade between two videos (1 second fade at 8 second offset)
ffmpeg -i clip1.mp4 -i clip2.mp4 \
  -filter_complex "[0][1]xfade=transition=fade:duration=1:offset=8" \
  -pix_fmt yuv420p output.mp4
```

### Transition Types

```ffmpeg
# Fade (simple opacity cross-fade)
xfade=transition=fade:duration=0.5:offset=4.5

# Wipe left
xfade=transition=wipeleft:duration=0.5:offset=4.5

# Wipe right
xfade=transition=wiperight:duration=0.5:offset=4.5

# Wipe up
xfade=transition=wipeup:duration=0.5:offset=4.5

# Wipe down
xfade=transition=wipedown:duration=0.5:offset=4.5

# Slide left
xfade=transition=slideleft:duration=0.5:offset=4.5

# Slide right
xfade=transition=slideright:duration=0.5:offset=4.5

# Slide up
xfade=transition=slideup:duration=0.5:offset=4.5

# Slide down
xfade=transition=slidedown:duration=0.5:offset=4.5

# Reveal left
xfade=transition=revealleft:duration=0.5:offset=4.5

# Reveal right
xfade=transition=revealright:duration=0.5:offset=4.5

# Dip to black (fade to black then to next clip)
xfade=transition=smoothleft:duration=0.3:offset=4.7
```

### Multiple Clips with Transitions

```ffmpeg
# Chain 3 clips with cross-fades
ffmpeg -i clip1.mp4 -i clip2.mp4 -i clip3.mp4 \
  -filter_complex "[0][1]xfade=transition=fade:duration=0.5:offset=4.5[v01]; \
                   [v01][2]xfade=transition=fade:duration=0.5:offset=9.5[v]" \
  -map "[v]" -map "[a]" output.mp4
```

---

## Audio Processing

### Voice Clarity (EQ + Compression)

```ffmpeg
# Boost voice presence (2kHz), compress peaks, normalize
ffmpeg -i audio.mp3 \
  -af "equalizer=f=2000:g=3:q=1.5,acompressor=threshold=-20:ratio=3,loudnorm" \
  -c:a aac output.mp3

# Gentler EQ (less boost)
ffmpeg -i audio.mp3 \
  -af "equalizer=f=2000:g=2:q=1.0,acompressor=threshold=-15:ratio=2,loudnorm" \
  -c:a aac output.mp3
```

### Music Processing

```ffmpeg
# High-pass filter (remove bass rumble, clean up for voice mix)
ffmpeg -i music.mp3 \
  -af "highpass=f=100:poles=2" \
  -c:a aac output.mp3

# High-pass + fade out
ffmpeg -i music.mp3 \
  -af "highpass=f=100:poles=2,afade=t=out:st=7:d=1" \
  -c:a aac output.mp3
```

### Reverb (Subtle Spaciousness)

```ffmpeg
# Add subtle reverb to voice (0.8/0.9 echo, 500ms decay, 0.3 feedback)
# Note: requires aecho filter (more hardware-efficient than true reverb)
ffmpeg -i audio.mp3 \
  -af "areverse,aecho=0.8:0.9:500:0.3,areverse" \
  -c:a aac output.mp3
```

### Loudness Normalization (LUFS)

```ffmpeg
# Broadcast-standard loudness normalization
ffmpeg -i audio.mp3 \
  -af "loudnorm=I=-23:TP=-1.5:LRA=11" \
  -c:a aac output.mp3

# More aggressive (louder)
ffmpeg -i audio.mp3 \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" \
  -c:a aac output.mp3
```

### Complete Audio Chain

```ffmpeg
# Voice + Music mix with professional processing
ffmpeg -i voiceover.mp3 -i music.mp3 \
  -filter_complex "[0]equalizer=f=2000:g=3:q=1.5,acompressor=threshold=-20:ratio=3[v]; \
                   [1]highpass=f=100:poles=2[m]; \
                   [v][m]amix=inputs=2:duration=shortest,loudnorm" \
  -c:a aac output.mp3
```

---

## Composite Filters

### Combining Motion + Color

```ffmpeg
# Zoom + color grade in single FFmpeg call
ffmpeg -loop 1 -i image.jpg -t 8 \
  -vf "zoompan=z='min(1+0.15*on/240,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=240:s=1920x1080:fps=30, \
       curves=all='0/0 0.5/0.4 1/1',saturation=1.15,hue=15" \
  -c:v libx264 -preset ultrafast output.mp4
```

### Watermark + Fade Animation

```ffmpeg
# Add watermark with fade-in
ffmpeg -i video.mp4 -i watermark.png \
  -filter_complex "[1]fade=t=in:st=0:d=0.5[wm]; \
                   [0][wm]overlay=x=32:y=32:alpha=1[v]" \
  -map "[v]" -map "0:a" output.mp4
```

### Chroma Key (Green Screen Removal)

```ffmpeg
# If needed for text/graphics with transparent backgrounds
ffmpeg -i video_with_bg.mp4 \
  -vf "chromakey=color=green:similarity=0.1:blend=0.1" \
  -c:v libx264 output.mp4
```

---

## Python Integration Examples

### Using subprocess to run FFmpeg filters

```python
import subprocess

def apply_ffmpeg_filter(input_path: str, filter_str: str, output_path: str) -> bool:
    """Run FFmpeg filter on video."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr.decode()}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("FFmpeg timeout")
        return False

# Usage:
filter_str = "curves=all='0/0 0.5/0.4 1/1',saturation=1.15,hue=15"
apply_ffmpeg_filter("input.mp4", filter_str, "output.mp4")
```

### Building dynamic filter expressions

```python
def build_motion_filter(effect_dict: dict, fps: int, duration: float) -> str:
    """Build FFmpeg zoompan filter from effect dict."""
    n_frames = int(fps * duration)
    
    # Replace "N" placeholder with actual frame count
    z = effect_dict["z"].replace("N", str(n_frames))
    x = effect_dict["x"].replace("N", str(n_frames))
    y = effect_dict["y"].replace("N", str(n_frames))
    
    return (
        f"zoompan=z='{z}':x='{x}':y='{y}':"
        f"d={n_frames}:s=1920x1080:fps={fps}"
    )

# Usage:
effect = {"z": "min(1+0.15*on/N,1.15)", "x": "iw/2-(iw/zoom/2)", "y": "ih/2-(ih/zoom/2)"}
filter_str = build_motion_filter(effect, fps=30, duration=8.0)
# Output: "zoompan=z='min(1+0.15*on/240,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=240:s=1920x1080:fps=30"
```

---

## Testing Filters

### Quick test (5 second clip)

```bash
# Test motion effect
ffmpeg -loop 1 -i test_image.jpg -t 5 \
  -vf "zoompan=z='min(1+0.15*on/150,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1920x1080:fps=30" \
  -c:v libx264 -preset ultrafast test_motion.mp4

# Test color grade
ffmpeg -i input.mp4 -t 5 \
  -vf "curves=all='0/0 0.5/0.4 1/1',saturation=1.15,hue=15" \
  test_color.mp4

# Test audio
ffmpeg -i input.mp3 \
  -af "equalizer=f=2000:g=3:q=1.5,acompressor=threshold=-20:ratio=3" \
  test_audio.mp3
```

### Verify filter without encoding

```bash
# Parse filter without encoding (faster, just validates syntax)
ffmpeg -f lavfi -i color=c=black:s=1920x1080:d=1 \
  -vf "zoompan=z='min(1+0.15*on/30,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=30:s=1920x1080:fps=30" \
  -f null -

# Exit code 0 = filter is valid
# Exit code != 0 = syntax error
```

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| "Unknown filter" | Typo in filter name | Check FFmpeg docs for correct name |
| "Invalid expression" | Bad math in filter param | Escape quotes: `'expr'` not `expr` |
| "N: Undefined variable" | Using "N" in expression without replacing | Replace "N" at runtime with frame count |
| "Output would be empty" | Filter chain broken | Add intermediate labels: `[v1][v2]overlay[out]` |
| Audio too quiet | Volume not set | Add `,volume=2.0` to audio filter |
| Video distorted | Wrong aspect ratio | Use `scale=1920:1080:force_original_aspect_ratio=decrease` |
| Slow encoding | CRF/preset too high quality | Use `-preset ultrafast -crf 23` |

---

## Quick Recipes (Copy-Paste Ready)

### Hook Title (static image → 8s cinematic video)
```bash
ffmpeg -loop 1 -i hook_title.jpg -t 8 \
  -vf "zoompan=z='min(1+0.12*on/240,1.12)':x='iw/2-(iw/zoom/2)+sin(on/80)*50':y='ih/2-(ih/zoom/2)':d=240:s=1920x1080:fps=30, \
       curves=all='0/0 0.5/0.4 1/1',saturation=1.15,hue=15" \
  -c:v libx264 -preset ultrafast -crf 23 -pix_fmt yuv420p hook.mp4
```

### Section B-Roll (Pexels clip + color grade)
```bash
ffmpeg -i pexels_clip.mp4 -t 5 \
  -vf "curves=all='0/0 0.5/0.4 1/1',saturation=1.15,hue=15" \
  -c:v libx264 -preset ultrafast output.mp4
```

### Voice + Music Mix
```bash
ffmpeg -i voice.mp3 -i music.mp3 \
  -filter_complex "[0]equalizer=f=2000:g=3:q=1.5,acompressor=threshold=-20:ratio=3[v]; \
                   [1]highpass=f=100:poles=2[m]; \
                   [v][m]amix=inputs=2:duration=shortest" \
  -c:a aac final_audio.mp3
```

---

These recipes are production-ready. Test each on a small sample before full production use.
