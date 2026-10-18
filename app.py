import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
import io
import os
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# --- 1. Page Configuration ---
st.set_page_config(page_title="4K Sports Thumbnail Studio", layout="wide")

CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 2160

# --- 2. High-Quality Stadium Backgrounds (4K Presets) ---
STADIUM_PRESETS = {
    "Night Floodlights (Default)": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=3840&auto=format&fit=crop",
    "Cricket Arena Lights": "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=3840&auto=format&fit=crop",
    "Crowd & Floodlights": "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?q=80&w=3840&auto=format&fit=crop"
}

# --- 3. Robust Font Engine with Auto-Fitting ---
@st.cache_resource
def get_font_file():
    font_path = "/tmp/Montserrat-Black.ttf"
    if not os.path.exists(font_path):
        try:
            url = "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat-Black.ttf"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(r.content)
                return font_path
        except:
            pass
    return font_path if os.path.exists(font_path) else None

def load_font(size):
    font_path = get_font_file()
    if font_path and os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except:
            pass
    for path in ["arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue
    try:
        return ImageFont.load_default(size=size)
    except:
        return ImageFont.load_default()

def get_fitted_font(text, max_width, max_height, initial_size=220):
    """Dynamically shrinks text size so long names never clip or overflow."""
    size = initial_size
    while size > 60:
        font = load_font(size)
        bbox = font.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= max_width and h <= max_height:
            return font
        size -= 10
    return load_font(size)

# --- 4. Universal Image Fetcher (Handles Cricinfo CDN, Wikipedia & Web) ---
@st.cache_data(show_spinner=False)
def fetch_online_image(url):
    if not url or not str(url).strip():
        return None
    url = url.strip()
    
    # Upgrade low-res Cricinfo CDN thumbnails (w_320) to high-res (w_1200)
    if "hscicdn.com" in url:
        url = re.sub(r"w_\d+", "w_1200", url)
        url = re.sub(r"q_\d+", "q_100", url)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.espncricinfo.com/"
        }
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            img = Image.open(io.BytesIO(res.content))
            return img.convert("RGBA")
    except Exception as e:
        st.warning(f"Failed to fetch image: {e}")
    return None

# --- 5. Cricinfo Match/Squad URL Parser ---
@st.cache_data(show_spinner=False)
def parse_cricinfo_squad_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return None, f"HTTP Error {response.status_code} fetching Cricinfo page."

        soup = BeautifulSoup(response.text, "html.parser")
        next_data_tag = soup.find("script", id="__NEXT_DATA__")

        if next_data_tag:
            data = json.loads(next_data_tag.string)
            props = data.get("props", {}).get("appPageProps", {})
            squad_data = props.get("data", {}).get("squads", []) or props.get("data", {}).get("teams", [])

            teams_found = []
            for team in squad_data:
                team_name = team.get("team", {}).get("name") or team.get("name", "TEAM")
                team_abbrev = team.get("team", {}).get("abbreviation") or team_name[:3].upper()

                captain_name = None
                captain_img = None

                players = team.get("players", [])
                for p in players:
                    player_obj = p.get("player", p)
                    is_capt = p.get("isCaptain", False) or "(c)" in player_obj.get("name", "").lower()
                    if is_capt and not captain_name:
                        captain_name = player_obj.get("name", "").replace("(c)", "").strip()
                        img_obj = player_obj.get("image", {})
                        captain_img = img_obj.get("url") if isinstance(img_obj, dict) else img_obj
                        break

                if not captain_name and players:
                    first_p = players[0].get("player", players[0])
                    captain_name = first_p.get("name", "Player")
                    img_obj = first_p.get("image", {})
                    captain_img = img_obj.get("url") if isinstance(img_obj, dict) else img_obj

                teams_found.append({
                    "name": team_name,
                    "code": team_abbrev,
                    "captain": captain_name,
                    "img_url": captain_img
                })

            if len(teams_found) >= 2:
                return teams_found[:2], None

        return None, "Captains not found in structured data. Please paste direct image URLs below."
    except Exception as e:
        return None, f"Error parsing: {str(e)}"

# --- 6. Graphics & Compositing Engine ---
def apply_sports_color_grade(image):
    if not image:
        return None
    image = ImageEnhance.Color(image).enhance(1.22)
    image = ImageEnhance.Contrast(image).enhance(1.18)
    image = ImageEnhance.Sharpness(image).enhance(1.30)
    return image

def render_player_with_rim_light(canvas, player_img, pos_x, pos_y, target_w, target_h):
    resized = player_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if "A" not in resized.getbands():
        resized.putalpha(Image.new("L", (target_w, target_h), 255))

    alpha = resized.split()[3]
    glow_mask = alpha.filter(ImageFilter.MaxFilter(21)).filter(ImageFilter.GaussianBlur(15))
    glow_surface = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 0))
    glow_surface.putalpha(glow_mask)

    canvas.paste(glow_surface, (pos_x, pos_y), glow_surface)
    canvas.paste(resized, (pos_x, pos_y), resized)

