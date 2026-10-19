"""Compatibility no-op for older Render Build Commands.

The current PREET SPORTS app uses OpenCV GrabCut for local background removal,
so it does not download or initialize rembg/U2Net model weights. This file stays
in the repository so an older Build Command ending in `python preload_rembg_model.py`
continues to finish successfully while users update their Render settings.
"""
print("PREET SPORTS uses model-free OpenCV GrabCut; no background-removal model preload is required.", flush=True)
