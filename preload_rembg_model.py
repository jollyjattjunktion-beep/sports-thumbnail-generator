"""Best-effort U2NETP preload during the Render build, never during user requests.

Recommended Render Build Command:
    pip install -r requirements.txt && python preload_rembg_model.py

If weights cannot be downloaded during build, deployment continues and the app
falls back to fast OpenCV GrabCut. Runtime code never initiates a model download.
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
expected = MODEL_HOME / f"{model_name}.onnx"

if expected.exists():
    print(f"PREET SPORTS: cached model already exists: {expected} ({expected.stat().st_size:,} bytes)", flush=True)
else:
    print(f"PREET SPORTS: attempting build-time preload of {model_name} into {MODEL_HOME} ...", flush=True)
    try:
        from rembg import new_session
        session = new_session(model_name)
        del session
        if expected.exists():
            print(f"PREET SPORTS: model ready: {expected} ({expected.stat().st_size:,} bytes)", flush=True)
        else:
            print(f"PREET SPORTS WARNING: {expected.name} was not found after initialization; runtime will use OpenCV fallback. Files: {[p.name for p in MODEL_HOME.iterdir()]}", flush=True)
    except Exception as exc:
        print(f"PREET SPORTS WARNING: model preload failed: {exc}. Deployment can continue; runtime will use OpenCV fallback.", flush=True)