def draw_pill_badge(draw, bbox, fill_color, border_color=None, border_width=0, radius=50):
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill_color)
    if border_color and border_width > 0:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, outline=border_color, width=border_width)

def draw_arrow_banner(draw, x, y, width, height, text, direction="left"):
    if direction == "left":
        points = [
            (x, y),
            (x + width - height // 2, y),
            (x + width, y + height // 2),
            (x + width - height // 2, y + height),
            (x, y + height)
        ]
    else:
        points = [
            (x + height // 2, y),
            (x + width, y),
            (x + width, y + height),
            (x + height // 2, y + height),
            (x, y + height // 2)
        ]

    draw.polygon(points, fill=(10, 10, 10, 255))
    draw.line(points + [points[0]], fill=(255, 255, 255, 255), width=10)

    # Auto-fit text inside banner
    usable_width = width - (height // 2) - 80
    usable_height = height - 60
    font = get_fitted_font(text, usable_width, usable_height, initial_size=200)

    text_bbox = font.getbbox(text)
    tw = text_bbox[2] - text_bbox[0]
    th = text_bbox[3] - text_bbox[1]

    if direction == "left":
        tx = x + (usable_width - tw) // 2 + 20
    else:
        tx = x + (height // 2) + (usable_width - tw) // 2 + 20

    ty = y + (height - th) // 2 - text_bbox[1]
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

def generate_thumbnail(bg_img, p1_img, p2_img, channel_text, match_status, match_badge, t1_name, t2_name, t1_flag, t2_flag):
    if bg_img:
        canvas = bg_img.convert("RGBA").resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
    else:
        # Fallback dark stadium tone
        canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (15, 30, 55, 255))

    # Render Players
    if p1_img:
        p1 = apply_sports_color_grade(p1_img.convert("RGBA"))
        aspect = p1.width / p1.height
        target_h = int(CANVAS_HEIGHT * 0.95)
        target_w = int(target_h * aspect)
        render_player_with_rim_light(canvas, p1, int(CANVAS_WIDTH * 0.03), CANVAS_HEIGHT - target_h, target_w, target_h)

    if p2_img:
        p2 = apply_sports_color_grade(p2_img.convert("RGBA"))
        aspect = p2.width / p2.height
        target_h = int(CANVAS_HEIGHT * 0.95)
        target_w = int(target_h * aspect)
        render_player_with_rim_light(canvas, p2, CANVAS_WIDTH - target_w - int(CANVAS_WIDTH * 0.03), CANVAS_HEIGHT - target_h, target_w, target_h)

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_live = load_font(460)
    font_sub = load_font(160)
    font_brand = load_font(110)

    # Top Brand Pill
    brand_bbox = font_brand.getbbox(channel_text)
    bw, bh = brand_bbox[2] - brand_bbox[0], brand_bbox[3] - brand_bbox[1]
    px, py = CANVAS_WIDTH // 2, 160
    draw_pill_badge(draw, (px - bw//2 - 80, py - 30, px + bw//2 + 80, py + bh + 30),
                    fill_color=(255, 255, 255, 255), border_color=(220, 30, 30, 255), border_width=12, radius=60)
    draw.text((px - bw//2, py - brand_bbox[1]), channel_text, font=font_brand, fill=(220, 20, 20, 255))

    # Center "LIVE" Text
    live_bbox = font_live.getbbox(match_status)
    lw, lh = live_bbox[2] - live_bbox[0], live_bbox[3] - live_bbox[1]
    lx, ly = (CANVAS_WIDTH - lw) // 2, (CANVAS_HEIGHT // 2) - 450

    border_px = 24
    for dx in range(-border_px, border_px + 1, 6):
        for dy in range(-border_px, border_px + 1, 6):
            draw.text((lx + dx, ly + dy - live_bbox[1]), match_status, font=font_live, fill=(255, 255, 255, 255))
    draw.text((lx, ly - live_bbox[1]), match_status, font=font_live, fill=(225, 25, 25, 255))

    # Sub-Heading (e.g., T20)
    sub_bbox = font_sub.getbbox(match_badge)
    sw, sh = sub_bbox[2] - sub_bbox[0], sub_bbox[3] - sub_bbox[1]
    sx, sy = CANVAS_WIDTH // 2, ly + lh + 130
    draw_pill_badge(draw, (sx - sw//2 - 120, sy - 35, sx + sw//2 + 120, sy + sh + 35),
                    fill_color=(15, 75, 175, 255), border_color=(255, 255, 255, 255), border_width=10, radius=50)
    draw.text((sx - sw//2, sy - sub_bbox[1]), match_badge, font=font_sub, fill=(255, 230, 0, 255))

    # Bottom Team Banners (With Auto-Fitting)
    banner_w, banner_h = 1250, 320
    draw_arrow_banner(draw, 80, CANVAS_HEIGHT - banner_h - 100, banner_w, banner_h, t1_name, "left")
    draw_arrow_banner(draw, CANVAS_WIDTH - banner_w - 80, CANVAS_HEIGHT - banner_h - 100, banner_w, banner_h, t2_name, "right")

    # Round Flags
    flag_size = 380
    if t1_flag:
        f1 = t1_flag.convert("RGBA").resize((flag_size, flag_size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (flag_size, flag_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, flag_size, flag_size), fill=255)
        overlay.paste(f1, (80, 80), mask)
        draw.ellipse((75, 75, 85 + flag_size, 85 + flag_size), outline=(255, 255, 255, 255), width=16)

    if t2_flag:
        f2 = t2_flag.convert("RGBA").resize((flag_size, flag_size), Image.Resampling.LANCZOS)
        mask2 = Image.new("L", (flag_size, flag_size), 0)
        ImageDraw.Draw(mask2).ellipse((0, 0, flag_size, flag_size), fill=255)
        overlay.paste(f2, (CANVAS_WIDTH - flag_size - 80, 80), mask2)
        draw.ellipse((CANVAS_WIDTH - flag_size - 85, 75, CANVAS_WIDTH - 75, 85 + flag_size), outline=(255, 255, 255, 255), width=16)

    return Image.alpha_composite(canvas, overlay)


# --- 7. Streamlit User Interface ---
st.title("🏏 4K Sports Thumbnail Studio")

# Session State for URL assets
for key in ["p1_url_img", "p2_url_img", "team1_val", "team2_val"]:
    if key not in st.session_state:
        st.session_state[key] = "" if "val" in key else None

col_left, col_right = st.columns([1, 1.3])

with col_left:
    st.subheader("1. Match & Squad URL Importer")
    cricinfo_page_url = st.text_input("Paste ESPNcricinfo Match/Squad Page URL (Optional):", "")
    if st.button("⚡ Auto-Extract Squad & Captains", type="secondary"):
        if cricinfo_page_url:
            with st.spinner("Extracting squads and headshots..."):
                teams, err = parse_cricinfo_squad_url(cricinfo_page_url)
                if teams:
                    st.session_state.team1_val = teams[0]["code"]
                    st.session_state.team2_val = teams[1]["code"]
                    if teams[0].get("img_url"):
                        st.session_state.p1_url_img = fetch_online_image(teams[0]["img_url"])
                    if teams[1].get("img_url"):
                        st.session_state.p2_url_img = fetch_online_image(teams[1]["img_url"])
                    st.success(f"Loaded: {teams[0]['name']} vs {teams[1]['name']}")
                else:
                    st.error(err)

    st.subheader("2. Direct Player Image URLs")
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        p1_img_url = st.text_input("Left Player Image URL (hscicdn / web):", key="url1")
    with col_u2:
        p2_img_url = st.text_input("Right Player Image URL (hscicdn / web):", key="url2")

    st.subheader("3. Match Details")
    c_t1, c_t2 = st.columns(2)
    with c_t1:
        team1 = st.text_input("Team 1 Name / Code", value=st.session_state.team1_val or "AUS WOMEN").strip()
    with c_t2:
        team2 = st.text_input("Team 2 Name / Code", value=st.session_state.team2_val or "NZ WOMEN").strip()

    c_s1, c_s2 = st.columns(2)
    with c_s1:
        match_status = st.text_input("Status", value="LIVE")
    with c_s2:
        match_badge = st.text_input("Badge Info", value="1st T20I")

    channel_title = st.text_input("Channel Title", value="PREET SPORTS")

    st.subheader("4. Background Selection")
    bg_choice = st.selectbox("Select 4K Stadium Style", list(STADIUM_PRESETS.keys()))
    custom_bg = st.file_uploader("Or Upload Custom 4K Stadium", type=["png", "jpg", "jpeg"])

# Resolve Player 1 Image
p1_final = None
if p1_img_url:
    p1_final = fetch_online_image(p1_img_url)
elif st.session_state.p1_url_img:
    p1_final = st.session_state.p1_url_img

# Resolve Player 2 Image
p2_final = None
if p2_img_url:
    p2_final = fetch_online_image(p2_img_url)
elif st.session_state.p2_url_img:
    p2_final = st.session_state.p2_url_img

# Resolve Background
if custom_bg:
    bg_final = Image.open(custom_bg)
else:
    bg_final = fetch_online_image(STADIUM_PRESETS[bg_choice])

with col_right:
    st.subheader("Live 4K Preview")
    result = generate_thumbnail(
        bg_img=bg_final,
        p1_img=p1_final,
        p2_img=p2_final,
        channel_text=channel_title,
        match_status=match_status,
        match_badge=match_badge,
        t1_name=team1,
        t2_name=team2,
        t1_flag=None,
        t2_flag=None
    )

    st.image(result, use_container_width=True)

    buf = io.BytesIO()
    result.save(buf, format="PNG", quality=95)
    st.download_button(
        label="⬇️ Download 4K Thumbnail (3840 x 2160)",
        data=buf.getvalue(),
        file_name=f"{team1}_vs_{team2}_4K.png",
        mime="image/png",
        use_container_width=True
    )
