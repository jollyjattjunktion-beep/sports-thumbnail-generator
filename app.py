import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
import io
import os
from rembg import remove

# --- Page Config ---
st.set_page_config(page_title="4K Sports Thumbnail Studio", layout="wide")

CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 2160

# Captain & Flag Roster Database
CAPTAIN_DATABASE = {
    "IND": {"name": "Rohit Sharma", "flag": "https://flagcdn.com/w320/in.png"},
    "INDIA": {"name": "Rohit Sharma", "flag": "https://flagcdn.com/w320/in.png"},
    "WI": {"name": "Shai Hope", "flag": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png"},
    "WEST INDIES": {"name": "Shai Hope", "flag": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png"},
    "AUS": {"name": "Pat Cummins", "flag": "https://flagcdn.com/w320/au.png"},
    "AUSTRALIA": {"name": "Pat Cummins", "flag": "https://flagcdn.com/w320/au.png"},
    "ENG": {"name": "Jos Buttler", "flag": "https://flagcdn.com/w320/gb-eng.png"},
    "ENGLAND": {"name": "Jos Buttler", "flag": "https://flagcdn.com/w320/gb-eng.png"},
    "PAK": {"name": "Babar Azam", "flag": "https://flagcdn.com/w320/pk.png"},
    "PAKISTAN": {"name": "Babar Azam", "flag": "https://flagcdn.com/w320/pk.png"},
    "SA": {"name": "Temba Bavuma", "flag": "https://flagcdn.com/w320/za.png"},
    "SOUTH AFRICA": {"name": "Temba Bavuma", "flag": "https://flagcdn.com/w320/za.png"},
    "NZ": {"name": "Kane Williamson", "flag": "https://flagcdn.com/w320/nz.png"},
    "NEW ZEALAND": {"name": "Kane Williamson", "flag": "https://flagcdn.com/w320/nz.png"},
    "BAN": {"name": "Najmul Hossain Shanto", "flag": "https://flagcdn.com/w320/bd.png"},
    "AFG": {"name": "Hashmatullah Shahidi", "flag": "https://flagcdn.com/w320/af.png"},
    "SL": {"name": "Charith Asalanka", "flag": "https://flagcdn.com/w320/lk.png"},
}

def load_robust_font(size):
    """Loads a bold font across Windows, macOS, or Linux/Render."""
    font_candidates = [
        "arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "Helvetica-Bold.ttf",
        "Arial.ttf"
    ]
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    return ImageFont.load_default()

@st.cache_data(show_spinner=False)
def fetch_player_image_from_web(player_name):
    """Searches Wikipedia/Wikimedia API for full portrait, then removes background."""
    try:
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={player_name.replace(' ', '%20')}&prop=pageimages&format=json&pithumbsize=2000"
        headers = {'User-Agent': 'SportsThumbnailApp/1.0 (contact@example.com)'}
        res = requests.get(search_url, headers=headers, timeout=10).json()
        pages = res.get("query", {}).get("pages", {})

        img_url = None
        for _, page in pages.items():
            if "thumbnail" in page:
                img_url = page["thumbnail"]["source"]
                break

        if not img_url:
            return None

        img_data = requests.get(img_url, headers=headers, timeout=15).content
        input_image = Image.open(io.BytesIO(img_data)).convert("RGBA")
        return remove(input_image)
    except Exception as e:
        st.warning(f"Could not load cutout for {player_name}: {e}")
        return None

@st.cache_data(show_spinner=False)
def fetch_flag_image(url):
    try:
        headers = {'User-Agent': 'SportsThumbnailApp/1.0'}
        res = requests.get(url, headers=headers, timeout=10)
        return Image.open(io.BytesIO(res.content)).convert("RGBA")
    except:
        return None

def apply_sports_color_grade(image):
    """Enhances contrast, saturation, and sharpness for sports thumbnails."""
    if not image:
        return None
    # 1. Boost Color Saturation
    enhancer = ImageEnhance.Color(image)
    image = enhancer.enhance(1.25)
    # 2. Boost Contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.20)
    # 3. Boost Sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(1.35)
    return image

def render_player_with_rim_light(canvas, player_img, pos_x, pos_y, target_w, target_h, glow_color=(255, 255, 255)):
    """Pastes player onto canvas with a stadium floodlight edge glow."""
    resized = player_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    alpha = resized.split()[3]

    # Expand and blur the alpha mask to create rim lighting
    glow_mask = alpha.filter(ImageFilter.MaxFilter(21)).filter(ImageFilter.GaussianBlur(15))
    glow_surface = Image.new("RGBA", (target_w, target_h), glow_color + (0,))
    glow_surface.putalpha(glow_mask)

    # Paste glow behind the player
    canvas.paste(glow_surface, (pos_x, pos_y), glow_surface)
    # Paste actual player cutout on top
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
    
    draw.polygon(points, fill=(10, 10, 10))
    draw.line(points + [points[0]], fill=(255, 255, 255), width=8)

    text_bbox = font.getbbox(text)
    tw, th = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    tx = x + (width - tw) // 2
    ty = y + (height - th) // 2 - text_bbox[1]
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255))

