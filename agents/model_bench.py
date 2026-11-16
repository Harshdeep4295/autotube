"""
Real test of a new model on new-model ("trend") days: the channel runs it itself and the video
reports what it measured, instead of only repeating the model card.

  1. find a ready-made GGUF copy of the model on Hugging Face (the most downloaded repo whose name
     matches), and in it the best quantization that fits this computer (Q4_K_M first, smaller ones after)
  2. download llama.cpp's prebuilt Linux build (latest GitHub release) and the GGUF file
  3. llama-bench: prompt reading and answer writing speed (tokens per second); peak memory from
     /usr/bin/time

The result becomes a "MEASURED BY THIS CHANNEL" block at the top of the script's source text, so the
script can use the numbers and the number check accepts them. When even the smallest file is too big
for this computer, the block says so with the file sizes (that is a finding too). Anything that goes
wrong returns None and the video is made as before: a test never fails the run.

    python -m agents.model_bench Qwen/Qwen3-0.6B        # try it by hand
"""

import io
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import requests

from config import config

logger = logging.getLogger(__name__)

HF = "https://huggingface.co"
LLAMA_RELEASES = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10"
QUANTS = ("Q4_K_M", "Q4_K_S", "IQ4_XS", "Q4_0", "Q3_K_M", "IQ3_M", "Q3_K_S", "Q2_K", "IQ2_M", "IQ2_XS")
TRUSTED = ("unsloth", "bartowski", "lmstudio-community", "ggml-org", "mradermacher", "qwen", "google")
HEADERS = {"User-Agent": "AutoTube/1.0"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _get(url: str, **kw):
    r = requests.get(url, timeout=30, headers=HEADERS, **kw)
    r.raise_for_status()
    return r.json()


def gguf_repos(model_id: str) -> List[str]:
    """GGUF repos of this model, best first: the lab's own, then well-known quantizers, by downloads."""
    name = model_id.split("/")[-1]
    want = _norm(name)
    found = _get(f"{HF}/api/models", params={"search": name, "filter": "gguf", "sort": "downloads",
                                             "direction": "-1", "limit": 30})
    repos = [m["id"] for m in found if want in _norm(m["id"].split("/")[-1])]
    lab = model_id.split("/")[0].lower()
    return sorted(repos, key=lambda r: (r.split("/")[0].lower() != lab,
                                        r.split("/")[0].lower() not in TRUSTED, repos.index(r)))


def gguf_files(repo: str) -> List[Dict]:
    """Single-file model GGUFs in a repo: [{path, size, quant}] (split files and vision adapters left out)."""
    tree = _get(f"{HF}/api/models/{repo}/tree/main", params={"recursive": "true"})
    out = []
    for f in tree:
        path = f.get("path", "")
        if not path.lower().endswith(".gguf") or "mmproj" in path.lower() or re.search(r"-\d{5}-of-\d{5}", path):
            continue
        size = int((f.get("lfs") or {}).get("size") or f.get("size") or 0)
        quant = next((q for q in QUANTS if q.lower() in path.lower()), None)
        out.append({"path": path, "size": size, "quant": quant})
    return out


def choose(files: List[Dict], max_bytes: int) -> Optional[Dict]:
    """The best quantization that fits, in QUANTS order."""
    for q in QUANTS:
        for f in sorted(files, key=lambda f: f["size"]):
            if f["quant"] == q and 0 < f["size"] <= max_bytes:
                return f
    return None


def _work_dir() -> Path:
    """The writable disk with the most free space (GitHub runners have a big /mnt)."""
    spots = [Path(tempfile.gettempdir())] + [Path("/mnt")] * os.access("/mnt", os.W_OK)
    best = max(spots, key=lambda p: shutil.disk_usage(p).free)
    return Path(tempfile.mkdtemp(prefix="bench_", dir=best))


def llama_bench(work: Path) -> Path:
    """The llama-bench binary from llama.cpp's latest prebuilt Ubuntu x64 release."""
    hdr = dict(HEADERS)
    if os.getenv("GITHUB_TOKEN"):
        hdr["Authorization"] = f"Bearer {os.getenv('GITHUB_TOKEN')}"
    # the newest numbered build that has the plain CPU Linux file ("latest" can be a placeholder release)
    rels = requests.get(LLAMA_RELEASES, timeout=30, headers=hdr).json()
    rel, asset = next((r, a) for r in rels for a in r.get("assets", [])
                      if re.fullmatch(r"llama-b\d+-bin-ubuntu-x64\.(zip|tar\.gz)", a["name"]))
    data = requests.get(asset["browser_download_url"], timeout=300, headers=HEADERS).content
    dest = work / "llama"
    if asset["name"].endswith(".zip"):
        zipfile.ZipFile(io.BytesIO(data)).extractall(dest)
    else:
        tarfile.open(fileobj=io.BytesIO(data), mode="r:gz").extractall(dest, filter="data")
    binary = next(dest.rglob("llama-bench"))
    for f in binary.parent.iterdir():
        f.chmod(0o755)
    logger.info(f"[bench] llama.cpp {rel.get('tag_name')}")
    return binary


def download(repo: str, path: str, dest: Path) -> Path:
    out = dest / Path(path).name
    with requests.get(f"{HF}/{repo}/resolve/main/{path}", stream=True, timeout=60, headers=HEADERS) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
    return out


def machine() -> Dict:
    ram_kb = next((int(l.split()[1]) for l in open("/proc/meminfo") if l.startswith("MemTotal")), 0)
    return {"cores": os.cpu_count() or 0, "ram_gb": round(ram_kb / 1024 / 1024)}


def measure(binary: Path, model: Path, threads: int) -> Dict:
    """Prompt reading and answer writing speed (tokens/s) and peak memory (GB)."""
    cmd = [str(binary), "-m", str(model), "-p", "256", "-n", "64", "-r", "2", "-t", str(threads), "-o", "json"]
    timed = ["/usr/bin/time", "-v"] + cmd if Path("/usr/bin/time").exists() else cmd
    r = subprocess.run(timed, capture_output=True, text=True, timeout=config.MODEL_BENCH_TIMEOUT,
                       env={**os.environ, "LD_LIBRARY_PATH": str(binary.parent)})
    if r.returncode != 0:
        raise RuntimeError(f"llama-bench exited {r.returncode}: {r.stderr[-300:]}")
    rows = json.loads(r.stdout[r.stdout.find("["):])
    read = next(x["avg_ts"] for x in rows if x.get("n_prompt") and not x.get("n_gen"))
    write = next(x["avg_ts"] for x in rows if x.get("n_gen") and not x.get("n_prompt"))
    peak = re.search(r"Maximum resident set size \(kbytes\): (\d+)", r.stderr)
    return {"read_tps": round(read, 1), "write_tps": round(write, 1),
            "peak_gb": round(int(peak.group(1)) / 1024 / 1024, 1) if peak else None}


def weights_gb(model_id: str) -> float:
    """Total size of the model's original weight files (safetensors / bin), in GB."""
    tree = _get(f"{HF}/api/models/{model_id}/tree/main", params={"recursive": "true"})
    size = sum(int((f.get("lfs") or {}).get("size") or f.get("size") or 0) for f in tree
               if f.get("path", "").endswith((".safetensors", ".bin")))
    return round(size / 1024**3, 1)


def too_big_without_gguf(model_id: str) -> Optional[Dict]:
    """No compressed copy yet: when the original files alone are bigger than this computer's memory,
    that is still a real finding ("needs more than N GB"); otherwise there is nothing to report."""
    full = weights_gb(model_id)
    box = machine()
    if full <= box["ram_gb"]:
        logger.info(f"[bench] no GGUF copy of {model_id} yet ({full} GB original files) — no test")
        return None
    logger.info(f"[bench] no GGUF copy of {model_id} yet; original files {full} GB > {box['ram_gb']} GB RAM")
    return {"model": model_id, "repo": model_id, **box, "fits": False, "no_gguf": True, "full_gb": full}


def run(model_id: str) -> Optional[Dict]:
    """Test the model on this computer. None when there is nothing to report."""
    started = time.time()
    work = None
    try:
        repos = gguf_repos(model_id)
        if not repos:
            return too_big_without_gguf(model_id)
        repo, files = next(((r, f) for r in repos[:4] if (f := gguf_files(r))), (None, []))
        if not files:
            logger.info(f"[bench] no single-file GGUF of {model_id} — no test")
            return None
        box = machine()
        work = _work_dir()
        room = min(config.MODEL_BENCH_MAX_GB * 1024**3, shutil.disk_usage(work).free - 2 * 1024**3)
        pick = choose(files, int(room))
        base = {"model": model_id, "repo": repo, **box}
        if not pick:
            q4 = choose(files, 10**15)
            smallest = min((f for f in files if f["size"]), key=lambda f: f["size"], default=None)
            logger.info(f"[bench] {model_id}: too big for this computer (smallest file "
                        f"{smallest['size'] / 1024**3 if smallest else 0:.0f} GB)")
            return {**base, "fits": False,
                    "q4_gb": round(q4["size"] / 1024**3, 1) if q4 else None, "q4_quant": q4["quant"] if q4 else None,
                    "smallest_gb": round(smallest["size"] / 1024**3, 1) if smallest else None,
                    "smallest_quant": smallest["quant"] if smallest else None}
        logger.info(f"[bench] testing {repo}/{pick['path']} ({pick['size'] / 1024**3:.1f} GB) on "
                    f"{box['cores']} cores, {box['ram_gb']} GB RAM")
        binary = llama_bench(work)
        model = download(repo, pick["path"], work)
        got = measure(binary, model, threads=box["cores"])
        result = {**base, "fits": True, "file": pick["path"], "quant": pick["quant"],
                  "size_gb": round(pick["size"] / 1024**3, 1), **got, "seconds": round(time.time() - started)}
        logger.info(f"[bench] {pick['quant']}: reads {got['read_tps']} tok/s, writes {got['write_tps']} tok/s, "
                    f"peak {got['peak_gb']} GB ({result['seconds']} s)")
        return result
    except Exception as e:  # noqa: BLE001 — no test: the video is made from the model card as before
        logger.warning(f"[bench] no test ({type(e).__name__}: {str(e)[:200]})")
        return None
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)


