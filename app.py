import io
import hashlib
import json
import os
import re
from urllib.parse import urlsplit, urlunsplit, urljoin

import requests
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
        "name": "Babar Azam",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/Babar_Azam_2023.png/800px-Babar_Azam_2023.png",
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
    """Fit a player inside a fixed side-specific frame without stretching or overflow.

    The frame has an exact width/height, but the source image keeps its original
    aspect ratio. Any subtle shadow is composited inside that same frame, so it
    cannot spill beyond the left/right player area or create a large outer halo.
    """
    if player_img is None:
        return

    player = get_image_alpha_content(apply_sports_color_grade(player_img))
    if side == "left":
        target_w, target_h = LEFT_PLAYER_WIDTH, LEFT_PLAYER_HEIGHT
        x, y = LEFT_PLAYER_X, LEFT_PLAYER_Y
    elif side == "right":
        target_w, target_h = RIGHT_PLAYER_WIDTH, RIGHT_PLAYER_HEIGHT
        x, y = RIGHT_PLAYER_X, RIGHT_PLAYER_Y
    else:
        raise ValueError("side must be 'left' or 'right'")

    # Keep the image proportional and constrain it to the exact placement box.
    scale = min(target_w / max(1, player.width), target_h / max(1, player.height))
    fitted_w = max(1, min(target_w, int(round(player.width * scale))))
    fitted_h = max(1, min(target_h, int(round(player.height * scale))))
    player = player.resize((fitted_w, fitted_h), Image.Resampling.LANCZOS)

    # Fixed-size transparent frame; center horizontally and align to the bottom.
    frame_player = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    offset_x = (target_w - fitted_w) // 2
    offset_y = target_h - fitted_h
    frame_player.alpha_composite(player, (offset_x, offset_y))

    # A restrained dark shadow, generated and clipped inside the same fixed frame.
    alpha = frame_player.getchannel("A")
    shadow_alpha = alpha.filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.GaussianBlur(7))
    shadow_alpha = shadow_alpha.point(lambda value: int(value * 0.18))
    shadow = Image.new("RGBA", (target_w, target_h), (5, 10, 20, 0))
    shadow.putalpha(shadow_alpha)

    composite = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    composite.alpha_composite(shadow)
    composite.alpha_composite(frame_player)

    # Composite only the fixed frame. Nothing from the player or shadow extends outside it.
    canvas.alpha_composite(composite, (x, y))


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
    font = load_robust_font(118)
    parts = str(channel_text or "PREET SPORTS").strip().split(maxsplit=1)
    if len(parts) == 2:
        first, second = parts[0], parts[1]
    else:
        first, second = str(channel_text or "PREET SPORTS"), ""
    bbox1 = draw.textbbox((0, 0), first, font=font)
    bbox2 = draw.textbbox((0, 0), second, font=font) if second else (0, 0, 0, 0)
    w1, h1 = bbox1[2] - bbox1[0], bbox1[3] - bbox1[1]
    w2 = bbox2[2] - bbox2[0]
    total_w = w1 + (28 if second else 0) + w2
    total_h = max(h1, bbox2[3] - bbox2[1] if second else h1)
    center_x = CANVAS_WIDTH // 2
    x0 = center_x - total_w // 2 - 70
    x1 = center_x + total_w // 2 + 70
    y0, y1 = 55, 55 + total_h + 75
    draw_pill_badge(draw, (x0, y0, x1, y1), (255, 255, 255, 255), (10, 10, 10, 255), 10, 100)
    # Thin red outside accent
    draw.rounded_rectangle((x0 - 5, y0 - 5, x1 + 5, y1 + 5), radius=105, outline=(220, 20, 30, 255), width=5)
    text_x = center_x - total_w // 2
    text_y = y0 + (total_h + 75 - total_h) // 2 - bbox1[1]
    draw.text((text_x, text_y), first, font=font, fill=(7, 7, 7, 255))
    if second:
        draw.text((text_x + w1 + 28, text_y), second, font=font, fill=(224, 18, 27, 255))


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
                       t1_name, t2_name, t1_flag, t2_flag):
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

    # Bold inward-pointing team labels at the bottom.
    font_team = load_robust_font(245)
    banner_w, banner_h = 1280, 360
    banner_y = CANVAS_HEIGHT - banner_h - 95
    draw_arrow_banner(draw, 0, banner_y, banner_w, banner_h, normalize_team_name(t1_name), font_team, "left")
    draw_arrow_banner(draw, CANVAS_WIDTH - banner_w, banner_y, banner_w, banner_h, normalize_team_name(t2_name), font_team, "right")

    # Circular flags in the two top corners.
    flag_size = 360
    draw_round_flag(overlay, draw, t1_flag, 55, 55, flag_size)
    draw_round_flag(overlay, draw, t2_flag, CANVAS_WIDTH - flag_size - 55, 55, flag_size)

    return Image.alpha_composite(canvas, overlay)