def generate_thumbnail(bg_img, p1_img, p2_img, channel_text, match_status, match_badge, t1_name, t2_name, t1_flag, t2_flag):
    # 1. Base Canvas
    if bg_img:
        canvas = bg_img.convert("RGBA").resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
    else:
        canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (20, 35, 65, 255))

    # 2. Render Left Player with Stadium Rim Glow
    if p1_img:
        p1 = apply_sports_color_grade(p1_img.convert("RGBA"))
        p1_aspect = p1.width / p1.height
        target_h = int(CANVAS_HEIGHT * 0.95)
        target_w = int(target_h * p1_aspect)
        render_player_with_rim_light(canvas, p1, int(CANVAS_WIDTH * 0.05), CANVAS_HEIGHT - target_h, target_w, target_h)

    # 3. Render Right Player with Stadium Rim Glow
    if p2_img:
        p2 = apply_sports_color_grade(p2_img.convert("RGBA"))
        p2_aspect = p2.width / p2.height
        target_h = int(CANVAS_HEIGHT * 0.95)
        target_w = int(target_h * p2_aspect)
        render_player_with_rim_light(canvas, p2, CANVAS_WIDTH - target_w - int(CANVAS_WIDTH * 0.05), CANVAS_HEIGHT - target_h, target_w, target_h)

    # 4. Text & Badges Overlay
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_live = load_robust_font(460)
    font_sub = load_robust_font(160)
    font_team = load_robust_font(220)
    font_brand = load_robust_font(110)

    # Branding Badge (PREET SPORTS)
    brand_bbox = font_brand.getbbox(channel_text)
    bw, bh = brand_bbox[2] - brand_bbox[0], brand_bbox[3] - brand_bbox[1]
    px, py = CANVAS_WIDTH // 2, 160
    draw_pill_badge(draw, (px - bw//2 - 70, py - 30, px + bw//2 + 70, py + bh + 30),
                    fill_color=(255, 255, 255), border_color=(220, 30, 30), border_width=12, radius=60)
    draw.text((px - bw//2, py - brand_bbox[1]), channel_text, font=font_brand, fill=(220, 20, 20))

    # Center LIVE Text with 3D White Stroke
    live_bbox = font_live.getbbox(match_status)
    lw, lh = live_bbox[2] - live_bbox[0], live_bbox[3] - live_bbox[1]
    lx, ly = (CANVAS_WIDTH - lw) // 2, (CANVAS_HEIGHT // 2) - 450

    border_px = 24
    for dx in range(-border_px, border_px + 1, 4):
        for dy in range(-border_px, border_px + 1, 4):
            draw.text((lx + dx, ly + dy - live_bbox[1]), match_status, font=font_live, fill=(255, 255, 255))
    draw.text((lx, ly - live_bbox[1]), match_status, font=font_live, fill=(225, 25, 25))

    # Sub-Heading (e.g., 2nd ODI)
    sub_bbox = font_sub.getbbox(match_badge)
    sw, sh = sub_bbox[2] - sub_bbox[0], sub_bbox[3] - sub_bbox[1]
    sx, sy = CANVAS_WIDTH // 2, ly + lh + 130
    draw_pill_badge(draw, (sx - sw//2 - 120, sy - 35, sx + sw//2 + 120, sy + sh + 35),
                    fill_color=(15, 75, 175), border_color=(255, 255, 255), border_width=10, radius=50)
    draw.text((sx - sw//2, sy - sub_bbox[1]), match_badge, font=font_sub, fill=(255, 230, 0))

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
        draw.ellipse((95, 95, 105 + flag_size, 105 + flag_size), outline=(255, 255, 255), width=16)

    if t2_flag:
        f2 = t2_flag.convert("RGBA").resize((flag_size, flag_size), Image.Resampling.LANCZOS)
        mask2 = Image.new("L", (flag_size, flag_size), 0)
        ImageDraw.Draw(mask2).ellipse((0, 0, flag_size, flag_size), fill=255)
        overlay.paste(f2, (CANVAS_WIDTH - flag_size - 100, 100), mask2)
        draw.ellipse((CANVAS_WIDTH - flag_size - 105, 95, CANVAS_WIDTH - 95, 105 + flag_size), outline=(255, 255, 255), width=16)

    return Image.alpha_composite(canvas, overlay)


# --- Streamlit UI ---
st.title("🏏 Auto 4K Sports Thumbnail Generator")
st.caption("Auto-fetches captain cutouts, adds stadium rim glow, and creates broadcast-quality 4K graphics.")

# Session State Initialization
for key in ["p1_cutout", "p2_cutout", "f1_img", "f2_img"]:
    if key not in st.session_state:
        st.session_state[key] = None

col_left, col_right = st.columns([1, 1.2])

with col_left:
    st.subheader("1. Match & Teams")
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
    default_p1 = CAPTAIN_DATABASE.get(team1, {}).get("name", "")
    default_p2 = CAPTAIN_DATABASE.get(team2, {}).get("name", "")

    p1_name = st.text_input("Player 1 Name", value=default_p1)
    p2_name = st.text_input("Player 2 Name", value=default_p2)

    if st.button("⚡ Fetch HD Player Cutouts & Flags", type="primary"):
        with st.spinner("Fetching HD portraits, removing background, and color-grading..."):
            if p1_name:
                st.session_state.p1_cutout = fetch_player_image_from_web(p1_name)
            if p2_name:
                st.session_state.p2_cutout = fetch_player_image_from_web(p2_name)

            if team1 in CAPTAIN_DATABASE:
                st.session_state.f1_img = fetch_flag_image(CAPTAIN_DATABASE[team1]["flag"])
            if team2 in CAPTAIN_DATABASE:
                st.session_state.f2_img = fetch_flag_image(CAPTAIN_DATABASE[team2]["flag"])

    st.subheader("3. Optional Uploads (Overrides Auto-Fetch)")
    bg_file = st.file_uploader("Upload 4K Stadium BG", type=["png", "jpg"])
    custom_p1 = st.file_uploader("Manual Left Player Cutout", type=["png"])
    custom_p2 = st.file_uploader("Manual Right Player Cutout", type=["png"])

# Resolve Final Images
p1_final = Image.open(custom_p1) if custom_p1 else st.session_state.p1_cutout
p2_final = Image.open(custom_p2) if custom_p2 else st.session_state.p2_cutout
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
        t1_flag=st.session_state.f1_img,
        t2_flag=st.session_state.f2_img
    )

    st.image(result, use_container_width=True)

    buf = io.BytesIO()
    result.save(buf, format="PNG", quality=100)
    st.download_button(
        label="⬇️ Download 4K Thumbnail (3840 x 2160)",
        data=buf.getvalue(),
        file_name=f"{team1}_vs_{team2}_4K.png",
        mime="image/png",
        use_container_width=True
    )
