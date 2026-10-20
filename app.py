import io
import base64
import gc
import hashlib
import json
import os
import re
from urllib.parse import urlsplit, urlunsplit, urljoin

import requests
import numpy as np
import streamlit as st
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# =========================================================
# PREET SPORTS — IMAGE 1 STYLE 4K CRICKET THUMBNAIL STUDIO
# 3840 x 2160 | URL-based captain images | realistic stadium BG
# =========================================================
st.set_page_config(page_title="PREET SPORTS 4K Thumbnail Studio", layout="wide")

CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 2160
RENDER_PIPELINE_VERSION = "preet-sports-4k-v26-balanced-team-panels-brand-colors"
EXPECTED_OUTPUT_SIZE = (CANVAS_WIDTH, CANVAS_HEIGHT)

# Default panoramic cricket-stadium photo (Unsplash, free to use under Unsplash License).
# Users can override it with their own stadium URL or upload.
DEFAULT_STADIUM_URL = (
    # A stable, known sports-stadium photo fetched at preview-friendly resolution.
    # It is resized to 3840 x 2160 locally for the final download.
    "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e"
    "?auto=format&fit=crop&fm=jpg&q=72&w=1920&h=1080"
)

# Team flags are separate from captain photos, so women's team labels work too.
TEAM_FLAG_DATABASE = {
    "IND": "https://flagcdn.com/w320/in.png",
    "INDIA": "https://flagcdn.com/w320/in.png",
    "IND WOMEN": "https://flagcdn.com/w320/in.png",
    "IND-W": "https://flagcdn.com/w320/in.png",
    "IND W": "https://flagcdn.com/w320/in.png",
    "INDIA WOMEN": "https://flagcdn.com/w320/in.png",
    "WI": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "WEST INDIES": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "WEST INDIES WOMEN": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "WI WOMEN": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "AUS": "https://flagcdn.com/w320/au.png",
    "AUSTRALIA": "https://flagcdn.com/w320/au.png",
    "AUS WOMEN": "https://flagcdn.com/w320/au.png",
    "AUSTRALIA WOMEN": "https://flagcdn.com/w320/au.png",
    "NZ": "https://flagcdn.com/w320/nz.png",
    "NEW ZEALAND": "https://flagcdn.com/w320/nz.png",
    "NZ WOMEN": "https://flagcdn.com/w320/nz.png",
    "NEW ZEALAND WOMEN": "https://flagcdn.com/w320/nz.png",
    "ENG": "https://flagcdn.com/w320/gb-eng.png",
    "ENGLAND": "https://flagcdn.com/w320/gb-eng.png",
    "ENG WOMEN": "https://flagcdn.com/w320/gb-eng.png",
    "PAK": "https://flagcdn.com/w320/pk.png",
    "PAKISTAN": "https://flagcdn.com/w320/pk.png",
    "SA": "https://flagcdn.com/w320/za.png",
    "SOUTH AFRICA": "https://flagcdn.com/w320/za.png",
    "BAN": "https://flagcdn.com/w320/bd.png",
    "BANGLADESH": "https://flagcdn.com/w320/bd.png",
    "SL": "https://flagcdn.com/w320/lk.png",
    "SRI LANKA": "https://flagcdn.com/w320/lk.png",
    "AFG": "https://flagcdn.com/w320/af.png",
    "AFGHANISTAN": "https://flagcdn.com/w320/af.png",
    "IRE": "https://flagcdn.com/w320/ie.png",
    "IRELAND": "https://flagcdn.com/w320/ie.png",
    "ZIM": "https://flagcdn.com/w320/zw.png",
    "ZIMBABWE": "https://flagcdn.com/w320/zw.png",
    "ZIM-W": "https://flagcdn.com/w320/zw.png",
    "ZIM W": "https://flagcdn.com/w320/zw.png",
    "ZIMBABWE WOMEN": "https://flagcdn.com/w320/zw.png",
    "NEP": "https://flagcdn.com/w320/np.png",
    "NEPAL": "https://flagcdn.com/w320/np.png",
    "USA": "https://flagcdn.com/w320/us.png",
    "UAE": "https://flagcdn.com/w320/ae.png",
    "OMAN": "https://flagcdn.com/w320/om.png",
    "NED": "https://flagcdn.com/w320/nl.png",
    "NETHERLANDS": "https://flagcdn.com/w320/nl.png",
    "SCOT": "https://flagcdn.com/w320/gb-sct.png",
    "SCOTLAND": "https://flagcdn.com/w320/gb-sct.png",
}

# Historical fallback photos are used only if no URL image has been fetched.
# For best results, paste match-specific, high-resolution, transparent player PNG/WebP URLs.
CAPTAIN_DATABASE = {
    "IND": {
        "name": "Rohit Sharma",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Rohit_Sharma_during_the_India_vs_Australia_match_in_2023.png/800px-Rohit_Sharma_during_the_India_vs_Australia_match_in_2023.png",
    },
    "INDIA": {
        "name": "Rohit Sharma",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Rohit_Sharma_during_the_India_vs_Australia_match_in_2023.png/800px-Rohit_Sharma_during_the_India_vs_Australia_match_in_2023.png",
    },
    "WI": {
        "name": "Shai Hope",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Shai_Hope_2019.png/800px-Shai_Hope_2019.png",
    },
    "WEST INDIES": {
        "name": "Shai Hope",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Shai_Hope_2019.png/800px-Shai_Hope_2019.png",
    },
    "AUS": {
        "name": "Pat Cummins",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Pat_Cummins_in_2023.png/800px-Pat_Cummins_in_2023.png",
    },
    "AUSTRALIA": {
        "name": "Pat Cummins",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Pat_Cummins_in_2023.png/800px-Pat_Cummins_in_2023.png",
    },
    "ENG": {
        "name": "Jos Buttler",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Jos_Buttler_2022.png/800px-Jos_Buttler_2022.png",
    },
    "PAK": {
        "name": "Shaheen Afridi",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/66833.png",
    },
    "PAKISTAN": {
        "name": "Shaheen Afridi",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/66833.png",
    },
    "SL": {
        "name": "Kusal Mendis",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/63882.png",
    },
    "SRI LANKA": {
        "name": "Kusal Mendis",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/63882.png",
    },
    "SA": {
        "name": "Temba Bavuma",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Temba_Bavuma_2023.png/800px-Temba_Bavuma_2023.png",
    },
    "NZ": {
        "name": "Kane Williamson",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Kane_Williamson_in_2019.png/800px-Kane_Williamson_in_2019.png",
    },
}


def normalize_team_name(team_name):
    """Normalize team labels to make flag lookups work for e.g. AUS WOMEN."""
    return re.sub(r"\s+", " ", str(team_name or "").strip().upper().replace("_", " "))


def get_team_flag_url(team_name):
    key = normalize_team_name(team_name)
    if key in TEAM_FLAG_DATABASE:
        return TEAM_FLAG_DATABASE[key]
    # If input contains a common long name, allow the base country flag to resolve.
    first = key.replace(" WOMEN", "").replace(" MEN", "")
    if first in TEAM_FLAG_DATABASE:
        return TEAM_FLAG_DATABASE[first]
    return None


