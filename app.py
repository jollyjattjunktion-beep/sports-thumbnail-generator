import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
import io
import os

# --- Page Config ---
st.set_page_config(page_title="4K Sports Thumbnail Studio", layout="wide")

CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 2160

# --- High-Resolution Transparent PNG Captain & Flag Database ---
# Direct transparent cutouts ensure zero-RAM-crash performance on Render
CAPTAIN_DATABASE = {
    "IND": {
        "name": "Rohit Sharma",
        "flag": "https://flagcdn.com/w320/in.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Rohit_Sharma_during_the_India_vs_Australia_match_in_2023.png/800px-Rohit_Sharma_during_the_India_vs_Australia_match_in_2023.png"
    },
    "INDIA": {
        "name": "Rohit Sharma",
        "flag": "https://flagcdn.com/w320/in.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Rohit_Sharma_during_the_India_vs_Australia_match_in_2023.png/800px-Rohit_Sharma_during_the_India_vs_Australia_match_in_2023.png"
    },
    "WI": {
        "name": "Shai Hope",
        "flag": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Shai_Hope_2019.png/800px-Shai_Hope_2019.png"
    },
    "WEST INDIES": {
        "name": "Shai Hope",
        "flag": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Shai_Hope_2019.png/800px-Shai_Hope_2019.png"
    },
    "AUS": {
        "name": "Pat Cummins",
        "flag": "https://flagcdn.com/w320/au.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Pat_Cummins_in_2023.png/800px-Pat_Cummins_in_2023.png"
    },
    "AUSTRALIA": {
        "name": "Pat Cummins",
        "flag": "https://flagcdn.com/w320/au.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Pat_Cummins_in_2023.png/800px-Pat_Cummins_in_2023.png"
    },
    "ENG": {
        "name": "Jos Buttler",
        "flag": "https://flagcdn.com/w320/gb-eng.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Jos_Buttler_2022.png/800px-Jos_Buttler_2022.png"
    },
    "PAK": {
        "name": "Babar Azam",
        "flag": "https://flagcdn.com/w320/pk.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/Babar_Azam_2023.png/800px-Babar_Azam_2023.png"
    },
    "SA": {
        "name": "Temba Bavuma",
        "flag": "https://flagcdn.com/w320/za.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Temba_Bavuma_2023.png/800px-Temba_Bavuma_2023.png"
    },
    "NZ": {
        "name": "Kane Williamson",
        "flag": "https://flagcdn.com/w320/nz.png",
        "player_png": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Kane_Williamson_in_2019.png/800px-Kane_Williamson_in_2019.png"
    }
}

# --- Reliable Font Loader (Works on Windows, Mac & Render Linux) ---
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

def load_robust_font(size):
    font_path = get_font_file()
    if font_path and os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except:
            pass
    # Local OS fallbacks
    for path in ["arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue
    try:
        return ImageFont.load_default(size=size)
    except:
        return ImageFont.load_default()

# --- Network Image Fetchers ---
@st.cache_data(show_spinner=False)
def fetch_online_image(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return Image.open(io.BytesIO(res.content)).convert("RGBA")
    except:
        pass
    return None

# --- Procedural 4K Stadium Generator (Default BG) ---
@st.cache_resource
def generate_procedural_stadium():
    img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (12, 28, 48, 255))
    draw = ImageDraw.Draw(img)

    # Sky gradient / Floodlight glow
    for y in range(int(CANVAS_HEIGHT * 0.65)):
        ratio = y / (CANVAS_HEIGHT * 0.65)
        r = int(10 + ratio * 20)
        g = int(35 + ratio * 50)
        b = int(75 + ratio * 85)
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(r, g, b, 255))

    # Green Outfield Perspective
    grass_top = int(CANVAS_HEIGHT * 0.58)
    for y in range(grass_top, CANVAS_HEIGHT):
        ratio = (y - grass_top) / (CANVAS_HEIGHT - grass_top)
        r = int(25 + ratio * 15)
        g = int(120 + ratio * 45)
        b = int(30 + ratio * 15)
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(r, g, b, 255))

    # Center Pitch Oval
    draw.ellipse([CANVAS_WIDTH//2 - 500, CANVAS_HEIGHT - 750, CANVAS_WIDTH//2 + 500, CANVAS_HEIGHT - 350], fill=(195, 175, 125, 255))
    return img.filter(ImageFilter.GaussianBlur(1))

# --- Image Processing & Lighting ---
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
    # Edge floodlight glow
    glow_mask = alpha.filter(ImageFilter.MaxFilter(19)).filter(ImageFilter.GaussianBlur(12))
    glow_surface = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 0))
    glow_surface.putalpha(glow_mask)

    canvas.paste(glow_surface, (pos_x, pos_y), glow_surface)
    canvas.paste(resized, (pos_x, pos_y), resized)

