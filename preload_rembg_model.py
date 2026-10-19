"""Preload the lightweight local rembg model during the Render build.

Recommended Render Build Command:
    pip install -r requirements.txt && python preload_rembg_model.py

The runtime app uses the same PREET_REMBG_HOME / U2NET_HOME directory.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_HOME = Path(
    os.environ.get("PREET_REMBG_HOME")
    or os.environ.get("U2NET_HOME")
    or str(BASE_DIR / ".preet_models" / "u2net")
)
MODEL_HOME.mkdir(parents=True, exist_ok=True)
os.environ["U2NET_HOME"] = str(MODEL_HOME)
model_name = os.environ.get("REMBG_MODEL", "u2netp").strip() or "u2netp"

print(f"Preloading local rembg model '{model_name}' into {MODEL_HOME} ...", flush=True)
try:
    from rembg import new_session
    session = new_session(model_name)
    del session
except Exception as exc:
    raise SystemExit(
        f"Could not preload rembg model '{model_name}': {exc}\n"
        "Check that rembg[cpu] is installed and the build environment can download model weights."
    )
files = sorted(p.name for p in MODEL_HOME.iterdir() if p.is_file())
print(f"Local background-removal model ready. Cached files: {files}", flush=True)
