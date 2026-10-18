import io
import base64
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
RENDER_PIPELINE_VERSION = "preet-sports-4k-v11-generic-background-removal"
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


def remove_background_from_any_image(upload_bytes, filename="image"):
    """Use Gemini image editing to isolate the main foreground subject on transparency.

    Works with ordinary uploaded photos, products, people, pets, objects and logos.
    Gemini is asked for a uniform magenta backing, which is converted to alpha locally.
    Returns (PIL.Image in RGBA mode or None, error message or None).
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return None, (
            "Background removal is not configured. Add GEMINI_API_KEY in Render → Environment. "
            "Gemini API calls may be billed separately from your Gemini Pro subscription."
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
            has_alpha = source.getchannel("A").getextrema()[0] < 250
            source_buffer = io.BytesIO()
            if has_alpha:
                source.save(source_buffer, format="PNG", optimize=False, compress_level=3)
                mime_type = "image/png"
            else:
                source.convert("RGB").save(source_buffer, format="JPEG", quality=92, optimize=True)
                mime_type = "image/jpeg"
            source_bytes = source_buffer.getvalue()
    except Exception as exc:
        return None, f"Could not read the uploaded image: {exc}"

    prompt = (
        "Perform a precise background-removal edit on the supplied image. Identify and preserve the main "
        "foreground subject or object exactly as shown, including fine edges such as hair, fur, feathers, "
        "transparent product edges, and small details. Remove the entire original background, including "
        "scenery, room, sky, floor, shadows that belong to the background, and unrelated objects. Do not "
        "redraw, beautify, recolor, reshape, crop, or replace the main subject. Preserve its identity, pose, "
        "proportions, clothing, logos, text, and colors. If there are multiple clearly intended foreground "
        "subjects, keep all of them. Keep the subject fully inside the image with a small margin. Do not add "
        "new objects, text, borders, or watermarks. For reliable background extraction, place the preserved "
        "subject on a perfectly flat, uniform pure magenta background RGB(255, 0, 255), edge to edge; no "
        "gradient, texture, scenery, cast shadow, or magenta rim light. Magenta must only appear in empty "
        "background pixels, never on the subject. Return one edited image."
    )
    request_body = {
        "model": os.environ.get("GEMINI_IMAGE_MODEL", "gemini-nano-banana-2.1").strip(),
        "input": [
            {"type": "text", "text": prompt},
            {"type": "image", "data": base64.b64encode(source_bytes).decode("ascii"), "mime_type": mime_type},
        ],
        "response_format": {"type": "image", "mime_type": "image/png", "image_size": "2K"},
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
                return None, f"Gemini API key or permissions rejected (HTTP {response.status_code}). {detail}".strip()
            if response.status_code == 429:
                return None, f"Gemini API quota/rate limit reached (HTTP 429). Check AI Studio billing/usage. {detail}".strip()
            return None, f"Gemini background removal failed (HTTP {response.status_code}). {detail}".strip()

        payload = response.json()
        image_block = _find_gemini_image_block(payload)
        if not image_block or not image_block.get("data"):
            return None, "Gemini returned no image. Try a clearer image or another file format."
        result_bytes = base64.b64decode(image_block["data"])
        with Image.open(io.BytesIO(result_bytes)) as output_image:
            output_image.load()
            result = output_image.convert("RGBA")
        result = _remove_magenta_chroma_background(result)
        # Trim only transparent outside margins; leave a small safety margin around the subject.
        alpha = result.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            subject = result.crop(bbox)
            pad = max(8, int(max(subject.size) * 0.015))
            trimmed = Image.new("RGBA", (subject.width + 2 * pad, subject.height + 2 * pad), (0, 0, 0, 0))
            trimmed.alpha_composite(subject, (pad, pad))
            result = trimmed
        return result, None
    except requests.Timeout:
        return None, "Gemini background removal timed out. Try a smaller image or retry."
    except requests.RequestException as exc:
        return None, f"Could not reach the Gemini image-edit API: {exc}"
    except Exception as exc:
        return None, f"Background removal failed: {exc}"


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
            "mime_type": "image/png",
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
    image = ImageEnhance.Sharpness(image).enhance(1.15)
    return image


# Exact player placement boxes measured from the 16:9 reference thumbnail.
# Canvas: 3840 x 2160 px. The independent left/right sizes intentionally match the reference.
LEFT_PLAYER_WIDTH = 1640
LEFT_PLAYER_HEIGHT = 1960
LEFT_PLAYER_X = 0
LEFT_PLAYER_Y = CANVAS_HEIGHT - LEFT_PLAYER_HEIGHT  # 200 px from top

RIGHT_PLAYER_WIDTH = 1600
RIGHT_PLAYER_HEIGHT = 1920
RIGHT_PLAYER_X = CANVAS_WIDTH - RIGHT_PLAYER_WIDTH  # 2240 px from left
RIGHT_PLAYER_Y = CANVAS_HEIGHT - RIGHT_PLAYER_HEIGHT  # 240 px from top


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
    font = load_robust_font(72)  # Compact brand pill: keep it away from players and face area.
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
    pad_x, pad_y = 36, 17
    x0 = center_x - total_w // 2 - pad_x
    x1 = center_x + total_w // 2 + pad_x
    y0, y1 = 38, 38 + total_h + 2 * pad_y
    radius = (y1 - y0) // 2
    draw_pill_badge(draw, (x0, y0, x1, y1), (255, 255, 255, 255), (10, 10, 10, 255), 7, radius)
    draw.rounded_rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), radius=radius + 4, outline=(220, 20, 30, 255), width=4)
    text_x = center_x - total_w // 2
    text_y = y0 + (y1 - y0 - total_h) // 2 - bbox1[1]
    draw.text((text_x, text_y), first, font=font, fill=(7, 7, 7, 255))
    if second:
        draw.text((text_x + w1 + gap, text_y), second, font=font, fill=(224, 18, 27, 255))


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

    # Captain cutouts are layered above the stadium and below the text.
    render_player_cutout(canvas, p1_img, "left")
    render_player_cutout(canvas, p2_img, "right")

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw_brand_pill(draw, channel_text)

    # Large red LIVE with a clean white stroke, similar to the first reference image.
    font_live = load_robust_font(555)
    live_y = 420
    draw_centered_text(
        draw, CANVAS_WIDTH, str(match_status or "LIVE"), live_y, font_live,
        (232, 15, 23, 255), stroke_width=25, stroke_fill=(255, 255, 255, 255)
    )

    # Blue rounded match badge directly under LIVE.
    font_sub = load_robust_font(225)
    badge_text = str(match_badge or "MATCH DAY")
    sub_bbox = draw.textbbox((0, 0), badge_text, font=font_sub, stroke_width=0)
    sw, sh = sub_bbox[2] - sub_bbox[0], sub_bbox[3] - sub_bbox[1]
    badge_w = sw + 260
    badge_h = sh + 65
    bx0 = (CANVAS_WIDTH - badge_w) // 2
    by0 = 1130
    draw_pill_badge(
        draw, (bx0, by0, bx0 + badge_w, by0 + badge_h),
        (0, 72, 205, 255), (255, 255, 255, 255), 9, badge_h // 2
    )
    tx = (CANVAS_WIDTH - sw) // 2
    ty = by0 + (badge_h - sh) // 2 - sub_bbox[1]
    draw.text((tx, ty), badge_text, font=font_sub, fill=(255, 230, 0, 255))

    # Secondary Hindi Commentary box directly below the T20 / match-format badge.
    # Palette: deep navy fill, saffron outer border, white inner border, yellow/white text.
    commentary_label = str(commentary_text or "HINDI COMMENTARY").strip().upper()
    if commentary_label:
        font_commentary = load_robust_font(108)
        # Reduce the label font only if a user enters unusually long text.
        while font_commentary.size > 64 and draw.textbbox((0, 0), commentary_label, font=font_commentary)[2] > 1750:
            font_commentary = load_robust_font(font_commentary.size - 6)
        cbbox = draw.textbbox((0, 0), commentary_label, font=font_commentary)
        ctext_w = cbbox[2] - cbbox[0]
        ctext_h = cbbox[3] - cbbox[1]
        commentary_w = ctext_w + 150
        commentary_h = max(122, ctext_h + 48)
        commentary_x = (CANVAS_WIDTH - commentary_w) // 2
        commentary_y = by0 + badge_h + 28
        # Keep it safely above the team banners even if fonts vary by host.
        banner_top = CANVAS_HEIGHT - 360 - 95
        commentary_y = min(commentary_y, banner_top - commentary_h - 20)
        draw.rounded_rectangle(
            (commentary_x, commentary_y, commentary_x + commentary_w, commentary_y + commentary_h),
            radius=commentary_h // 2,
            fill=(8, 24, 55, 245),
            outline=(255, 145, 0, 255),
            width=12,
        )
        inner_pad = 9
        draw.rounded_rectangle(
            (commentary_x + inner_pad, commentary_y + inner_pad,
             commentary_x + commentary_w - inner_pad, commentary_y + commentary_h - inner_pad),
            radius=max(20, commentary_h // 2 - inner_pad),
            outline=(255, 255, 255, 230),
            width=4,
        )
        # Split the default label so HINDI is highlighted yellow and COMMENTARY is white.
        if commentary_label == "HINDI COMMENTARY":
            first_word, second_word = "HINDI", "COMMENTARY"
            first_bbox = draw.textbbox((0, 0), first_word, font=font_commentary)
            second_bbox = draw.textbbox((0, 0), second_word, font=font_commentary)
            first_w = first_bbox[2] - first_bbox[0]
            second_w = second_bbox[2] - second_bbox[0]
            spacing = 24
            start_x = (CANVAS_WIDTH - first_w - spacing - second_w) // 2
            text_y = commentary_y + (commentary_h - ctext_h) // 2 - cbbox[1]
            draw.text((start_x, text_y), first_word, font=font_commentary, fill=(255, 220, 0, 255))
            draw.text((start_x + first_w + spacing, text_y), second_word, font=font_commentary, fill=(255, 255, 255, 255))
        else:
            text_x = (CANVAS_WIDTH - ctext_w) // 2
            text_y = commentary_y + (commentary_h - ctext_h) // 2 - cbbox[1]
            draw.text((text_x, text_y), commentary_label, font=font_commentary, fill=(255, 255, 255, 255))

    # Bold inward-pointing team labels at the bottom.
    font_team = load_robust_font(245)
    banner_w, banner_h = 1280, 360
    banner_y = CANVAS_HEIGHT - banner_h - 95
    draw_arrow_banner(draw, 0, banner_y, banner_w, banner_h, normalize_team_name(t1_name), font_team, "left")
    draw_arrow_banner(draw, CANVAS_WIDTH - banner_w, banner_y, banner_w, banner_h, normalize_team_name(t2_name), font_team, "right")

    # Circular flags in the two top corners.
    flag_size = 190  # Compact flags placed high enough to avoid covering player hair/foreheads.
    draw_round_flag(overlay, draw, t1_flag, 28, 22, flag_size)
    draw_round_flag(overlay, draw, t2_flag, CANVAS_WIDTH - flag_size - 28, 22, flag_size)

    return Image.alpha_composite(canvas, overlay)


# =========================================================
# STREAMLIT UI
# =========================================================
st.title("🏏 PREET SPORTS — 4K Cricket Thumbnail Studio")
st.caption("Broadcast-style layout inspired by cricket live thumbnails: compact brand, large player portraits, bold LIVE / format badges, and clean bottom team banners. Export: 3840 × 2160 PNG.")

for key in ["p1_cutout", "p2_cutout", "p1_ai_front", "p2_ai_front", "p1_ai_source_hash", "p2_ai_source_hash", "t1_code", "t2_code", "auto_bg"]:
    if key not in st.session_state:
        st.session_state[key] = None

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
        "Upload a photo, person, product, pet, object, or logo. Gemini attempts to isolate the foreground "
        "and return a transparent PNG. Requires GEMINI_API_KEY in Render Environment; API usage may be billed separately."
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
            with st.spinner("Gemini is removing the background. This may take a little while…"):
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

    st.subheader("5. Background (optional override)")
    stadium_url = st.text_input(
        "Custom Stadium Background URL",
        value="",
        placeholder="Leave blank to use the built-in cricket stadium photo",
        key="stadium_background_url",
    )
    bg_file = st.file_uploader("Or upload your own 16:9 stadium background", type=["png", "jpg", "jpeg", "webp"])
    st.subheader("6. Upload Player Photos — AI Front-Facing Pose")
    st.caption(
        "Upload a side-facing photo and press Convert. Gemini Nano Banana will attempt to turn the head and shoulders toward camera. "
        "The app requests a magenta background and removes it to create a player cutout. Add GEMINI_API_KEY in Render Environment; "
        "API use may be billed separately from Gemini Pro, and identity/uniform details should be checked."
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
st.caption("AI front-facing conversion uses Gemini Nano Banana only when you press a Convert button. Set GEMINI_API_KEY in Render → Environment first. Gemini API use may be billed separately from your Gemini Pro subscription. Inspect generated portraits for identity/uniform accuracy. The downloaded PNG is rendered at 3840 × 2160.")