@st.cache_resource
def get_font_file():
    """Use a local font when available; avoid delaying every first render for a download."""
    local_candidates = [
        "/tmp/Montserrat-Black.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for font_path in local_candidates:
        if os.path.exists(font_path):
            return font_path
    return None


def load_robust_font(size):
    font_path = get_font_file()
    if font_path:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    for path in [
        "arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def image_url_candidates(url):
    """Try the original ESPN CDN image and higher-resolution, less-cropped variants."""
    if not url or not isinstance(url, str):
        return []
    url = url.strip()
    candidates = []
    parsed = urlsplit(url)
    path = parsed.path
    marker = "/image/upload/"

    if "hscicdn.com" in parsed.netloc.lower() and marker in path:
        before, tail = path.split(marker, 1)
        sections = tail.split("/", 1)
        if len(sections) == 2:
            transform, asset_path = sections
            # Only strip/replace the first path segment when it looks like CDN transforms.
            looks_like_transform = (
                "," in transform
                or transform.startswith(("f_", "t_", "w_", "h_", "c_", "q_", "dpr_"))
            )
            if looks_like_transform:
                # First try the untransformed asset, then explicit high-resolution variants.
                candidates.extend([
                    urlunsplit((parsed.scheme, parsed.netloc, before + marker + asset_path, "", "")),
                    urlunsplit((parsed.scheme, parsed.netloc, before + marker + "f_auto,q_auto/" + asset_path, "", "")),
                    urlunsplit((parsed.scheme, parsed.netloc, before + marker + "f_auto,t_ds_w_1600/" + asset_path, "", "")),
                    urlunsplit((parsed.scheme, parsed.netloc, before + marker + "f_auto,t_4x3_1600/" + asset_path, "", "")),
                ])
    candidates.append(url)
    # Stable unique ordering
    return list(dict.fromkeys(candidates))


@st.cache_data(show_spinner=False, ttl=86400, max_entries=128)
def fetch_online_image(url):
    """Fetch and cache an image quickly, trying at most two useful ESPN CDN variants."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    all_candidates = image_url_candidates(url)
    if len(all_candidates) > 1:
        # First try the untransformed original asset. If it fails/is tiny, try the
        # explicit high-resolution rendition; don't serially wait on every variant.
        candidates = [all_candidates[0]]
        high_res = next(
            (item for item in all_candidates if "t_ds_w_1600" in item or "t_4x3_1600" in item),
            None,
        )
        if high_res and high_res not in candidates:
            candidates.append(high_res)
        elif url not in candidates:
            candidates.append(url)
    else:
        candidates = all_candidates[:1]

    best_image = None
    best_score = -1.0
    for candidate in candidates:
        try:
            response = requests.get(candidate, headers=headers, timeout=(1.8, 2.8))
            response.raise_for_status()
            payload = response.content
            # Reject unexpectedly huge responses before decoding to protect Render memory.
            if len(payload) > 30 * 1024 * 1024:
                continue
            with Image.open(io.BytesIO(payload)) as opened:
                opened.load()
                img = opened.convert("RGBA")
                pixels = img.width * img.height
                aspect = img.width / max(1, img.height)
                has_transparency = "A" in opened.getbands() and opened.getchannel("A").getextrema()[0] < 255
                aspect_bonus = 1.20 if 0.52 <= aspect <= 0.95 else (1.0 if aspect <= 1.15 else 0.72)
                score = pixels * aspect_bonus * (1.05 if has_transparency else 1.0)
                if score > best_score:
                    best_image = img.copy()
                    best_score = score
                # One sufficiently large image is enough. This stops the preview
                # waiting for multiple nearly-identical CDN renditions.
                if pixels >= 900_000 or (has_transparency and pixels >= 500_000):
                    return img.copy()
        except Exception:
            continue
    return best_image



def get_gemini_api_key():
    """Read the Gemini API key from Render env vars or Streamlit secrets."""
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        key = os.environ.get(env_name, "").strip()
        if key:
            return key
    try:
        for secret_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            key = str(st.secrets.get(secret_name, "")).strip()
            if key:
                return key
    except Exception:
        pass
    return ""


def _find_gemini_image_block(payload):
    """Handle the image convenience field and nested Interaction output variants."""
    if not isinstance(payload, dict):
        return None
    direct = payload.get("output_image")
    if isinstance(direct, dict) and direct.get("data"):
        return direct

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "image" and node.get("data"):
                return node
            # Some responses use output/content/steps/model_output nesting.
            for value in node.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(node, list):
            for value in node:
                found = walk(value)
                if found:
                    return found
        return None

    return walk(payload.get("output", payload))


def _remove_magenta_chroma_background(image):
    """Convert a deliberately requested pure-magenta backing into a soft alpha mask.

    Gemini image generation doesn't expose a guaranteed transparent-background option
    in its image response format. We therefore request a uniform magenta background and
    key that color out when the model follows the instruction.
    """
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    alpha_array_existing = np.asarray(alpha, dtype=np.uint8)
    # Treat it as a true cutout only when a meaningful portion of the image is transparent.
    # A few partially transparent pixels alone should not bypass the chroma-key cleanup.
    if float(np.mean(alpha_array_existing < 250)) > 0.03:
        return image

    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    magenta_like = (
        (red > 90) & (blue > 90) & (green < 185)
        & ((red - green) > 38) & ((blue - green) > 38)
    )
    score = np.minimum(red - green, blue - green)
    # Keep non-magenta colors fully opaque; soften only the magenta range.
    keyed_alpha = 255 - np.clip((score - 22) * (255.0 / 100.0), 0, 255)
    alpha_array = np.where(magenta_like, keyed_alpha, 255).astype(np.uint8)

    # Refuse to silently composite a full rectangle if Gemini ignored the key-color request.
    border_pixels = np.concatenate([
        magenta_like[0, :], magenta_like[-1, :],
        magenta_like[:, 0], magenta_like[:, -1],
    ])
    if float(border_pixels.mean()) < 0.10:
        raise ValueError(
            "Gemini returned an image without a clear magenta background, so it could not be safely cut out. "
            "Try Convert again; the original photo has not been changed."
        )

    keyed = Image.fromarray(alpha_array, mode="L").filter(ImageFilter.GaussianBlur(0.45))
    image.putalpha(keyed)
    return image


@st.cache_resource(show_spinner=False)
def _get_local_rembg_session(model_name="u2netp"):
    """Load the lightweight local segmentation model once per running app process."""
    model_home = (
        os.environ.get("PREET_REMBG_HOME")
        or os.environ.get("U2NET_HOME")
        or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".preet_models", "u2net")
    )
    os.makedirs(model_home, exist_ok=True)
    os.environ["U2NET_HOME"] = model_home
    from rembg import new_session
    return new_session(model_name)


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 30, max_entries=64)
def _fast_local_cutout_cached(source_bytes, algorithm_version="cached-u2netp-512-opencv-v7-hole-fill"):

    """Create a local transparent cutout using cached U2NETP if preloaded, else OpenCV.

    No hosted API is called, and model weights are never downloaded during a user request.
    """
    import cv2

    try:
        cv2.setNumThreads(1)
    except Exception:
        pass

    with Image.open(io.BytesIO(source_bytes)) as opened:
        opened.load()
        source = opened.convert("RGB")

    # Limit intermediate memory on small Render instances.
    max_output_side = 1800
    if max(source.size) > max_output_side:
        scale_out = max_output_side / float(max(source.size))
        source = source.resize(
            (max(1, round(source.width * scale_out)), max(1, round(source.height * scale_out))),
            Image.Resampling.LANCZOS,
        )

    original_size = source.size

    def fill_internal_mask_holes(mask_array):
        """Fill enclosed transparent holes inside a foreground silhouette.

        This restores dark jersey details (sponsors, badges, logos) that GrabCut can
        incorrectly label as background, without filling background connected to the
        outside edge of the crop. Soft edge pixels are preserved; only enclosed holes
        are changed to opaque.
        """
        binary = np.where(np.asarray(mask_array, dtype=np.uint8) > 16, 255, 0).astype(np.uint8)
        padded = np.pad(binary, 1, mode="constant", constant_values=0)
        flood = padded.copy()
        flood_mask = np.zeros((flood.shape[0] + 2, flood.shape[1] + 2), dtype=np.uint8)
        cv2.floodFill(flood, flood_mask, (0, 0), 255)
        filled = cv2.bitwise_or(padded, cv2.bitwise_not(flood))[1:-1, 1:-1]
        holes = (filled > 0) & (binary == 0)
        result = np.asarray(mask_array, dtype=np.uint8).copy()
        result[holes] = 255
        return result

    # Use local U2NETP only if its weights already exist on disk. Never download model
    # weights during a user request: on small Render instances that caused long waits and
    # HTTP 502 errors. If preloaded weights are missing or inference fails, use OpenCV.
    model_name = os.environ.get("REMBG_MODEL", "u2netp").strip() or "u2netp"
    model_home = (
        os.environ.get("PREET_REMBG_HOME")
        or os.environ.get("U2NET_HOME")
        or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".preet_models", "u2net")
    )
    weights_exist = os.path.isfile(os.path.join(model_home, f"{model_name}.onnx"))
    use_rembg = os.environ.get("PREET_ENABLE_REMBG", "1").strip().lower() not in {"0", "false", "no", "off"}
    if use_rembg and weights_exist:
        try:
            # U2NETP at 512px is a practical accuracy/speed compromise for Render CPU.
            model_side = max(384, min(512, int(os.environ.get("PREET_REMBG_MAX_SIDE", "512"))))
            model_input = source
            if max(model_input.size) > model_side:
                model_scale = model_side / float(max(model_input.size))
                model_input = model_input.resize(
                    (max(1, round(model_input.width * model_scale)), max(1, round(model_input.height * model_scale))),
                    Image.Resampling.LANCZOS,
                )
            model_buffer = io.BytesIO()
            model_input.save(model_buffer, format="PNG", optimize=False)
            from rembg import remove as rembg_remove
            local_session = _get_local_rembg_session(model_name)
            rembg_result_bytes = rembg_remove(
                model_buffer.getvalue(), session=local_session, alpha_matting=False, post_process_mask=True
            )
            with Image.open(io.BytesIO(rembg_result_bytes)) as rembg_opened:
                rembg_result = rembg_opened.convert("RGBA")
            if rembg_result.size != original_size:
                rembg_result = rembg_result.resize(original_size, Image.Resampling.LANCZOS)
            rembg_alpha = rembg_result.getchannel("A")
            # Segmentation models can also punch transparent holes through dark logos.
            # Fill only enclosed holes, leaving the exterior background transparent.
            rembg_alpha = Image.fromarray(fill_internal_mask_holes(np.asarray(rembg_alpha, dtype=np.uint8)), mode="L")
            rembg_result.putalpha(rembg_alpha)
            transparent_fraction = float(np.asarray(rembg_alpha, dtype=np.uint8).__lt__(250).mean())
            if rembg_alpha.getextrema()[0] < 250 and 0.005 < transparent_fraction < 0.97:
                alpha_bounds = rembg_alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
                if alpha_bounds:
                    l, t, r, b = alpha_bounds
                    pad = max(3, int(max(rembg_result.size) * 0.008))
                    rembg_result = rembg_result.crop((
                        max(0, l - pad), max(0, t - pad),
                        min(rembg_result.width, r + pad), min(rembg_result.height, b + pad),
                    ))
                rembg_buffer = io.BytesIO()
                rembg_result.save(rembg_buffer, format="PNG", optimize=False, compress_level=1)
                return rembg_buffer.getvalue()
        except Exception:
            # Any model/inference failure falls through to OpenCV; don't block the app.
            pass

    max_segmentation_side = int(os.environ.get("PREET_GRABCUT_MAX_SIDE", "512"))
    max_segmentation_side = max(320, min(max_segmentation_side, 640))
    scale = min(1.0, max_segmentation_side / float(max(source.size)))
    small = source if scale >= 1.0 else source.resize(
        (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )

    rgb = np.asarray(small, dtype=np.uint8)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    if width < 40 or height < 40:
        raise ValueError("Image crop is too small. Use a player crop at least 40 × 40 pixels.")

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    face = None
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
        detector = cv2.CascadeClassifier(cascade_path)
        if not detector.empty():
            detected = detector.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=4,
                minSize=(max(32, int(width * 0.11)), max(32, int(height * 0.11))),
            )
            if len(detected):
                # Cropped player images normally have one large face; small flag/logo
                # detections are discarded in favor of the largest plausible face.
                plausible = [tuple(map(int, f)) for f in detected if f[2] >= width * 0.16 and f[3] >= height * 0.12]
                if plausible:
                    face = max(plausible, key=lambda f: f[2] * f[3])
    except Exception:
        face = None

    mask = np.full((height, width), cv2.GC_BGD, dtype=np.uint8)

    if face is not None:
        fx, fy, fw, fh = face
        cx = fx + fw / 2.0
        # Portrait silhouette: tightly follows the head/face and expands down into
        # shoulders/torso. The areas outside this polygon are definite background, so
        # flags and colored panels at the top corners cannot become part of the cutout.
        def clipx(value):
            return int(max(0, min(width - 1, round(value))))

        def clipy(value):
            return int(max(0, min(height - 1, round(value))))

        top = max(0, int(fy - 0.42 * fh))
        points = np.array([
            [clipx(cx - 0.36 * fw), clipy(top)],
            [clipx(cx + 0.36 * fw), clipy(top)],
            [clipx(fx + 0.98 * fw), clipy(fy - 0.04 * fh)],
            [clipx(fx + 1.03 * fw), clipy(fy + 0.25 * fh)],
            [clipx(fx + 1.03 * fw), clipy(fy + 0.70 * fh)],
            [clipx(fx + 1.10 * fw), clipy(fy + 0.95 * fh)],
            [clipx(cx + 0.88 * fw), clipy(fy + 1.15 * fh)],
            [clipx(cx + 1.30 * fw), clipy(fy + 1.38 * fh)],
            [width - 1, clipy(fy + 1.48 * fh)],
            [width - 1, height - 1],
            [0, height - 1],
            [0, clipy(fy + 1.48 * fh)],
            [clipx(cx - 1.30 * fw), clipy(fy + 1.38 * fh)],
            [clipx(cx - 0.88 * fw), clipy(fy + 1.15 * fh)],
            [clipx(fx - 0.10 * fw), clipy(fy + 0.95 * fh)],
            [clipx(fx - 0.04 * fw), clipy(fy + 0.70 * fh)],
            [clipx(fx - 0.04 * fw), clipy(fy + 0.25 * fh)],
            [clipx(fx + 0.02 * fw), clipy(fy - 0.04 * fh)],
        ], dtype=np.int32)
        cv2.fillPoly(mask, [points], cv2.GC_PR_FGD)

        # Sure-foreground seeds inside the face and central jersey. These help GrabCut
        # learn the player colors while keeping outside panels as hard background.
        face_center = (clipx(cx), clipy(fy + 0.56 * fh))
        cv2.ellipse(
            mask,
            face_center,
            (max(5, int(fw * 0.33)), max(5, int(fh * 0.42))),
            0, 0, 360, cv2.GC_FGD, -1,
        )
        torso_top = clipy(fy + 0.96 * fh)
        torso_left = clipx(cx - 0.22 * fw)
        torso_right = clipx(cx + 0.22 * fw)
        if torso_top < height - 2:
            cv2.rectangle(mask, (torso_left, torso_top), (torso_right, height - 1), cv2.GC_FGD, -1)
    else:
        # Fallback for non-portrait images such as products, pets, or a missed face.
        margin_x = max(2, int(width * 0.035))
        margin_y = max(2, int(height * 0.025))
        rect = (margin_x, margin_y, max(1, width - 2 * margin_x), max(1, height - 2 * margin_y))
        cv2.grabCut(bgr, mask, rect, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 3, cv2.GC_INIT_WITH_RECT)

    bg_model = np.zeros((1, 65), dtype=np.float64)
    fg_model = np.zeros((1, 65), dtype=np.float64)
    cv2.grabCut(bgr, mask, None, bg_model, fg_model, 4 if face is not None else 1, cv2.GC_INIT_WITH_MASK if face is not None else cv2.GC_EVAL)

    alpha_small = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
    ).astype(np.uint8)
    if face is not None:
        # Keep only the foreground component connected to the detected face.
        count, labels, stats, _ = cv2.connectedComponentsWithStats((alpha_small > 0).astype(np.uint8), 8)
        fx, fy, fw, fh = face
        seed_x = max(0, min(width - 1, int(fx + fw / 2)))
        seed_y = max(0, min(height - 1, int(fy + fh * 0.56)))
        component_id = int(labels[seed_y, seed_x])
        if component_id > 0:
            alpha_small = np.where(labels == component_id, 255, 0).astype(np.uint8)

    # Remove small specks and smooth only the mask edge. Keep genuine semi-transparent
    # pixels at the edge so hair and jersey contours don't look like hard stickers.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    alpha_small = cv2.morphologyEx(alpha_small, cv2.MORPH_CLOSE, kernel, iterations=1)
    # Critical fix: preserve dark logos and sponsor lettering inside the player mask.
    alpha_small = fill_internal_mask_holes(alpha_small)
    foreground_fraction = float(np.count_nonzero(alpha_small)) / float(alpha_small.size)
    if foreground_fraction < 0.04 or foreground_fraction > 0.98:
        raise ValueError(
            "The player mask was not reliable. Crop closer around one player, include the complete head/shoulders, and exclude the neighboring flag or graphics."
        )

    alpha = Image.fromarray(alpha_small, mode="L")
    if original_size != alpha.size:
        alpha = alpha.resize(original_size, Image.Resampling.LANCZOS)
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.45))
    result = source.convert("RGBA")
    result.putalpha(alpha)

    bbox = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
    if not bbox:
        raise ValueError("No foreground pixels were detected in this crop.")
    left, top, right, bottom = bbox
    padding = max(3, int(max(result.size) * 0.008))
    result = result.crop((
        max(0, left - padding), max(0, top - padding),
        min(result.width, right + padding), min(result.height, bottom + padding),
    ))

    output = io.BytesIO()
    result.save(output, format="PNG", optimize=False, compress_level=1)
    return output.getvalue()

def remove_background_from_any_image(upload_bytes, filename="image", subject_instruction=None):
    """Remove background locally with cached U2NETP when preloaded, else OpenCV GrabCut.

    No hosted API is called. Model weights are never downloaded during an app interaction.
    """
    try:
        with Image.open(io.BytesIO(upload_bytes)) as opened:
            opened.load()
            source = opened.convert("RGBA")
            # If the input already has meaningful transparency, retain it and avoid segmentation.
            alpha = source.getchannel("A")
            if alpha.getextrema()[0] < 250:
                bbox = alpha.getbbox()
                if bbox:
                    source = source.crop(bbox)
                return source, None

            # Limit cache input size to reduce memory; output cutout keeps up to 1800px detail.
            rgb = source.convert("RGB")
            max_source_side = 1800
            if max(rgb.size) > max_source_side:
                scale = max_source_side / float(max(rgb.size))
                rgb = rgb.resize(
                    (max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale))),
                    Image.Resampling.LANCZOS,
                )
            normalized = io.BytesIO()
            rgb.save(normalized, format="JPEG", quality=90, optimize=False)
            normalized_bytes = normalized.getvalue()
    except Exception as exc:
        return None, f"Could not read the uploaded image: {exc}"

    try:
        result_bytes = _fast_local_cutout_cached(normalized_bytes, "cached-u2netp-512-opencv-v7-hole-fill")
        with Image.open(io.BytesIO(result_bytes)) as output_image:
            output_image.load()
            result = output_image.convert("RGBA")
        alpha_extrema = result.getchannel("A").getextrema()
        if alpha_extrema == (255, 255):
            return None, "No transparent foreground was created. Try adjusting the crop around the player."
        return result, None
    except Exception as exc:
        return None, (
            f"Fast local background removal failed: {exc}. Make the crop include the full player and a small border of background, then retry."
        )

def convert_player_to_front_facing(upload_bytes, filename, side):
    """Use Gemini Nano Banana to edit a cricket photo into a front-facing cutout.

    Uses Google's REST Interactions API so the app doesn't require an extra SDK.
    The call is user-triggered because image editing may incur API charges.
    Returns (PIL.Image or None, error message or None).
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return None, (
            "Gemini image editing is not configured. Create a Gemini API key in Google AI Studio, "
            "then add it in Render → Environment as GEMINI_API_KEY and redeploy. "
            "Gemini API usage may be billed separately from your Gemini Pro subscription."
        )

    try:
        with Image.open(io.BytesIO(upload_bytes)) as opened:
            opened.load()
            source = opened.convert("RGBA")
            if max(source.size) > 1600:
                scale = 1600 / max(source.size)
                source = source.resize(
                    (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
                    Image.Resampling.LANCZOS,
                )
            # Photos go as compact JPEG; input cutouts keep their transparency as PNG.
            has_alpha = source.getchannel("A").getextrema()[0] < 250
            source_buffer = io.BytesIO()
            if has_alpha:
                source.save(source_buffer, format="PNG", optimize=False, compress_level=3)
                mime_type = "image/png"
            else:
                source.convert("RGB").save(source_buffer, format="JPEG", quality=90, optimize=True)
                mime_type = "image/jpeg"
            source_bytes = source_buffer.getvalue()
    except Exception as exc:
        return None, f"Could not read the uploaded photo: {exc}"

    side_label = "left" if side == "left" else "right"
    prompt = (
        "Edit the supplied real cricket-player photograph for a professional sports broadcast thumbnail. "
        "Make the SAME player face directly forward toward the camera: head straight, both eyes visible, "
        "nose and shoulders aligned naturally toward the lens, shoulders nearly square to camera. "
        "Avoid side profile and avoid three-quarter pose. Preserve the person's recognizable identity, "
        "facial proportions, skin tone, hairstyle, age, and the same team's uniform colors/design as closely "
        "as possible. Frame from the top of the head to around the waist or mid-torso with both shoulders "
        "and the jersey visible. Use realistic anatomy, photographic skin texture and crisp sports-photo detail. "
        "Do not add text, flags, graphics, watermarks, other people, or props. "
        "IMPORTANT CUTOUT REQUIREMENT: place the player against a perfectly flat, uniform pure magenta "
        "background RGB(255, 0, 255), edge to edge. No gradient, texture, shadows, stadium, or colored rim light. "
        "Keep magenta only in the empty background, never on the player. Center the player with a little margin "
        f"around hair and shoulders for the {side_label} side of a 16:9 cricket thumbnail. Return one edited image."
    )

    request_body = {
        "model": os.environ.get("GEMINI_IMAGE_MODEL", "gemini-nano-banana-2.1").strip(),
        "input": [
            {"type": "text", "text": prompt},
            {
                "type": "image",
                "data": base64.b64encode(source_bytes).decode("ascii"),
                "mime_type": mime_type,
            },
        ],
        "response_format": {
            "type": "image",
            "mime_type": "image/jpeg",
            "aspect_ratio": "3:4",
            "image_size": "2K",
        },
    }

    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=request_body,
            timeout=(15, 240),
        )
        if response.status_code >= 400:
            detail = ""
            try:
                err_json = response.json()
                err = err_json.get("error", {}) if isinstance(err_json, dict) else {}
                detail = err.get("message", "") if isinstance(err, dict) else str(err)
            except Exception:
                detail = response.text[:500]
            if response.status_code in (401, 403):
                return None, (
                    "Gemini rejected the API key or permission (HTTP "
                    f"{response.status_code}). Check GEMINI_API_KEY in Render and verify the key's project/API access. "
                    + detail
                ).strip()
            if response.status_code == 429:
                return None, (
                    "Gemini API quota/rate limit reached (HTTP 429). Check your AI Studio API usage/billing or retry later. "
                    + detail
                ).strip()
            return None, f"Gemini image editing failed (HTTP {response.status_code}). {detail}".strip()

        payload = response.json()
        image_block = _find_gemini_image_block(payload)
        if not image_block:
            return None, "Gemini returned no image. Try again or use a clearer, higher-resolution player photo."
        encoded = image_block.get("data")
        if not encoded:
            return None, "Gemini's response did not contain image data."
        image_bytes = base64.b64decode(encoded)
        with Image.open(io.BytesIO(image_bytes)) as output_image:
            output_image.load()
            converted = output_image.convert("RGBA")
        try:
            converted = _remove_magenta_chroma_background(converted)
        except ValueError as exc:
            return None, str(exc)
        return converted, None
    except requests.Timeout:
        return None, "Gemini pose conversion timed out. Try a smaller source photo or retry later."
    except requests.RequestException as exc:
        return None, f"Could not reach the Gemini image-edit API: {exc}"
    except Exception as exc:
        return None, f"Gemini pose conversion failed: {exc}"

@st.cache_data(show_spinner=False, ttl=86400, max_entries=64)
def resolve_player_image_url(player_url):
    """Accept a direct image URL or a public ICC player-profile URL.

    ICC player pages use numeric player IDs, which are also used by ICC's player-image CDN.
    For other profile pages, fall back to Open Graph / Twitter image metadata.
    """
    if not player_url or not isinstance(player_url, str):
        return None
    player_url = player_url.strip()
    if not player_url.lower().startswith(("http://", "https://")):
        return None

    parsed = urlsplit(player_url)
    host = (parsed.netloc or "").lower()

    # Direct image links should be fetched as supplied.
    if host.startswith("images.icc-cricket.com") and "/image/upload/" in parsed.path:
        return player_url
    if re.search(r"\.(png|jpe?g|webp|gif)(?:$|\?)", player_url, re.I):
        return player_url

    # ICC player profile URLs such as /rankings/66833/shaheen-afridi map to player ID 66833.
    if "icc-cricket.com" in host:
        player_id_match = re.search(r"/rankings/(\d+)(?:/|$)", parsed.path, re.I)
        if player_id_match:
            player_id = player_id_match.group(1)
            return (
                "https://images.icc-cricket.com/image/upload/"
                "t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/"
                f"{player_id}.png"
            )

    # Generic webpage fallback: extract its preferred hero / player image.
    try:
        response = requests.get(
            player_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=(2.0, 4.0),
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for attr, value in (("property", "og:image"), ("name", "twitter:image"), ("property", "og:image:secure_url")):
            tag = soup.find("meta", attrs={attr: value})
            if tag and tag.get("content"):
                return urljoin(player_url, tag["content"].strip())

        # ICC/other sports pages may expose images with these attributes even without OG tags.
        for img_tag in soup.find_all("img"):
            candidate = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
            alt = str(img_tag.get("alt", "")).lower()
            if candidate and any(word in alt for word in ("player", "kusal", "mendis", "shaheen", "afridi")):
                return urljoin(player_url, candidate)
    except Exception:
        pass

    # Return the original as a last resort; the fetcher will validate whether it is an image.
    return player_url


def _player_image_from_object(player_obj):
    """Read image URLs from several common ESPNcricinfo JSON shapes."""
    if not isinstance(player_obj, dict):
        return None
    image_obj = player_obj.get("image") or player_obj.get("photo") or player_obj.get("headshot")
    if isinstance(image_obj, dict):
        for key in ("url", "src", "href", "imageUrl", "fullImageUrl", "originalUrl"):
            if image_obj.get(key):
                return image_obj[key]
    elif isinstance(image_obj, str):
        return image_obj
    for key in ("imageUrl", "imageURL", "photoUrl", "headshotUrl", "image_url"):
        if player_obj.get(key):
            return player_obj[key]
    return None


def _is_captain(player_record, player_obj):
    name = str(player_obj.get("name", ""))
    role = str(player_obj.get("role", ""))
    return bool(
        player_record.get("isCaptain")
        or player_obj.get("isCaptain")
        or player_obj.get("captain") is True
        or "(c)" in name.lower()
        or "captain" in role.lower()
    )


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_from_cricinfo_url(url):
    """Extract captain and team information from accessible ESPNcricinfo match/squad pages."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=18)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        next_data_tag = soup.find("script", id="__NEXT_DATA__")
        if not next_data_tag or not next_data_tag.string:
            return None, "The match page did not expose squad data to the app. Try direct image URLs below."

        data = json.loads(next_data_tag.string)
        props = data.get("props", {}).get("appPageProps", {})
        page_data = props.get("data", {}) if isinstance(props, dict) else {}
        squad_data = page_data.get("squads") or page_data.get("teams") or []

        # Some ESPN pages nest squad data under a slightly different key.
        if not squad_data and isinstance(page_data, dict):
            for candidate_key in ("matchSquads", "teamSquads", "squad"):
                if isinstance(page_data.get(candidate_key), list):
                    squad_data = page_data[candidate_key]
                    break

        teams_found = []
        for team in squad_data:
            team_obj = team.get("team", {}) if isinstance(team.get("team"), dict) else {}
            team_name = team_obj.get("name") or team.get("name") or team.get("displayName") or "TEAM"
            team_code = (
                team_obj.get("abbreviation")
                or team_obj.get("shortName")
                or team.get("abbreviation")
                or team.get("shortName")
                or re.sub(r"[^A-Za-z]", "", team_name)[:3].upper()
            )

            players = team.get("players", []) or team.get("squad", []) or []
            captain_record = None
            captain_obj = None
            for player_record in players:
                if not isinstance(player_record, dict):
                    continue
                player_obj = player_record.get("player", player_record)
                if isinstance(player_obj, dict) and _is_captain(player_record, player_obj):
                    captain_record, captain_obj = player_record, player_obj
                    break

            # Check explicit captain object if no squad member had the captain marker.
            if captain_obj is None:
                possible_captain = team.get("captain") or team_obj.get("captain")
                if isinstance(possible_captain, dict):
                    captain_obj = possible_captain.get("player", possible_captain)
                    captain_record = possible_captain

            captain_name = None
            captain_img = None
            if isinstance(captain_obj, dict):
                captain_name = re.sub(r"\s*\(c\)\s*", "", str(captain_obj.get("name", "")), flags=re.I).strip()
                captain_img = _player_image_from_object(captain_obj)
                if captain_img:
                    captain_img = urljoin(url, captain_img)

            teams_found.append({
                "name": team_name,
                "code": str(team_code).upper(),
                "captain": captain_name or "Captain not marked on page",
                "img_url": captain_img,
            })

        if len(teams_found) >= 2:
            return teams_found[:2], None
        return None, "Could not find two squads in this match page. Paste direct player image URLs instead."
    except requests.HTTPError as exc:
        code = getattr(exc.response, "status_code", "unknown")
        return None, f"ESPNcricinfo blocked or rejected this request (HTTP {code}). Use direct player image URLs below."
    except Exception as exc:
        return None, f"Could not read the match page: {exc}. Use direct player image URLs below."


def resize_cover(image, width, height):
    """Resize and center-crop an image to the exact thumbnail aspect ratio."""
    image = image.convert("RGB")
    scale = max(width / image.width, height / image.height)
    new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    image = image.resize(new_size, Image.Resampling.LANCZOS)
    left = (image.width - width) // 2
    top = (image.height - height) // 2
    return image.crop((left, top, left + width, top + height)).convert("RGBA")


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_default_stadium_background():
    return fetch_online_image(DEFAULT_STADIUM_URL)


@st.cache_resource
def generate_procedural_stadium():
    """Fallback if the online stadium photo cannot be fetched."""
    img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (16, 68, 130, 255))
    draw = ImageDraw.Draw(img)
    # Blue sky gradient
    for y in range(int(CANVAS_HEIGHT * 0.60)):
        t = y / max(1, int(CANVAS_HEIGHT * 0.60))
        color = (int(8 + 18 * t), int(100 + 55 * t), int(205 + 20 * t), 255)
        draw.line((0, y, CANVAS_WIDTH, y), fill=color, width=1)
    # Distant stands
    stand_top, stand_bottom = int(CANVAS_HEIGHT * 0.30), int(CANVAS_HEIGHT * 0.63)
    draw.rectangle((0, stand_top, CANVAS_WIDTH, stand_bottom), fill=(35, 48, 69, 255))
    for y in range(stand_top + 20, stand_bottom, 58):
        draw.line((0, y, CANVAS_WIDTH, y), fill=(80, 94, 111, 255), width=12)
    # Stadium floodlights
    for x in (int(CANVAS_WIDTH * 0.25), int(CANVAS_WIDTH * 0.75)):
        draw.rectangle((x, 150, x + 22, int(CANVAS_HEIGHT * 0.42)), fill=(35, 40, 51, 255))
        draw.rounded_rectangle((x - 90, 100, x + 115, 285), radius=22, fill=(245, 246, 255, 255))
        for gy in range(114, 276, 25):
            for gx in range(x - 70, x + 100, 28):
                draw.ellipse((gx, gy, gx + 13, gy + 13), fill=(255, 255, 231, 255))
    # Green pitch / outfield
    for y in range(stand_bottom, CANVAS_HEIGHT):
        t = (y - stand_bottom) / max(1, CANVAS_HEIGHT - stand_bottom)
        color = (int(37 - 7 * t), int(112 + 52 * t), int(35 + 8 * t), 255)
        draw.line((0, y, CANVAS_WIDTH, y), fill=color, width=1)
    draw.ellipse((CANVAS_WIDTH // 2 - 480, CANVAS_HEIGHT - 690, CANVAS_WIDTH // 2 + 480, CANVAS_HEIGHT - 360), fill=(199, 176, 126, 255))
    return img.filter(ImageFilter.GaussianBlur(1.5))


def get_image_alpha_content(image):
    """Trim transparent padding from PNG cutouts without trimming opaque photos."""
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    extrema = alpha.getextrema()
    if extrema == (255, 255):
        return image
    content_mask = alpha.point(lambda value: 255 if value > 8 else 0)
    bbox = content_mask.getbbox()
    if not bbox:
        return image
    left, top, right, bottom = bbox
    pad_x = max(8, int((right - left) * 0.015))
    pad_y = max(8, int((bottom - top) * 0.012))
    bbox = (
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(image.width, right + pad_x),
        min(image.height, bottom + pad_y),
    )
    # Don't crop if there is virtually no transparent margin to remove.
    if bbox[2] - bbox[0] > image.width * 0.985 and bbox[3] - bbox[1] > image.height * 0.985:
        return image
    return image.crop(bbox)


def apply_sports_color_grade(image):
    if image is None:
        return None
    image = ImageEnhance.Color(image).enhance(1.10)
    image = ImageEnhance.Contrast(image).enhance(1.06)
    image = ImageEnhance.Sharpness(image).enhance(1.24)
    return image


# Exact player placement boxes measured from the 16:9 reference thumbnail.
# Canvas: 3840 x 2160 px. The independent left/right sizes intentionally match the reference.
LEFT_PLAYER_WIDTH = 1700
LEFT_PLAYER_HEIGHT = 2025
LEFT_PLAYER_X = 0
LEFT_PLAYER_Y = CANVAS_HEIGHT - LEFT_PLAYER_HEIGHT  # 135 px from top

RIGHT_PLAYER_WIDTH = 1660
RIGHT_PLAYER_HEIGHT = 2000
RIGHT_PLAYER_X = CANVAS_WIDTH - RIGHT_PLAYER_WIDTH  # 2180 px from left
RIGHT_PLAYER_Y = CANVAS_HEIGHT - RIGHT_PLAYER_HEIGHT  # 160 px from top


def render_player_cutout(canvas, player_img, side):
    """Place the entire player cutout in the outer side lane without distortion.

    The player's natural aspect ratio is preserved (contain-fit). Left player anchors to
    the far left; right player anchors to the far right, keeping the centre title clear.
    Flags and player layers remain separate, and shadows are kept subtle.
    """
    if player_img is None:
        return

    player = get_image_alpha_content(apply_sports_color_grade(player_img)).convert("RGBA")
    if side == "left":
        max_w, max_h = LEFT_PLAYER_WIDTH, LEFT_PLAYER_HEIGHT
    elif side == "right":
        max_w, max_h = RIGHT_PLAYER_WIDTH, RIGHT_PLAYER_HEIGHT
    else:
        raise ValueError("side must be 'left' or 'right'")

    # Fit the whole image inside its fixed maximum dimensions; never stretch or crop the head/torso.
    scale = min(max_w / max(1, player.width), max_h / max(1, player.height))
    new_w = max(1, int(round(player.width * scale)))
    new_h = max(1, int(round(player.height * scale)))
    player = player.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Put players on opposite outside edges. The right portrait is explicitly anchored to canvas right.
    x = 0 if side == "left" else CANVAS_WIDTH - new_w
    y = CANVAS_HEIGHT - new_h

    alpha = player.getchannel("A")
    shadow_alpha = alpha.filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.GaussianBlur(7))
    shadow_alpha = shadow_alpha.point(lambda value: int(value * 0.13))
    shadow = Image.new("RGBA", (new_w, new_h), (5, 10, 20, 0))
    shadow.putalpha(shadow_alpha)
    canvas.alpha_composite(shadow, (x, y))
    canvas.alpha_composite(player, (x, y))


def draw_pill_badge(draw, bbox, fill_color, border_color=None, border_width=0, radius=60):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill_color)
    if border_color and border_width > 0:
        draw.rounded_rectangle(bbox, radius=radius, outline=border_color, width=border_width)


def draw_centered_text(draw, canvas_width, text, y, font, fill, stroke_width=0, stroke_fill=None):
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    text_width = bbox[2] - bbox[0]
    x = (canvas_width - text_width) // 2
    draw.text(
        (x, y - bbox[1]),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
    return (x, y, text_width, bbox[3] - bbox[1])


def draw_brand_pill(draw, channel_text):
    """Smaller top-centre brand pill, keeping attention on players and LIVE text."""
    font = load_robust_font(82)  # Compact top-centre wordmark, matching the channel banner.
    parts = str(channel_text or "PREET SPORTS").strip().split(maxsplit=1)
    if len(parts) == 2:
        first, second = parts[0], parts[1]
    else:
        first, second = str(channel_text or "PREET SPORTS"), ""
    bbox1 = draw.textbbox((0, 0), first, font=font)
    bbox2 = draw.textbbox((0, 0), second, font=font) if second else (0, 0, 0, 0)
    w1, h1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
    w2 = bbox2[2] - bbox2[0]
    h2 = bbox2[3] - bbox2[1] if second else h1
    gap = 18 if second else 0
    total_w = w1 + gap + w2
    total_h = max(h1, h2)
    center_x = CANVAS_WIDTH // 2
    pad_x, pad_y = 32, 13
    x0 = center_x - total_w // 2 - pad_x
    x1 = center_x + total_w // 2 + pad_x
    y0, y1 = 28, 28 + total_h + 2 * pad_y
    radius = (y1 - y0) // 2
    draw_pill_badge(draw, (x0, y0, x1, y1), (255, 255, 255, 255), (10, 10, 10, 255), 7, radius)
    draw.rounded_rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), radius=radius + 4, outline=(22, 70, 150, 255), width=4)
    text_x = center_x - total_w // 2
    text_y = y0 + (y1 - y0 - total_h) // 2 - bbox1[1]
    draw.text((text_x, text_y), first, font=font, fill=(20, 69, 137, 255))
    if second:
        draw.text((text_x + w1 + gap, text_y), second, font=font, fill=(211, 24, 35, 255))


def draw_arrow_banner(draw, x, y, width, height, text, font, side):
    # Left nameplate points inward to the right; right nameplate points inward to the left.
    if side == "left":
        points = [(x, y), (x + width - height // 2, y), (x + width, y + height // 2),
                  (x + width - height // 2, y + height), (x, y + height)]
    else:
        points = [(x + height // 2, y), (x + width, y), (x + width, y + height),
                  (x + height // 2, y + height), (x, y + height // 2)]
    draw.polygon(points, fill=(0, 0, 0, 255))
    draw.line(points + [points[0]], fill=(255, 255, 255, 255), width=12, joint="curve")

    # Shrink long team names to fit the banner.
    max_text_width = int(width * 0.77)
    text_font = font
    while text_font.size > 80 and draw.textbbox((0, 0), text, font=text_font)[2] > max_text_width:
        text_font = load_robust_font(text_font.size - 8)
    bbox = draw.textbbox((0, 0), text, font=text_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x + (width - tw) // 2
    ty = y + (height - th) // 2 - bbox[1]
    draw.text((tx, ty), text, font=text_font, fill=(255, 255, 255, 255))


def draw_round_flag(overlay, draw, flag_image, x, y, size):
    if flag_image is None:
        return
    flag = flag_image.convert("RGBA")
    # Center-crop the flag into a circle so it behaves like the round flag badges in reference 1.
    side = min(flag.width, flag.height)
    left = (flag.width - side) // 2
    top = (flag.height - side) // 2
    flag = flag.crop((left, top, left + side, top + side)).resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    overlay.paste(flag, (x, y), mask)
    draw.ellipse((x - 7, y - 7, x + size + 7, y + size + 7), outline=(255, 255, 255, 255), width=14)


# Official-ish broadcast palettes chosen by common team labels. These are graphic
# theme colours, not claims about a team's official brand specification.
TEAM_COLOR_PALETTES = {
    "IND": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "INDIA": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "IND WOMEN": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "IND-W": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "IND W": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "PAK": ((0, 111, 67), (190, 245, 120), (0, 53, 35)),
    "PAKISTAN": ((0, 111, 67), (190, 245, 120), (0, 53, 35)),
    "SL": ((15, 54, 125), (255, 190, 20), (4, 24, 65)),
    "SRI LANKA": ((15, 54, 125), (255, 190, 20), (4, 24, 65)),
    "AUS": ((0, 70, 170), (255, 190, 0), (0, 28, 83)),
    "AUSTRALIA": ((0, 70, 170), (255, 190, 0), (0, 28, 83)),
    "AUS WOMEN": ((0, 70, 170), (255, 190, 0), (0, 28, 83)),
    "NZ": ((16, 28, 48), (0, 184, 220), (3, 9, 20)),
    "NEW ZEALAND": ((16, 28, 48), (0, 184, 220), (3, 9, 20)),
    "NZ WOMEN": ((16, 28, 48), (0, 184, 220), (3, 9, 20)),
    # West Indies palette follows the visible maroon jersey with gold accents.
    "WI": ((139, 18, 58), (255, 211, 35), (67, 5, 27)),
    "WEST INDIES": ((139, 18, 58), (255, 211, 35), (67, 5, 27)),
    "ENG": ((15, 49, 112), (210, 230, 255), (4, 18, 55)),
    "ENGLAND": ((15, 49, 112), (210, 230, 255), (4, 18, 55)),
    "ZIM": ((0, 112, 75), (255, 203, 0), (0, 56, 38)),
    "ZIMBABWE": ((0, 112, 75), (255, 203, 0), (0, 56, 38)),
    "ZIM-W": ((0, 112, 75), (255, 203, 0), (0, 56, 38)),
    "ZIM W": ((0, 112, 75), (255, 203, 0), (0, 56, 38)),
    "SA": ((0, 105, 76), (255, 205, 0), (0, 43, 34)),
    "SOUTH AFRICA": ((0, 105, 76), (255, 205, 0), (0, 43, 34)),
    "BAN": ((0, 106, 78), (235, 245, 235), (0, 48, 36)),
    "BANGLADESH": ((0, 106, 78), (235, 245, 235), (0, 48, 36)),
    "AFG": ((25, 75, 160), (75, 190, 120), (8, 35, 90)),
    "AFGHANISTAN": ((25, 75, 160), (75, 190, 120), (8, 35, 90)),
}


def team_palette(team_name):
    """Return (main, accent, shadow) colors for a team label."""
    key = normalize_team_name(team_name)
    palette = TEAM_COLOR_PALETTES.get(key)
    if palette:
        return palette
    key = key.replace(" WOMEN", "").replace(" MEN", "")
    return TEAM_COLOR_PALETTES.get(key, ((24, 77, 185), (255, 145, 25), (5, 25, 75)))


def draw_team_flag_watermark(canvas, flag_image, x, y, size, main_color, accent_color,
                             opacity=225, team_label=""):
    """Draw a circular flag/logo badge; use a readable team monogram if no flag loaded."""
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.ellipse((3, 3, size - 4, size - 4), fill=(*main_color, min(240, opacity)),
               outline=(255, 255, 255, 245), width=18)
    bd.ellipse((17, 17, size - 18, size - 18), outline=(*accent_color, 255), width=9)

    if flag_image is not None:
        flag = flag_image.convert("RGBA")
        # Contain-fit the full rectangular flag on the badge; don't crop identifying details.
        max_flag = int(size * 0.72)
        scale = min(max_flag / max(1, flag.width), max_flag / max(1, flag.height))
        flag = flag.resize((max(1, int(flag.width * scale)), max(1, int(flag.height * scale))), Image.Resampling.LANCZOS)
        fa = flag.getchannel("A").point(lambda value: int(value * opacity / 255))
        flag.putalpha(fa)
        fx = (size - flag.width) // 2
        fy = (size - flag.height) // 2
        badge.alpha_composite(flag, (fx, fy))
    else:
        # Never leave an empty ring when a team has no separate flag asset (e.g. West Indies).
        label = (team_label or "TEAM").upper().replace(" WOMEN", "").replace(" MEN", "")
        label = {"WEST INDIES": "WI", "INDIA": "IND", "ZIMBABWE": "ZIM"}.get(label, label[:3])
        font = load_robust_font(max(36, int(size * (0.27 if len(label) > 3 else 0.34))))
        bbox = bd.textbbox((0, 0), label, font=font, stroke_width=1)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (size - tw) // 2
        ty = (size - th) // 2 - bbox[1]
        bd.text((tx, ty), label, font=font, fill=(255, 255, 255, 255),
                stroke_width=2, stroke_fill=(*accent_color, 255))

    # Outer rings keep a clear logo edge when it sits over the tinted team panel.
    bd = ImageDraw.Draw(badge)
    bd.ellipse((3, 3, size - 4, size - 4), outline=(255, 255, 255, 250), width=18)
    bd.ellipse((17, 17, size - 18, size - 18), outline=(*accent_color, 255), width=8)
    canvas.alpha_composite(badge, (x, y))


def draw_team_color_backplates(canvas, team1_name, team2_name, flag1, flag2):
    """Add diagonal team-colour panels, accent slashes and flag watermarks behind players.

    The stadium remains visible through the colour panels and across the central pitch,
    mimicking compact team-colour YouTube live thumbnails rather than using a flat backdrop.
    """
    left_main, left_accent, left_dark = team_palette(team1_name)
    right_main, right_accent, right_dark = team_palette(team2_name)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = canvas.size
    panel_bottom = int(h * 0.86)
    left_inner_x = int(w * 0.34)
    left_outer_diag_x = int(w * 0.435)
    right_inner_x = int(w * 0.66)
    right_outer_diag_x = int(w * 0.565)

    # OPAQUE-LEANING team panels: the jersey/flag colours must visibly replace the
    # old blue stadium tint, while the central strip keeps the real stadium visible.
    # Strong alpha is intentional; the previous low-opacity panels looked unchanged.
    d.polygon([(0, 0), (int(w * .34), 0), (int(w * .405), panel_bottom), (0, panel_bottom)],
              fill=(*left_main, 218))
    d.polygon([(w, 0), (int(w * .66), 0), (int(w * .595), panel_bottom), (w, panel_bottom)],
              fill=(*right_main, 218))

    # Dark outer edge adds depth and keeps portraits readable against bright kits.
    d.polygon([(0, 0), (int(w * .12), 0), (int(w * .22), panel_bottom), (0, panel_bottom)],
              fill=(*left_dark, 78))
    d.polygon([(w, 0), (int(w * .88), 0), (int(w * .78), panel_bottom), (w, panel_bottom)],
              fill=(*right_dark, 78))

    # Clean, narrow team-accent stripes echo the orange/green-gold jersey and flag accents.
    d.polygon([(int(w * .285), 0), (int(w * .302), 0), (int(w * .365), panel_bottom),
               (int(w * .348), panel_bottom)], fill=(*left_accent, 235))
    d.polygon([(int(w * .715), 0), (int(w * .698), 0), (int(w * .635), panel_bottom),
               (int(w * .652), panel_bottom)], fill=(*right_accent, 235))
    canvas.alpha_composite(layer)

    # Keep the centre bright and stadium-led like the reference thumbnail, instead
    # of the dark rounded navy slab that made the previous text treatment look different.
    centre = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(centre)
    cd.rectangle((int(w * .34), 0, int(w * .66), int(h * .69)), fill=(205, 226, 248, 82))
    # A restrained light-blue veil improves text contrast but leaves the pitch visible.
    canvas.alpha_composite(centre)

    # Large faded team logos/flags sit BEHIND the players. Player cutouts are composited next.
    watermark_size = 285
    draw_team_flag_watermark(canvas, flag1, 30, 58, watermark_size, left_main, left_accent,
                             opacity=145, team_label=team1_name)
    draw_team_flag_watermark(canvas, flag2, w - watermark_size - 30, 58, watermark_size, right_main, right_accent,
                             opacity=145, team_label=team2_name)


def generate_thumbnail(bg_img, p1_img, p2_img, channel_text, match_status, match_badge,
                       t1_name, t2_name, t1_flag, t2_flag, commentary_text="HINDI COMMENTARY"):
    # Real stadium first; use a hand-drawn stadium only if the remote image is unavailable.
    if bg_img is None:
        bg_img = fetch_default_stadium_background()
    if bg_img is not None:
        canvas = resize_cover(bg_img, CANVAS_WIDTH, CANVAS_HEIGHT)
        canvas = canvas.filter(ImageFilter.GaussianBlur(1.1))
        canvas = ImageEnhance.Color(canvas).enhance(1.10)
        canvas = ImageEnhance.Contrast(canvas).enhance(1.05)
    else:
        canvas = generate_procedural_stadium()

    # A subtle translucent vignette keeps the middle typography legible without hiding the ground.
    vignette = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    vdraw.rectangle((0, int(CANVAS_HEIGHT * 0.79), CANVAS_WIDTH, CANVAS_HEIGHT), fill=(0, 0, 0, 48))
    canvas = Image.alpha_composite(canvas, vignette)

    # Reference channel style: diagonal team-colour panels and muted team logos BEHIND players.
    draw_team_color_backplates(canvas, t1_name, t2_name, t1_flag, t2_flag)

    # Captain cutouts are layered above the stadium and team panels, below the text.
    render_player_cutout(canvas, p1_img, "left")
    render_player_cutout(canvas, p2_img, "right")

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw_brand_pill(draw, channel_text)

    # Reference-style LIVE: red face, strong black offset shadow, thin white keyline.
    # Keep the exact centered position/layout; only the colour treatment changes.
    font_live = load_robust_font(520)
    live_label = str(match_status or "LIVE")
    live_bbox = draw.textbbox((0, 0), live_label, font=font_live, stroke_width=10)
    live_w = live_bbox[2] - live_bbox[0]
    live_x = (CANVAS_WIDTH - live_w) // 2
    live_y = 405 - live_bbox[1]
    draw.text((live_x + 22, live_y + 20), live_label, font=font_live,
              fill=(5, 8, 16, 255), stroke_width=15, stroke_fill=(5, 8, 16, 255))
    draw.text((live_x, live_y), live_label, font=font_live,
              fill=(235, 13, 24, 255), stroke_width=10, stroke_fill=(255, 255, 255, 255))

    # Match badge now follows the reference palette: black panel with bright yellow text.
    font_sub = load_robust_font(178)
    badge_text = str(match_badge or "MATCH DAY")
    sub_bbox = draw.textbbox((0, 0), badge_text, font=font_sub, stroke_width=0)
    sw, sh = sub_bbox[2] - sub_bbox[0], sub_bbox[3] - sub_bbox[1]
    badge_w = sw + 200
    badge_h = sh + 50
    bx0 = (CANVAS_WIDTH - badge_w) // 2
    by0 = 900
    draw.rounded_rectangle(
        (bx0, by0, bx0 + badge_w, by0 + badge_h), radius=20,
        fill=(5, 7, 13, 248), outline=(255, 205, 0, 255), width=10
    )
    tx = (CANVAS_WIDTH - sw) // 2
    ty = by0 + (badge_h - sh) // 2 - sub_bbox[1]
    draw.text((tx, ty), badge_text, font=font_sub, fill=(255, 230, 0, 255))

    # Secondary Hindi Commentary box directly below the T20 / match-format badge.
    # Palette: deep navy fill, saffron outer border, white inner border, yellow/white text.
    commentary_label = str(commentary_text or "HINDI COMMENTARY").strip().upper()
    if commentary_label:
        font_commentary = load_robust_font(82)
        # Reduce the label font only if a user enters unusually long text.
        while font_commentary.size > 64 and draw.textbbox((0, 0), commentary_label, font=font_commentary)[2] > 1750:
            font_commentary = load_robust_font(font_commentary.size - 6)
        cbbox = draw.textbbox((0, 0), commentary_label, font=font_commentary)
        ctext_w = cbbox[2] - cbbox[0]
        ctext_h = cbbox[3] - cbbox[1]
        commentary_w = ctext_w + 112
        commentary_h = max(104, ctext_h + 34)
        commentary_x = (CANVAS_WIDTH - commentary_w) // 2
        commentary_y = by0 + badge_h + 16
        # Keep it safely above the team banners even if fonts vary by host.
        banner_top = CANVAS_HEIGHT - 330 - 70
        commentary_y = min(commentary_y, banner_top - commentary_h - 20)
        draw.rounded_rectangle(
            (commentary_x, commentary_y, commentary_x + commentary_w, commentary_y + commentary_h),
            radius=18,
            fill=(9, 48, 117, 248),
            outline=(255, 255, 255, 255),
            width=8,
        )
        inner_pad = 9
        draw.rounded_rectangle(
            (commentary_x + inner_pad, commentary_y + inner_pad,
             commentary_x + commentary_w - inner_pad, commentary_y + commentary_h - inner_pad),
            radius=max(20, commentary_h // 2 - inner_pad),
            outline=(255, 255, 255, 230),
            width=3,
        )
        # Split the default label so HINDI is highlighted yellow and COMMENTARY is white.
        if commentary_label == "HINDI COMMENTARY":
            first_word, second_word = "HINDI", "COMMENTARY"
            first_bbox = draw.textbbox((0, 0), first_word, font=font_commentary)
            second_bbox = draw.textbbox((0, 0), second_word, font=font_commentary)
            first_w = first_bbox[2] - first_bbox[0]
            second_w = second_bbox[2] - second_bbox[0]
            spacing = 18
            start_x = (CANVAS_WIDTH - first_w - spacing - second_w) // 2
            text_y = commentary_y + (commentary_h - ctext_h) // 2 - cbbox[1]
            draw.text((start_x, text_y), first_word, font=font_commentary, fill=(255, 220, 0, 255))
            draw.text((start_x + first_w + spacing, text_y), second_word, font=font_commentary, fill=(255, 255, 255, 255))
        else:
            text_x = (CANVAS_WIDTH - ctext_w) // 2
            text_y = commentary_y + (commentary_h - ctext_h) // 2 - cbbox[1]
            draw.text((text_x, text_y), commentary_label, font=font_commentary, fill=(255, 255, 255, 255))

    # Bold inward-pointing team labels at the bottom.
    font_team = load_robust_font(225)
    banner_w, banner_h = 1260, 330
    banner_y = CANVAS_HEIGHT - banner_h - 70
    draw_arrow_banner(draw, 0, banner_y, banner_w, banner_h, normalize_team_name(t1_name), font_team, "left")
    draw_arrow_banner(draw, CANVAS_WIDTH - banner_w, banner_y, banner_w, banner_h, normalize_team_name(t2_name), font_team, "right")

    # Team flag/logo badges are deliberately behind the portraits, not on top of the players' heads.

    return Image.alpha_composite(canvas, overlay)


# =========================================================
# STREAMLIT UI
# =========================================================
st.title("🏏 PREET SPORTS — 4K Cricket Thumbnail Studio")
st.caption("Balanced left/right player cutouts; compact centered LIVE / match-format / commentary stack; team-colour side panels; blue PREET and red SPORTS branding; bold inward-facing team banners; 3840 × 2160 PNG export.")

for key in ["p1_cutout", "p2_cutout", "p1_ai_front", "p2_ai_front", "p1_ai_source_hash", "p2_ai_source_hash", "t1_code", "t2_code", "auto_bg", "reference_left_cutout", "reference_right_cutout", "reference_thumbnail_hash"]:
    if key not in st.session_state:
        st.session_state[key] = None
if "_reference_pending_extractions" not in st.session_state:
    st.session_state["_reference_pending_extractions"] = []
if "_reference_extraction_messages" not in st.session_state:
    st.session_state["_reference_extraction_messages"] = []

col_left, col_right = st.columns([1, 1.2], gap="large")

with col_left:
    st.subheader("1. Match & Captain Auto-Fetch")
    match_url = st.text_input(
        "Paste ESPNcricinfo Match / Squad URL (optional)",
        placeholder="https://www.espncricinfo.com/series/.../match-squads",
        key="match_page_url",
    )
    if st.button("🚀 Auto-Extract Captains from Match Page", type="primary", use_container_width=True):
        if not match_url.strip():
            st.warning("Paste the match-squad URL first.")
        elif "cricinfo.com" not in match_url.lower():
            st.warning("Use an ESPNcricinfo match/squad page URL, or paste direct player image URLs below.")
        else:
            with st.spinner("Reading the squad page and fetching the highest-resolution accessible captain images..."):
                teams, err = fetch_from_cricinfo_url(match_url.strip())
                if teams:
                    st.session_state.t1_code = teams[0]["name"]
                    st.session_state.t2_code = teams[1]["name"]
                    st.session_state["team1_name_input"] = teams[0]["name"]
                    st.session_state["team2_name_input"] = teams[1]["name"]
                    if teams[0].get("img_url"):
                        img1 = fetch_online_image(teams[0]["img_url"])
                        if img1:
                            st.session_state.p1_cutout = img1
                            st.session_state["left_captain_image_url"] = teams[0]["img_url"]
                    if teams[1].get("img_url"):
                        img2 = fetch_online_image(teams[1]["img_url"])
                        if img2:
                            st.session_state.p2_cutout = img2
                            st.session_state["right_captain_image_url"] = teams[1]["img_url"]
                    loaded_count = int(st.session_state.p1_cutout is not None) + int(st.session_state.p2_cutout is not None)
                    if loaded_count == 2:
                        st.success(f"Fetched images for {teams[0]['name']} and {teams[1]['name']}.")
                    else:
                        st.warning("Team names were found, but one or both captain photos were unavailable. Paste direct image URLs below.")
                else:
                    st.warning(err)

    st.subheader("2. Direct Captain Image URLs")
    st.caption("Paste a direct image URL or an ICC player-profile URL. ICC profile pages are automatically resolved to their matching player image. For this IND-W vs ZIM-W preset, paste the desired player profile or direct image URLs below. Compact flags sit in the top corners; the right player is anchored to the far-right edge.")
    left_captain_url = st.text_input(
        "Left Captain Image / ICC Profile URL (India Women)",
        value="",
        placeholder="Paste a direct image or ICC player-profile URL",
        key="left_captain_image_url",
    )
    right_captain_url = st.text_input(
        "Right Captain Image / ICC Profile URL (Zimbabwe Women)",
        value="",
        placeholder="Paste a direct image or ICC player-profile URL",
        key="right_captain_image_url",
    )
    if st.button("🖼️ Fetch / Refresh Captain Images", use_container_width=True):
        attempts, loaded = 0, 0
        if left_captain_url.strip():
            attempts += 1
            resolved_left_url = resolve_player_image_url(left_captain_url.strip())
            image_left = fetch_online_image(resolved_left_url) if resolved_left_url else None
            if image_left is not None:
                st.session_state.p1_cutout = image_left
                loaded += 1
            else:
                st.error("Left image could not be downloaded. Check that the URL is public and points directly to an image.")
        if right_captain_url.strip():
            attempts += 1
            resolved_right_url = resolve_player_image_url(right_captain_url.strip())
            image_right = fetch_online_image(resolved_right_url) if resolved_right_url else None
            if image_right is not None:
                st.session_state.p2_cutout = image_right
                loaded += 1
            else:
                st.error("Right image could not be downloaded. Check that the URL is public and points directly to an image.")
        if attempts == 0:
            st.warning("Paste at least one captain image URL first.")
        elif loaded:
            st.success(f"Loaded {loaded} image{'s' if loaded != 1 else ''}. Preview refreshed.")

    st.subheader("3. Match Details")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        team1 = st.text_input("Left Team Name", value=st.session_state.t1_code or "IND-W", key="team1_name_input").strip().upper()
    with col_t2:
        team2 = st.text_input("Right Team Name", value=st.session_state.t2_code or "ZIM-W", key="team2_name_input").strip().upper()

    col_status, col_badge = st.columns(2)
    with col_status:
        match_status = st.text_input("Main Text", value="LIVE", key="match_status_input")
    with col_badge:
        match_badge = st.text_input("Match Format / Badge", value="T20", key="match_badge_input")
    commentary_text = st.text_input("Box below T20 badge", value="HINDI COMMENTARY", key="commentary_text_input")
    channel_title = st.text_input("Channel Brand", value="PREET SPORTS", key="channel_title_input")

    st.subheader("4. Remove Background from Any Image")
    st.caption(
        "Background removal uses local U2NETP only when weights are already cached; otherwise it quickly falls back to OpenCV GrabCut. "
        "No Gemini API request is made. Results are cached for 30 days; cropping and 4K composition remain local."
    )
    any_image_upload = st.file_uploader(
        "Choose any image to remove its background",
        type=["png", "jpg", "jpeg", "webp"],
        key="generic_background_removal_upload",
    )
    if st.button("✂️ Remove Background", type="primary", use_container_width=True, key="remove_any_background_button"):
        if not any_image_upload:
            st.warning("Upload an image first.")
        else:
            with st.spinner("Removing background locally… uses cached U2NETP if available; otherwise fast OpenCV fallback."):
                transparent_result, bg_remove_error = remove_background_from_any_image(
                    any_image_upload.getvalue(), any_image_upload.name
                )
            if transparent_result is not None:
                st.session_state["generic_bg_removed_png"] = transparent_result
                st.session_state["generic_bg_removed_name"] = any_image_upload.name
                st.success("Background removed. Preview and download your transparent PNG below.")
            else:
                st.error(bg_remove_error or "Could not remove the background.")

    if st.session_state.get("generic_bg_removed_png") is not None:
        removed_image = st.session_state["generic_bg_removed_png"]
        source_name = st.session_state.get("generic_bg_removed_name", "image")
        preview_col, download_col = st.columns([1, 1])
        with preview_col:
            st.image(removed_image, caption="Background removed", use_container_width=True)
        with download_col:
            png_buffer = io.BytesIO()
            removed_image.save(png_buffer, format="PNG", optimize=False)
            base_name = re.sub(r"[^A-Za-z0-9_-]+", "_", os.path.splitext(source_name)[0]).strip("_") or "image"
            st.download_button(
                "⬇️ Download Transparent PNG",
                data=png_buffer.getvalue(),
                file_name=f"{base_name}_background_removed.png",
                mime="image/png",
                use_container_width=True,
                key="download_generic_background_removed",
            )

    st.subheader("5. Remove Background from Cropped Player Images (Local)")
    st.caption(
        "Upload the already-cropped left and right player photos. The app uses the preloaded lightweight U2NETP model when available; it never downloads model weights during a user request, and falls back to OpenCV when weights are missing. "
        "No Gemini API request is made. For clarity, the reference crop download buttons above save the raw crop with its background; use the Remove Background or Extract buttons to create transparency. The cutouts can be applied "
        "directly to the left/right player slots in your thumbnail."
    )
    cutout_left_col, cutout_right_col = st.columns(2)
    with cutout_left_col:
        cropped_left_upload = st.file_uploader(
            "Upload cropped LEFT player image",
            type=["png", "jpg", "jpeg", "webp"],
            key="cropped_player_left_upload_v1",
        )
        if cropped_left_upload is not None:
            left_source_bytes = cropped_left_upload.getvalue()
            left_source_hash = hashlib.sha1(left_source_bytes).hexdigest()
            if st.session_state.get("cropped_left_source_hash") != left_source_hash:
                st.session_state["cropped_left_source_hash"] = left_source_hash
                st.session_state["cropped_left_transparent"] = None
            if st.button("✂️ Remove LEFT background", use_container_width=True, key="remove_cropped_left_bg_v1"):
                with st.spinner("Removing the LEFT background locally…"):
                    cutout, cutout_error = remove_background_from_any_image(left_source_bytes, cropped_left_upload.name)
                if cutout is not None:
                    st.session_state["cropped_left_transparent"] = cutout
                    st.session_state.p1_cutout = cutout
                    st.session_state["reference_left_cutout"] = cutout
                    st.success("Left player background removed. This transparent cutout is now selected for the thumbnail.")
                else:
                    st.error(cutout_error or "Could not remove the left background.")
            if st.session_state.get("cropped_left_transparent") is not None:
                left_transparent = st.session_state["cropped_left_transparent"]
                st.image(left_transparent, caption="LEFT player — transparent preview", use_container_width=True)
                left_transparent_buffer = io.BytesIO()
                left_transparent.save(left_transparent_buffer, format="PNG", optimize=False)
                st.download_button(
                    "⬇️ Download LEFT transparent PNG",
                    data=left_transparent_buffer.getvalue(),
                    file_name="left_player_transparent.png",
                    mime="image/png",
                    use_container_width=True,
                    key="download_cropped_left_transparent_v1",
                )
    with cutout_right_col:
        cropped_right_upload = st.file_uploader(
            "Upload cropped RIGHT player image",
            type=["png", "jpg", "jpeg", "webp"],
            key="cropped_player_right_upload_v1",
        )
        if cropped_right_upload is not None:
            right_source_bytes = cropped_right_upload.getvalue()
            right_source_hash = hashlib.sha1(right_source_bytes).hexdigest()
            if st.session_state.get("cropped_right_source_hash") != right_source_hash:
                st.session_state["cropped_right_source_hash"] = right_source_hash
                st.session_state["cropped_right_transparent"] = None
            if st.button("✂️ Remove RIGHT background", use_container_width=True, key="remove_cropped_right_bg_v1"):
                with st.spinner("Removing the RIGHT background locally…"):
                    cutout, cutout_error = remove_background_from_any_image(right_source_bytes, cropped_right_upload.name)
                if cutout is not None:
                    st.session_state["cropped_right_transparent"] = cutout
                    st.session_state.p2_cutout = cutout
                    st.session_state["reference_right_cutout"] = cutout
                    st.success("Right player background removed. This transparent cutout is now selected for the thumbnail.")
                else:
                    st.error(cutout_error or "Could not remove the right background.")
            if st.session_state.get("cropped_right_transparent") is not None:
                right_transparent = st.session_state["cropped_right_transparent"]
                st.image(right_transparent, caption="RIGHT player — transparent preview", use_container_width=True)
                right_transparent_buffer = io.BytesIO()
                right_transparent.save(right_transparent_buffer, format="PNG", optimize=False)
                st.download_button(
                    "⬇️ Download RIGHT transparent PNG",
                    data=right_transparent_buffer.getvalue(),
                    file_name="right_player_transparent.png",
                    mime="image/png",
                    use_container_width=True,
                    key="download_cropped_right_transparent_v1",
                )

    st.subheader("6. Reference Thumbnail Player Extractor")
    st.caption(
        "Upload another cricket thumbnail, crop around each player, and create transparent PNG cutouts using cached local U2NETP when available, with a fast OpenCV fallback. "
        "This avoids Gemini API calls. Players are processed one at a time to reduce memory use and help avoid Render 502 disconnects. "
        "Segmentation may leave text or graphics that touch/overlap the player, and it cannot reconstruct hidden pixels. "
        "Use only images you have permission to reuse. Successful extractions are cached for 30 days."
    )
    st.markdown("**Option A — Load reference thumbnail from an image URL**")
    reference_thumbnail_url = st.text_input(
        "Reference thumbnail image URL",
        placeholder="https://example.com/cricket-thumbnail.jpg",
        key="reference_thumbnail_image_url",
        help="Use a direct, publicly accessible image URL ending in JPG, PNG, or WebP. A normal webpage URL may not work.",
    )
    if st.button("🌐 Load thumbnail from URL", use_container_width=True, key="load_reference_thumbnail_url"):
        if not reference_thumbnail_url.strip():
            st.warning("Paste a direct thumbnail image URL first.")
        else:
            with st.spinner("Fetching reference thumbnail from URL…"):
                fetched_reference = fetch_online_image(reference_thumbnail_url.strip())
            if fetched_reference is None:
                st.error("Could not load that URL as an image. Use a direct, public JPG/PNG/WebP image URL, not a webpage or a private/expired link.")
            else:
                ref_buffer = io.BytesIO()
                fetched_reference.convert("RGB").save(ref_buffer, format="PNG")
                st.session_state["reference_thumbnail_url_bytes"] = ref_buffer.getvalue()
                st.session_state["reference_thumbnail_url_name"] = "reference_thumbnail_from_url.png"
                st.session_state["reference_thumbnail_url_loaded"] = reference_thumbnail_url.strip()
                st.session_state["reference_thumbnail_hash"] = None
                st.session_state["reference_left_cutout"] = None
                st.session_state["reference_right_cutout"] = None
                st.success("Reference thumbnail loaded. Adjust the crop sliders, then extract both players.")

    st.markdown("**Option B — Upload a reference thumbnail file**")
    reference_thumbnail = st.file_uploader(
        "Upload reference thumbnail (PNG/JPG/WebP)",
        type=["png", "jpg", "jpeg", "webp"],
        key="reference_thumbnail_upload",
    )
    # Uploaded file takes priority. Otherwise use the image previously loaded from URL.
    if reference_thumbnail is not None:
        reference_thumbnail_bytes = reference_thumbnail.getvalue()
        reference_thumbnail_name = reference_thumbnail.name
        # Keep uploaded bytes in this user's Streamlit session so normal reruns and
        # transient websocket reconnects don't discard the source image.
        st.session_state["reference_thumbnail_uploaded_bytes"] = reference_thumbnail_bytes
        st.session_state["reference_thumbnail_uploaded_name"] = reference_thumbnail_name
    else:
        reference_thumbnail_bytes = st.session_state.get("reference_thumbnail_url_bytes")
        reference_thumbnail_name = st.session_state.get("reference_thumbnail_url_name", "reference_thumbnail_from_url.png")
        if reference_thumbnail_bytes is None:
            reference_thumbnail_bytes = st.session_state.get("reference_thumbnail_uploaded_bytes")
            reference_thumbnail_name = st.session_state.get("reference_thumbnail_uploaded_name", "reference_thumbnail_recovered.png")

    use_reference_cutouts = st.checkbox(
        "Use extracted reference players in my PREET SPORTS thumbnail",
        value=True,
        key="use_reference_cutouts_checkbox",
    )
    if reference_thumbnail_bytes is not None:
        ref_bytes = reference_thumbnail_bytes
        ref_hash = hashlib.sha1(ref_bytes).hexdigest()
        if st.session_state.get("reference_thumbnail_hash") != ref_hash:
            st.session_state["reference_thumbnail_hash"] = ref_hash
            st.session_state["reference_left_cutout"] = None
            st.session_state["reference_right_cutout"] = None
        try:
            with Image.open(io.BytesIO(ref_bytes)) as ref_opened:
                ref_image = ref_opened.convert("RGB")
            st.image(ref_image, caption=f"Reference thumbnail: {ref_image.width} × {ref_image.height}", use_container_width=True)
            st.caption("Adjust each crop so it contains one player as fully as possible. Avoid including the LIVE text and team banners.")
            crop_left_col, crop_right_col = st.columns(2)
            with crop_left_col:
                st.markdown("**Left player crop**")
                # Reference-thumbnail defaults: keep the left player on the left third,
                # exclude most of the central LIVE/text area, and include the full torso.
                # Versioned widget keys reset previously saved slider positions on deploy.
                left_x_range = st.slider("Horizontal range (%) — left", 0, 100, (0, 43), key="ref_left_x_range_v3")
                left_y_range = st.slider("Vertical range (%) — left", 0, 100, (8, 100), key="ref_left_y_range_v3")
            with crop_right_col:
                st.markdown("**Right player crop**")
                right_x_range = st.slider("Horizontal range (%) — right", 0, 100, (50, 100), key="ref_right_x_range_v3")
                right_y_range = st.slider("Vertical range (%) — right", 0, 100, (8, 100), key="ref_right_y_range_v3")

            def _reference_crop(image, x_range, y_range):
                x0 = int(image.width * x_range[0] / 100)
                x1 = int(image.width * x_range[1] / 100)
                y0 = int(image.height * y_range[0] / 100)
                y1 = int(image.height * y_range[1] / 100)
                x1 = max(x0 + 1, min(image.width, x1))
                y1 = max(y0 + 1, min(image.height, y1))
                return image.crop((x0, y0, x1, y1))

            ref_left_crop = _reference_crop(ref_image, left_x_range, left_y_range)
            ref_right_crop = _reference_crop(ref_image, right_x_range, right_y_range)
            crop_prev1, crop_prev2 = st.columns(2)
            with crop_prev1:
                st.image(ref_left_crop, caption="Left crop preview", use_container_width=True)
                left_crop_buffer = io.BytesIO()
                ref_left_crop.save(left_crop_buffer, format="PNG")
                st.download_button(
                    "Download LEFT raw crop (background included)",
                    data=left_crop_buffer.getvalue(),
                    file_name="reference_left_crop.png",
                    mime="image/png",
                    use_container_width=True,
                    key="download_ref_left_crop_only",
                )
            with crop_prev2:
                st.image(ref_right_crop, caption="Right crop preview", use_container_width=True)
                right_crop_buffer = io.BytesIO()
                ref_right_crop.save(right_crop_buffer, format="PNG")
                st.download_button(
                    "Download RIGHT raw crop (background included)",
                    data=right_crop_buffer.getvalue(),
                    file_name="reference_right_crop.png",
                    mime="image/png",
                    use_container_width=True,
                    key="download_ref_right_crop_only",
                )

            extract_both_clicked = st.button(
                "✂️ Extract BOTH players & apply to thumbnail",
                use_container_width=True,
                type="primary",
                key="extract_reference_both_apply",
                help="Runs face-guided local segmentation, saves transparent PNG cutouts, and assigns them directly to the left/right thumbnail slots. No manual PNG download is needed.",
            )
            extract_col1, extract_col2 = st.columns(2)
            with extract_col1:
                extract_left_clicked = st.button("✂️ Extract LEFT only", use_container_width=True, key="extract_reference_left")
            with extract_col2:
                extract_right_clicked = st.button("✂️ Extract RIGHT only", use_container_width=True, key="extract_reference_right")

            def _crop_jpeg_bytes(crop):
                # Convert crop to a compact local-model input. No API request is made.
                crop_rgb = crop.convert("RGB")
                max_side = int(os.environ.get("PREET_GRABCUT_MAX_SIDE", "512"))
                max_side = max(320, min(max_side, 640))
                if max(crop_rgb.size) > max_side:
                    scale = max_side / max(crop_rgb.size)
                    crop_rgb = crop_rgb.resize((max(1, int(crop_rgb.width * scale)), max(1, int(crop_rgb.height * scale))), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                crop_rgb.save(buf, format="JPEG", quality=84, optimize=False)
                return buf.getvalue()

            def _queue_reference_extraction(side, crop):
                # Persist compact crop bytes in Session State. Process one crop per
                # Streamlit run to lower peak RAM and avoid a single long request
                # that can cause a Render 502/disconnect.
                return {
                    "side": side,
                    "source_bytes": _crop_jpeg_bytes(crop),
                    "filename": f"reference_{side}_player.jpg",
                }

            if extract_both_clicked:
                st.session_state["_reference_pending_extractions"] = [
                    _queue_reference_extraction("left", ref_left_crop),
                    _queue_reference_extraction("right", ref_right_crop),
                ]
                st.session_state["_reference_extraction_messages"] = []
                st.rerun()
            elif extract_left_clicked:
                st.session_state["_reference_pending_extractions"] = [
                    _queue_reference_extraction("left", ref_left_crop)
                ]
                st.session_state["_reference_extraction_messages"] = []
                st.rerun()
            elif extract_right_clicked:
                st.session_state["_reference_pending_extractions"] = [
                    _queue_reference_extraction("right", ref_right_crop)
                ]
                st.session_state["_reference_extraction_messages"] = []
                st.rerun()

            # Handle exactly one local GrabCut segmentation per request. After each inference,
            # save its result in session state and rerun so temporary arrays are released
            # before the next player or 4K composition.
            pending_extractions = st.session_state.get("_reference_pending_extractions", [])
            if pending_extractions:
                task = pending_extractions[0]
                st.session_state["_reference_pending_extractions"] = pending_extractions[1:]
                side = task["side"]
                with st.spinner(
                    f"Removing {side} player background… using cached local U2NETP if installed, otherwise the fast OpenCV fallback."
                ):
                    cutout, extract_error = remove_background_from_any_image(
                        task["source_bytes"], task.get("filename", f"reference_{side}_player.jpg")
                    )

                messages = st.session_state.setdefault("_reference_extraction_messages", [])
                if cutout is not None:
                    if side == "left":
                        st.session_state["reference_left_cutout"] = cutout
                        st.session_state.p1_cutout = cutout
                        st.session_state.p1_ai_front = None
                        st.session_state.p1_ai_source_hash = None
                    else:
                        st.session_state["reference_right_cutout"] = cutout
                        st.session_state.p2_cutout = cutout
                        st.session_state.p2_ai_front = None
                        st.session_state.p2_ai_source_hash = None
                    messages.append(f"{side.title()} player extracted and applied to the thumbnail.")
                else:
                    messages.append(f"{side.title()} player extraction failed: {extract_error or 'Unknown local segmentation error.'}")

                # Release local inference/result buffers before next queued crop or
                # the 4K renderer. No neural model session is needed.
                del cutout
                gc.collect()
                if st.session_state.get("_reference_pending_extractions"):
                    st.rerun()
                # Run one more clean pass before rendering the large 4K thumbnail.
                st.rerun()

            for extraction_message in st.session_state.get("_reference_extraction_messages", []):
                if "extraction failed:" in extraction_message.lower():
                    st.error(extraction_message)
                else:
                    st.success(extraction_message)

            saved_left, saved_right = st.columns(2)
            with saved_left:
                if st.session_state.get("reference_left_cutout") is not None:
                    st.image(st.session_state["reference_left_cutout"], caption="Extracted left player", use_container_width=True)
                    left_png = io.BytesIO()
                    st.session_state["reference_left_cutout"].save(left_png, format="PNG")
                    st.download_button("Download left cutout PNG", left_png.getvalue(), "reference_left_player.png", "image/png", use_container_width=True, key="download_ref_left_cutout")
            with saved_right:
                if st.session_state.get("reference_right_cutout") is not None:
                    st.image(st.session_state["reference_right_cutout"], caption="Extracted right player", use_container_width=True)
                    right_png = io.BytesIO()
                    st.session_state["reference_right_cutout"].save(right_png, format="PNG")
                    st.download_button("Download right cutout PNG", right_png.getvalue(), "reference_right_player.png", "image/png", use_container_width=True, key="download_ref_right_cutout")

            if st.button("🧹 Clear extracted reference players", key="clear_reference_cutouts"):
                st.session_state["reference_left_cutout"] = None
                st.session_state["reference_right_cutout"] = None
                st.rerun()
        except Exception as exc:
            st.error(f"Could not read the reference thumbnail: {exc}")
    else:
        use_reference_cutouts = False
        st.caption("Load a thumbnail using the URL option above or upload an image file to enable player extraction.")

    st.subheader("7. Background (optional override)")
    stadium_url = st.text_input(
        "Custom Stadium Background URL",
        value="",
        placeholder="Leave blank to use the built-in cricket stadium photo",
        key="stadium_background_url",
    )
    bg_file = st.file_uploader("Or upload your own 16:9 stadium background", type=["png", "jpg", "jpeg", "webp"])
    st.subheader("8. Optional AI Tool — Front-Facing Pose Conversion")
    st.info(
        "Everything else in this app—cropping, local background removal, cutout caching, thumbnail composition, and 4K PNG export—runs locally on this server and does not call Gemini. "
        "Only the Convert LEFT/RIGHT buttons below call Gemini. Pose conversion needs a configured GEMINI_API_KEY and available image-model quota; it may incur separate API charges. "
        "If Gemini is unavailable, continue using the local crop, background-removal, and thumbnail tools."
    )
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        custom_p1 = st.file_uploader(
            "Left player source photo (PNG/JPG/WebP)",
            type=["png", "jpg", "jpeg", "webp"],
            key="manual_left_player",
        )
        convert_left_clicked = st.button("✨ Convert LEFT to front-facing", use_container_width=True, key="convert_left_front")
    with col_up2:
        custom_p2 = st.file_uploader(
            "Right player source photo (PNG/JPG/WebP)",
            type=["png", "jpg", "jpeg", "webp"],
            key="manual_right_player",
        )
        convert_right_clicked = st.button("✨ Convert RIGHT to front-facing", use_container_width=True, key="convert_right_front")

    if convert_left_clicked:
        if not custom_p1:
            st.warning("Upload a left-player photo first.")
        else:
            source_bytes = custom_p1.getvalue()
            with st.spinner("AI is turning the left player toward the camera. This may take a little while…"):
                edited, error = convert_player_to_front_facing(source_bytes, custom_p1.name, "left")
            if edited is not None:
                st.session_state.p1_ai_front = edited
                st.session_state.p1_ai_source_hash = hashlib.sha1(source_bytes).hexdigest()
                st.success("Left player conversion is ready and will be used in the thumbnail.")
            else:
                st.error(error)

    if convert_right_clicked:
        if not custom_p2:
            st.warning("Upload a right-player photo first.")
        else:
            source_bytes = custom_p2.getvalue()
            with st.spinner("AI is turning the right player toward the camera. This may take a little while…"):
                edited, error = convert_player_to_front_facing(source_bytes, custom_p2.name, "right")
            if edited is not None:
                st.session_state.p2_ai_front = edited
                st.session_state.p2_ai_source_hash = hashlib.sha1(source_bytes).hexdigest()
                st.success("Right player conversion is ready and will be used in the thumbnail.")
            else:
                st.error(error)

# Resolve prefilled/profile image URLs on the first page load so the PAK vs SL defaults
# immediately show Shaheen Afridi (left) and Kusal Mendis (right). The URL/image functions are cached.
if st.session_state.p1_cutout is None and left_captain_url.strip():
    try:
        initial_left_url = resolve_player_image_url(left_captain_url.strip())
        initial_left_img = fetch_online_image(initial_left_url) if initial_left_url else None
        if initial_left_img is not None:
            st.session_state.p1_cutout = initial_left_img
    except Exception:
        pass
if st.session_state.p2_cutout is None and right_captain_url.strip():
    try:
        initial_right_url = resolve_player_image_url(right_captain_url.strip())
        initial_right_img = fetch_online_image(initial_right_url) if initial_right_url else None
        if initial_right_img is not None:
            st.session_state.p2_cutout = initial_right_img
    except Exception:
        pass

# Resolve player images: uploaded images override fetched URL images; URL images override team fallback.
c1_info = CAPTAIN_DATABASE.get(normalize_team_name(team1), {})
c2_info = CAPTAIN_DATABASE.get(normalize_team_name(team2), {})

def _uploaded_file_sha1(uploaded_file):
    return hashlib.sha1(uploaded_file.getvalue()).hexdigest() if uploaded_file else None


def _uploaded_file_is_transparent_cutout(uploaded_file):
    """True only if the uploaded file has real transparency, not merely an RGBA mode."""
    if not uploaded_file:
        return False
    try:
        with Image.open(io.BytesIO(uploaded_file.getvalue())) as candidate:
            if "A" not in candidate.getbands():
                return False
            return candidate.getchannel("A").getextrema()[0] < 250
    except Exception:
        return False


left_upload_hash = _uploaded_file_sha1(custom_p1)
right_upload_hash = _uploaded_file_sha1(custom_p2)
left_is_cutout = _uploaded_file_is_transparent_cutout(custom_p1)
right_is_cutout = _uploaded_file_is_transparent_cutout(custom_p2)

# A converted AI portrait is used only for the exact source file it was generated from.
# A normal opaque JPEG is treated as AI input, not pasted as a rectangle over the stadium.
if custom_p1 and st.session_state.p1_ai_front is not None and st.session_state.p1_ai_source_hash == left_upload_hash:
    p1_final = st.session_state.p1_ai_front
elif use_reference_cutouts and st.session_state.get("reference_left_cutout") is not None:
    p1_final = st.session_state["reference_left_cutout"]
elif custom_p1 and left_is_cutout:
    p1_final = Image.open(io.BytesIO(custom_p1.getvalue())).convert("RGBA")
elif st.session_state.p1_cutout is not None:
    p1_final = st.session_state.p1_cutout
elif c1_info.get("player_png"):
    p1_final = fetch_online_image(c1_info["player_png"])
else:
    p1_final = None

if custom_p2 and st.session_state.p2_ai_front is not None and st.session_state.p2_ai_source_hash == right_upload_hash:
    p2_final = st.session_state.p2_ai_front
elif use_reference_cutouts and st.session_state.get("reference_right_cutout") is not None:
    p2_final = st.session_state["reference_right_cutout"]
elif custom_p2 and right_is_cutout:
    p2_final = Image.open(io.BytesIO(custom_p2.getvalue())).convert("RGBA")
elif st.session_state.p2_cutout is not None:
    p2_final = st.session_state.p2_cutout
elif c2_info.get("player_png"):
    p2_final = fetch_online_image(c2_info["player_png"])
else:
    p2_final = None

if custom_p1 and not left_is_cutout and st.session_state.p1_ai_source_hash != left_upload_hash:
    st.info("Left upload has no transparent background yet. Press ‘Convert LEFT to front-facing’ to create a cutout.")
if custom_p2 and not right_is_cutout and st.session_state.p2_ai_source_hash != right_upload_hash:
    st.info("Right upload has no transparent background yet. Press ‘Convert RIGHT to front-facing’ to create a cutout.")

def _looks_like_square_headshot(image):
    """Detect a likely square squad portrait; this cannot prove the source is a headshot."""
    if image is None or image.height <= 0:
        return False
    ratio = image.width / image.height
    return 0.88 <= ratio <= 1.12

if _looks_like_square_headshot(p1_final) or _looks_like_square_headshot(p2_final):
    st.warning(
        "One or both player sources are nearly square. The app fits each source inside its fixed frame, "
        "but a cropped headshot does not contain the missing jersey or torso. Use full upper-body, "
        "preferably transparent PNG/WebP cutouts for the reference look."
    )

# Explicit background upload wins, then custom URL, then default real stadium photo.
if bg_file:
    bg_final = Image.open(bg_file).convert("RGBA")
elif stadium_url.strip():
    bg_final = fetch_online_image(stadium_url.strip())
    if bg_final is None:
        st.warning("Custom stadium URL could not be loaded. Using the default stadium background.")
        bg_final = fetch_default_stadium_background()
else:
    bg_final = fetch_default_stadium_background()

flag1_url = get_team_flag_url(team1)
flag2_url = get_team_flag_url(team2)
flag1 = fetch_online_image(flag1_url) if flag1_url else None
flag2 = fetch_online_image(flag2_url) if flag2_url else None

def _image_cache_key(image):
    """A stable, low-overhead fingerprint so the 4K composite isn't rebuilt on unrelated reruns."""
    if image is None:
        return None
    image = image.convert("RGBA")
    digest = hashlib.sha1(image.tobytes()).hexdigest()
    return (image.size, digest)


render_signature = (
    RENDER_PIPELINE_VERSION,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    normalize_team_name(team1),
    normalize_team_name(team2),
    str(channel_title),
    str(match_status),
    str(match_badge),
    str(commentary_text),
    _image_cache_key(bg_final),
    _image_cache_key(p1_final),
    _image_cache_key(p2_final),
    _image_cache_key(flag1),
    _image_cache_key(flag2),
)

if st.session_state.get("_thumbnail_signature") != render_signature:
    with st.spinner("Rendering your thumbnail…"):
        rendered = generate_thumbnail(
            bg_img=bg_final,
            p1_img=p1_final,
            p2_img=p2_final,
            channel_text=channel_title,
            match_status=match_status,
            match_badge=match_badge,
            t1_name=team1,
            t2_name=team2,
            t1_flag=flag1,
            t2_flag=flag2,
            commentary_text=commentary_text,
        )
        # Hard guard: the downloadable file must always be exactly 3840 x 2160.
        # The render pipeline itself uses this canvas natively; this also protects against stale/modified renderers.
        if rendered.size != EXPECTED_OUTPUT_SIZE:
            rendered = rendered.resize(EXPECTED_OUTPUT_SIZE, Image.Resampling.LANCZOS)
        if rendered.size != (3840, 2160):
            raise RuntimeError(f"Unexpected thumbnail size: {rendered.size}; expected 3840 x 2160")

        output_buffer = io.BytesIO()
        # Fast compression keeps generation quick; PNG remains lossless.
        rendered.save(output_buffer, format="PNG", optimize=False, compress_level=1)
        st.session_state["_thumbnail_result"] = rendered
        st.session_state["_thumbnail_png"] = output_buffer.getvalue()
        st.session_state["_thumbnail_signature"] = render_signature

result = st.session_state["_thumbnail_result"]
output_png = st.session_state["_thumbnail_png"]

with col_right:
    st.subheader("Live 4K Preview — Reference Image Style")
    # Send a lightweight preview to the browser; the download remains full 4K.
    preview_image = result.resize((1280, 720), Image.Resampling.LANCZOS)
    st.image(preview_image, use_container_width=True)
    st.caption(
        f"Preview: 1280 × 720 px for speed. Download: {result.width} × {result.height} px PNG (4K UHD)."
    )

    st.download_button(
        label="⬇️ Download 4K Thumbnail (3840 × 2160 PNG)",
        data=output_png,
        file_name=f"{normalize_team_name(team1).replace(' ', '_')}_vs_{normalize_team_name(team2).replace(' ', '_')}_4K.png",
        mime="image/png",
        use_container_width=True,
    )

st.divider()
st.caption("LOCAL-FIRST: cropping, cached local U2NETP/OpenCV background removal, cached cutouts, composition, and 3840 × 2160 PNG export run locally without Gemini API calls. Model weights are never downloaded during user interactions. Gemini is used only when you explicitly press a front-facing pose conversion button. Local segmentation may leave overlapping text/graphics and cannot reconstruct hidden pixels.")