# =========================================================
# STREAMLIT UI
# =========================================================
st.title("🏏 PREET SPORTS — 4K Cricket Thumbnail Studio")
st.caption("Reference-style output: left player 1640 × 1960 px at (0, 200); right player 1600 × 1920 px at (2240, 240); canvas 3840 × 2160 px.")

for key in ["p1_cutout", "p2_cutout", "t1_code", "t2_code", "auto_bg"]:
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
    st.caption("Use larger transparent PNG/WebP player cutouts or high-resolution player photos. If ESPN's URL is a small cropped headshot, the thumbnail cannot recreate the missing torso.")
    left_captain_url = st.text_input(
        "Left Captain Image URL",
        placeholder="Paste the left captain's direct image URL",
        key="left_captain_image_url",
    )
    right_captain_url = st.text_input(
        "Right Captain Image URL",
        placeholder="Paste the right captain's direct image URL",
        key="right_captain_image_url",
    )
    if st.button("🖼️ Fetch / Refresh Captain Images", use_container_width=True):
        attempts, loaded = 0, 0
        if left_captain_url.strip():
            attempts += 1
            image_left = fetch_online_image(left_captain_url.strip())
            if image_left is not None:
                st.session_state.p1_cutout = image_left
                loaded += 1
            else:
                st.error("Left image could not be downloaded. Check that the URL is public and points directly to an image.")
        if right_captain_url.strip():
            attempts += 1
            image_right = fetch_online_image(right_captain_url.strip())
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
        team1 = st.text_input("Left Team Name", value=st.session_state.t1_code or "IND", key="team1_name_input").strip().upper()
    with col_t2:
        team2 = st.text_input("Right Team Name", value=st.session_state.t2_code or "WI", key="team2_name_input").strip().upper()

    col_status, col_badge = st.columns(2)
    with col_status:
        match_status = st.text_input("Main Text", value="LIVE", key="match_status_input")
    with col_badge:
        match_badge = st.text_input("Match Badge", value="2nd ODI", key="match_badge_input")
    channel_title = st.text_input("Channel Brand", value="PREET SPORTS", key="channel_title_input")

    st.subheader("4. Background (optional override)")
    stadium_url = st.text_input(
        "Custom Stadium Background URL",
        value="",
        placeholder="Leave blank to use the built-in cricket stadium photo",
        key="stadium_background_url",
    )
    bg_file = st.file_uploader("Or upload your own 16:9 stadium background", type=["png", "jpg", "jpeg", "webp"])
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        custom_p1 = st.file_uploader("Manual left cutout (PNG/WebP)", type=["png", "webp"], key="manual_left_player")
    with col_up2:
        custom_p2 = st.file_uploader("Manual right cutout (PNG/WebP)", type=["png", "webp"], key="manual_right_player")

# Resolve player images: uploaded images override fetched URL images; URL images override team fallback.
c1_info = CAPTAIN_DATABASE.get(normalize_team_name(team1), {})
c2_info = CAPTAIN_DATABASE.get(normalize_team_name(team2), {})

if custom_p1:
    p1_final = Image.open(custom_p1).convert("RGBA")
elif st.session_state.p1_cutout is not None:
    p1_final = st.session_state.p1_cutout
elif c1_info.get("player_png"):
    p1_final = fetch_online_image(c1_info["player_png"])
else:
    p1_final = None

if custom_p2:
    p2_final = Image.open(custom_p2).convert("RGBA")
elif st.session_state.p2_cutout is not None:
    p2_final = st.session_state.p2_cutout
elif c2_info.get("player_png"):
    p2_final = fetch_online_image(c2_info["player_png"])
else:
    p2_final = None

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
    normalize_team_name(team1),
    normalize_team_name(team2),
    str(channel_title),
    str(match_status),
    str(match_badge),
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
        )
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
    st.caption("Preview shown at 1280 × 720 for faster loading. Download remains 3840 × 2160 PNG.")

    st.download_button(
        label="⬇️ Download 4K Thumbnail (3840 × 2160 PNG)",
        data=output_png,
        file_name=f"{normalize_team_name(team1).replace(' ', '_')}_vs_{normalize_team_name(team2).replace(' ', '_')}_4K.png",
        mime="image/png",
        use_container_width=True,
    )

st.divider()
st.caption("Tip: for the large upper-body look in your reference, use high-resolution transparent player cutouts. ESPNcricinfo squad pages sometimes expose cropped portrait thumbnails; this code tries untransformed and high-resolution CDN variants, but cannot invent body details that are absent from the source image.")