def draw_pill_badge(draw, bbox, fill_color, border_color=None, border_width=0, radius=50):
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill_color)
    if border_color and border_width > 0:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, outline=border_color, width=border_width)

def draw_arrow_banner(draw, x, y, width, height, text, font, direction="left"):
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

    text_bbox = font.getbbox(text)
    tw = text_bbox[2] - text_bbox[0]
    th = text_bbox[3] - text_bbox[1]
    tx = x + (width - tw) // 2
    ty = y + (height - th) // 2 - text_bbox[1]
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

# --- Main Thumbnail Rendering Function ---
def generate_thumbnail(bg_img, p1_img, p2_img, channel_text, match_status, match_badge, t1_name, t2_name, t1_flag, t2_flag):
    # 1. Base Canvas
    if bg_img:
        canvas = bg_img.convert("RGBA").resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
    else:
        canvas = generate_procedural_stadium().copy()

    # 2. Left Player
    if p1_img:
        p1 = apply_sports_color_grade(p1_img.convert("RGBA"))
        aspect = p1.width / p1.height
        target_h = int(CANVAS_HEIGHT * 0.95)
        target_w = int(target_h * aspect)
        render_player_with_rim_light(canvas, p1, int(CANVAS_WIDTH * 0.04), CANVAS_HEIGHT - target_h, target_w, target_h)

    # 3. Right Player
    if p2_img:
        p2 = apply_sports_color_grade(p2_img.convert("RGBA"))
        aspect = p2.width / p2.height
        target_h = int(CANVAS_HEIGHT * 0.95)
        target_w = int(target_h * aspect)
        render_player_with_rim_light(canvas, p2, CANVAS_WIDTH - target_w - int(CANVAS_WIDTH * 0.04), CANVAS_HEIGHT - target_h, target_w, target_h)

    # 4. Text & Badges Overlay
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_live = load_robust_font(460)
    font_sub = load_robust_font(160)
    font_team = load_robust_font(220)
    font_brand = load_robust_font(110)

    # Top Brand Pill
    brand_bbox = font_brand.getbbox(channel_text)
    bw, bh = brand_bbox[2] - brand_bbox[0], brand_bbox[3] - brand_bbox[1]
    px, py = CANVAS_WIDTH // 2, 160
    draw_pill_badge(draw, (px - bw//2 - 80, py - 30, px + bw//2 + 80, py + bh + 30),
                    fill_color=(255, 255, 255, 255), border_color=(220, 30, 30, 255), border_width=12, radius=60)
    draw.text((px - bw//2, py - brand_bbox[1]), channel_text, font=font_brand, fill=(220, 20, 20, 255))

    # Center "LIVE" Text with 3D White Outline
    live_bbox = font_live.getbbox(match_status)
    lw, lh = live_bbox[2] - live_bbox[0], live_bbox[3] - live_bbox[1]
    lx, ly = (CANVAS_WIDTH - lw) // 2, (CANVAS_HEIGHT // 2) - 450

    border_px = 24
    for dx in range(-border_px, border_px + 1, 6):
        for dy in range(-border_px, border_px + 1, 6):
            draw.text((lx + dx, ly + dy - live_bbox[1]), match_status, font=font_live, fill=(255, 255, 255, 255))
    draw.text((lx, ly - live_bbox[1]), match_status, font=font_live, fill=(225, 25, 25, 255))

    # Sub-Heading (e.g. 2nd ODI)
    sub_bbox = font_sub.getbbox(match_badge)
    sw, sh = sub_bbox[2] - sub_bbox[0], sub_bbox[3] - sub_bbox[1]
    sx, sy = CANVAS_WIDTH // 2, ly + lh + 130
    draw_pill_badge(draw, (sx - sw//2 - 120, sy - 35, sx + sw//2 + 120, sy + sh + 35),
                    fill_color=(15, 75, 175, 255), border_color=(255, 255, 255, 255), border_width=10, radius=50)
    draw.text((sx - sw//2, sy - sub_bbox[1]), match_badge, font=font_sub, fill=(255, 230, 0, 255))

    # Team Arrow Banners
    banner_w, banner_h = 1100, 300
    draw_arrow_banner(draw, 100, CANVAS_HEIGHT - banner_h - 100, banner_w, banner_h, t1_name, font_team, "left")
    draw_arrow_banner(draw, CANVAS_WIDTH - banner_w - 100, CANVAS_HEIGHT - banner_h - 100, banner_w, banner_h, t2_name, font_team, "right")

    # Round Flags
    flag_size = 380
    if t1_flag:
        f1 = t1_flag.convert("RGBA").resize((flag_size, flag_size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (flag_size, flag_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, flag_size, flag_size), fill=255)
        overlay.paste(f1, (100, 100), mask)
        draw.ellipse((95, 95, 105 + flag_size, 105 + flag_size), outline=(255, 255, 255, 255), width=16)

    if t2_flag:
        f2 = t2_flag.convert("RGBA").resize((flag_size, flag_size), Image.Resampling.LANCZOS)
        mask2 = Image.new("L", (flag_size, flag_size), 0)
        ImageDraw.Draw(mask2).ellipse((0, 0, flag_size, flag_size), fill=255)
        overlay.paste(f2, (CANVAS_WIDTH - flag_size - 100, 100), mask2)
        draw.ellipse((CANVAS_WIDTH - flag_size - 105, 95, CANVAS_WIDTH - 95, 105 + flag_size), outline=(255, 255, 255, 255), width=16)

    return Image.alpha_composite(canvas, overlay)


# --- Streamlit UI ---
st.title("🏏 4K Sports Thumbnail Studio")

col_left, col_right = st.columns([1, 1.3])

with col_left:
    st.subheader("1. Match Setup")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        team1 = st.text_input("Team 1 Code", value="IND").strip().upper()
    with col_t2:
        team2 = st.text_input("Team 2 Code", value="WI").strip().upper()

    col_txt1, col_txt2 = st.columns(2)
    with col_txt1:
        match_status = st.text_input("Main Status", value="LIVE")
    with col_txt2:
        match_badge = st.text_input("Badge Info", value="2nd ODI")

    channel_title = st.text_input("Channel Title", value="PREET SPORTS")

    st.subheader("2. Auto-Captain Fetch")
    c1_info = CAPTAIN_DATABASE.get(team1, {})
    c2_info = CAPTAIN_DATABASE.get(team2, {})

    p1_name = st.text_input("Player 1", value=c1_info.get("name", "Player 1"))
    p2_name = st.text_input("Player 2", value=c2_info.get("name", "Player 2"))

    st.subheader("3. Custom Uploads (Optional)")
    bg_file = st.file_uploader("Upload Custom 4K Stadium", type=["png", "jpg", "jpeg"])
    custom_p1 = st.file_uploader("Manual Left Cutout (PNG)", type=["png"])
    custom_p2 = st.file_uploader("Manual Right Cutout (PNG)", type=["png"])

# Resolve Final Cutouts & Flags
with st.spinner("Preparing 4K Graphics..."):
    # Left Player
    if custom_p1:
        p1_final = Image.open(custom_p1)
    elif c1_info.get("player_png"):
        p1_final = fetch_online_image(c1_info["player_png"])
    else:
        p1_final = None

    # Right Player
    if custom_p2:
        p2_final = Image.open(custom_p2)
    elif c2_info.get("player_png"):
        p2_final = fetch_online_image(c2_info["player_png"])
    else:
        p2_final = None

    # Flags
    t1_flag = fetch_online_image(c1_info["flag"]) if c1_info.get("flag") else None
    t2_flag = fetch_online_image(c2_info["flag"]) if c2_info.get("flag") else None
    bg_final = Image.open(bg_file) if bg_file else None

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
        t1_flag=t1_flag,
        t2_flag=t2_flag
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