def as_source(b: Optional[Dict]) -> str:
    """The test as plain sentences for the top of the script's source text."""
    if not b:
        return ""
    box = f"a free GitHub cloud computer with {b['cores']} CPU cores, {b['ram_gb']} GB of RAM and no graphics card"
    if b.get("no_gguf"):
        return ("MEASURED BY THIS CHANNEL (our own check, today): the model's original files on Hugging Face "
                f"add up to {b['full_gb']} GB, far more than the {b['ram_gb']} GB of RAM on {box}, so it cannot "
                "run there as released. No compressed (GGUF) version for home tools like llama.cpp, Ollama or "
                "LM Studio had been published yet when we checked.\n\n")
    if not b.get("fits"):
        sizes = []
        if b.get("q4_gb"):
            sizes.append(f"the usual compressed version ({b['q4_quant']}) is {b['q4_gb']} GB")
        if b.get("smallest_gb"):
            sizes.append(f"even the smallest version ({b['smallest_quant'] or 'smallest'}) is {b['smallest_gb']} GB")
        return ("MEASURED BY THIS CHANNEL (our own test, today): we tried to run this model with llama.cpp on "
                f"{box}. It does not fit: {'; '.join(sizes) or 'the files are too big'} (from {b['repo']} on "
                "Hugging Face). To run it at home you need a computer with more memory than that file size.\n\n")
    words = round(b["write_tps"] * 0.75, 1)
    peak = f" Peak memory used: {b['peak_gb']} GB." if b.get("peak_gb") else ""
    return ("MEASURED BY THIS CHANNEL (our own test, today): we ran this model with llama.cpp on "
            f"{box}. Version tested: {b['quant']} ({b['size_gb']} GB file, from {b['repo']} on Hugging Face). "
            f"Reading the prompt: {b['read_tps']} tokens per second. Writing the answer: {b['write_tps']} "
            f"tokens per second (about {words} words per second).{peak} A laptop with a recent processor "
            "should be similar or faster; a graphics card is much faster.\n\n")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    res = run(sys.argv[1])
    print(json.dumps(res, indent=2))
    print(as_source(res))
