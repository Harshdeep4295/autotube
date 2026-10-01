"""
POC — AI-generated video clips with Wan 2.1 (open weights, Apache-2.0), for a FREE cloud GPU.

UNTESTED: written for a Kaggle / Colab GPU notebook; it could not be run in the sandbox
it was written in (no GPU, Hugging Face blocked). Expect to fix small things on first run.

Where to run it (free):
  • Kaggle notebook → Settings → Accelerator "GPU T4 x2" (≈30 free GPU hours/week), Internet ON
  • Google Colab → Runtime → Change runtime type → T4 GPU (free tier, session limits apply)

In the notebook:
  !pip install -q "diffusers>=0.33" transformers accelerate ftfy imageio imageio-ffmpeg
  !python wan_clips.py sample_script.json --out out --limit 4

Each shot's visual prompt becomes one 5-second 832x480 clip (81 frames @ 16fps).
Download the out/ folder. Using the clips in a video is Phase B work (an `ai_clip` scene in
video/explainer); see docs/PLAN_EXPLAINER_AND_AI_VIDEO.md.

Cost reality: a clip takes minutes on a free T4, so a whole 8-minute video (~80 shots)
is not practical daily on free GPUs. Use AI clips for the hook and a few key moments.
"""

import argparse
import json
from pathlib import Path

import torch
from diffusers import AutoencoderKLWan, WanPipeline
from diffusers.utils import export_to_video

MODEL_ID = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
NEGATIVE = ("blurry, low quality, distorted, deformed hands, extra fingers, text, watermark, "
            "logo, subtitles, static frame, jpeg artifacts")
STYLE = ", cinematic, smooth camera motion, soft natural light, high detail"


def prompt_for(shot: dict) -> str:
    v = shot.get("visual", {})
    base = v.get("prompt") or v.get("query") or v.get("headline") or shot["text"]
    return base + STYLE


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("script", type=Path)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--limit", type=int, default=4, help="how many shots to generate (start small)")
    ap.add_argument("--steps", type=int, default=30)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    # T4/P100 have no fast bfloat16 — use float16 there; the VAE stays in float32 for stability.
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    vae = AutoencoderKLWan.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanPipeline.from_pretrained(MODEL_ID, vae=vae, torch_dtype=dtype)
    pipe.enable_model_cpu_offload()   # keeps peak VRAM low enough for a 16 GB T4

    shots = json.loads(a.script.read_text())["shots"][: a.limit]
    for i, shot in enumerate(shots):
        dest = a.out / f"clip_{i:02d}.mp4"
        if dest.exists():
            print(f"skip {dest} (exists)")
            continue
        prompt = prompt_for(shot)
        print(f"[{i+1}/{len(shots)}] {prompt[:90]}")
        frames = pipe(
            prompt=prompt, negative_prompt=NEGATIVE,
            height=480, width=832, num_frames=81,
            guidance_scale=5.0, num_inference_steps=a.steps,
            generator=torch.Generator("cuda").manual_seed(1000 + i),
        ).frames[0]
        export_to_video(frames, str(dest), fps=16)
        print(f"  saved {dest}")


if __name__ == "__main__":
    main()
