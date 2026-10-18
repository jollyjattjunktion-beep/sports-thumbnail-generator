import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
import io
import os
import re

# --- 1. Page Configuration ---
st.set_page_config(page_title="4K Sports Thumbnail Studio", layout="wide")

CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 2160

# --- 2. High-Resolution Stadium Presets (Matches Image 2) ---
DEFAULT_STADIUM_URL = "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?q=80&w=3840&auto=format&fit=crop"

# Built-in Flag / Logo Database
TEAM_FLAGS = {
    "AUS": "https://flagcdn.com/w320/au.png",
    "AUS WOMEN": "https://flagcdn.com/w320/au.png",
    "NZ": "https://flagcdn.com/w320/nz.png",
    "NZ WOMEN": "https://flagcdn.com/w320/nz.png",
    "IND": "https://flagcdn.com/w320/in.png",
    "INDIA": "https://flagcdn.com/w320/in.png",
    "WI": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "ENG": "https://flagcdn.com/w320/gb-eng.png",
    "PAK": "https://flagcdn.com/w320/pk.png",
    "SA": "https://flagcdn.com/w320/za.png",
}

# --- 3. Font Engine ---
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

def get_fitted_font(text, max_w, max_h, start_size=230):
    size = start_size
    while size > 50:
        f = load_font(size)
        bbox = f.getbbox(text)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= max_w and h <= max_h:
            return f
        size -= 10
    return load_font(size)

# --- 4. Network Fetcher (Upgrades Cricinfo Low-Res to HD) ---
@st.cache_data(show_spinner=False)
def fetch_online_image(url):
    if not url or not str(url).strip():
        return None
    url = url.strip()
    # Strip downscaling filters from ESPNcricinfo URLs
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
            return Image.open(io.BytesIO(res.content)).convert("RGBA")
    except Exception as e:
        st.warning(f"Failed to fetch image: {e}")
    return None

# --- 5. Stadium Daylight Background Generator (Fallback) ---
@st.cache_resource
def generate_daylight_stadium():
    img = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (30, 110, 200, 255))
    draw = ImageDraw.Draw(img)

    # 1. Daylight Blue Sky Gradient
    sky_h = int(CANVAS_HEIGHT * 0.55)
    for y in range(sky_h):
        ratio = y / sky_h
        r = int(50 + ratio * 80)
        g = int(140 + ratio * 70)
        b = int(225 + ratio * 25)
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(r, g, b, 255))

    # 2. Stadium Stands / Crowd Level
    stand_top = int(CANVAS_HEIGHT * 0.32)
    stand_bottom = int(CANVAS_HEIGHT * 0.58)
    for y in range(stand_top, stand_bottom):
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(65, 75, 95, 255))

    # 3. Floodlight Towers (Left & Right)
    def draw_floodlight(cx, cy):
        draw.ellipse([cx - 260, cy - 140, cx + 260, cy + 140], fill=(255, 255, 255, 240))
        for ox in [-140, -70, 0, 70, 140]:
            for oy in [-60, 0, 60]:
                draw.rectangle([cx + ox - 20, cy + oy - 15, cx + ox + 20, cy + oy + 15], fill=(255, 255, 220, 255))

    draw_floodlight(int(CANVAS_WIDTH * 0.26), int(CANVAS_HEIGHT * 0.15))
    draw_floodlight(int(CANVAS_WIDTH * 0.74), int(CANVAS_HEIGHT * 0.15))

    # 4. Lush Green Outfield
    grass_top = int(CANVAS_HEIGHT * 0.55)
    for y in range(grass_top, CANVAS_HEIGHT):
        ratio = (y - grass_top) / (CANVAS_HEIGHT - grass_top)
        r = int(70 + ratio * 30)
        g = int(155 + ratio * 30)
        b = int(25 + ratio * 15)
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(r, g, b, 255))

    # 5. Pitch Oval in Center
    draw.ellipse([CANVAS_WIDTH//2 - 450, CANVAS_HEIGHT - 650, CANVAS_WIDTH//2 + 450, CANVAS_HEIGHT - 380], fill=(190, 170, 115, 255))
    return img.filter(ImageFilter.GaussianBlur(1))

# --- 6. Graphic Components Matching Image 2 ---
def apply_sports_color_grade(image):
    if not image:
        return None
    image = ImageEnhance.Color(image).enhance(1.20)
    image = ImageEnhance.Contrast(image).enhance(1.15)
    image = ImageEnhance.Sharpness(image).enhance(1.25)
    return image

def render_player(canvas, player_img, side="left"):
    """Scales and positions player cutouts from the bottom corners."""
    p = apply_sports_color_grade(player_img)
    aspect = p.width / p.height
    target_h = int(CANVAS_HEIGHT * 0.96)
    target_w = int(target_h * aspect)
    resized = p.resize((target_w, target_h), Image.Resampling.LANCZOS)

    if "A" not in resized.getbands():
        resized.putalpha(Image.new("L", (target_w, target_h), 255))

    if side == "left":
        pos_x = int(CANVAS_WIDTH * 0.01)
    else:
        pos_x = CANVAS_WIDTH - target_w - int(CANVAS_WIDTH * 0.01)
    pos_y = CANVAS_HEIGHT - target_h

    # Stadium Floodlight Edge Glow
    alpha = resized.split()[3]
    glow_mask = alpha.filter(ImageFilter.MaxFilter(21)).filter(ImageFilter.GaussianBlur(14))
    glow_surface = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 0))
    glow_surface.putalpha(glow_mask)

    canvas.paste(glow_surface, (pos_x, pos_y), glow_surface)
    canvas.paste(resized, (pos_x, pos_y), resized)

def draw_pill(draw, bbox, fill_color, border_color=None, border_width=0, radius=55):
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill_color)
    if border_color and border_width > 0:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, outline=border_color, width=border_width)

def draw_team_banner_pointing_inward(draw, width, height, y, text, side="left"):
    """
    Left Banner (IND): Starts at x=0, points RIGHT (>) towards center.
    Right Banner (WI): Starts at x=CANVAS_WIDTH, points LEFT (<) towards center.
    """
    arrow_depth = 170

    if side == "left":
        points = [
            (-20, y),
            (width - arrow_depth, y),
            (width, y + height // 2),
            (width - arrow_depth, y + height),
            (-20, y + height)
        ]
        usable_w = width - arrow_depth
        font = get_fitted_font(text, usable_w - 60, height - 50, start_size=230)
        t_box = font.getbbox(text)
        tw = t_box[2] - t_box[0]
        th = t_box[3] - t_box[1]
        tx = (usable_w - tw) // 2
        ty = y + (height - th) // 2 - t_box[1]
    else:
        x_start = CANVAS_WIDTH - width
        points = [
            (CANVAS_WIDTH + 20, y),
            (x_start + arrow_depth, y),
            (x_start, y + height // 2),
            (x_start + arrow_depth, y + height),
            (CANVAS_WIDTH + 20, y + height)
        ]
        usable_w = width - arrow_depth
        font = get_fitted_font(text, usable_w - 60, height - 50, start_size=230)
        t_box = font.getbbox(text)
        tw = t_box[2] - t_box[0]
        th = t_box[3] - t_box[1]
        tx = x_start + arrow_depth + (usable_w - tw) // 2
        ty = y + (height - th) // 2 - t_box[1]

    # Solid Black Polygon Fill
    draw.polygon(points, fill=(5, 5, 5, 255))
    # Crisp Thick White Border
    draw.line(points + [points[0]], fill=(255, 255, 255, 255), width=18)
    # Centered White Bold Text
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

def draw_circular_flag(canvas, flag_img, pos_x, pos_y, size=380):
    if not flag_img:
        return
    f = flag_img.resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)

    flag_circle = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    flag_circle.paste(f, (0, 0), mask)

    canvas.paste(flag_circle, (pos_x, pos_y), flag_circle)
    # Thick White Border Ring
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([pos_x - 6, pos_y - 6, pos_x + size + 6, pos_y + size + 6], outline=(255, 255, 255, 255), width=18)

# --- 7. Main Rendering Pipeline ---
def generate_thumbnail(bg_img, p1_img, p2_img, t1_name, t2_name, status_text, badge_text, channel_p1, channel_p2, f1_img, f2_img):
    # 1. Base Stadium Canvas
    if bg_img:
        canvas = bg_img.convert("RGBA").resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.LANCZOS)
    else:
        canvas = generate_daylight_stadium().copy()

    # 2. Render Left and Right Players
    if p1_img:
        render_player(canvas, p1_img, side="left")
    if p2_img:
        render_player(canvas, p2_img, side="right")

    # 3. Text Overlay Layer
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 4. Top Branding Pill: "PREET" (Black) + "SPORTS" (Red)
    f_brand = load_font(115)
    bbox_p1 = f_brand.getbbox(channel_p1)
    bbox_p2 = f_brand.getbbox(channel_p2)
    w_p1 = bbox_p1[2] - bbox_p1[0]
    w_p2 = bbox_p2[2] - bbox_p2[0]
    space_w = 30
    total_brand_w = w_p1 + space_w + w_p2
    pill_h = 170
    pill_w = total_brand_w + 170
    px = (CANVAS_WIDTH - pill_w) // 2
    py = 65

    draw_pill(draw, (px, py, px + pill_w, py + pill_h), fill_color=(255, 255, 255, 255), border_color=(215, 25, 25, 255), border_width=14, radius=85)
    # Render "PREET" in Black
    start_tx = px + (pill_w - total_brand_w) // 2
    ty_brand = py + (pill_h - (bbox_p1[3] - bbox_p1[1])) // 2 - bbox_p1[1]
    draw.text((start_tx, ty_brand), channel_p1, font=f_brand, fill=(10, 10, 10, 255))
    # Render "SPORTS" in Red
    draw.text((start_tx + w_p1 + space_w, ty_brand), channel_p2, font=f_brand, fill=(215, 25, 25, 255))

    # 5. Center "LIVE" Text with 3D White Outline & Drop Shadow
    f_live = load_font(480)
    bbox_live = f_live.getbbox(status_text)
    lw = bbox_live[2] - bbox_live[0]
    lh = bbox_live[3] - bbox_live[1]
    lx = (CANVAS_WIDTH - lw) // 2
    ly = (CANVAS_HEIGHT // 2) - 430

    # Multi-pass Thick White Stroke
    stroke_px = 24
    for dx in range(-stroke_px, stroke_px + 1, 6):
        for dy in range(-stroke_px, stroke_px + 1, 6):
            draw.text((lx + dx, ly + dy - bbox_live[1]), status_text, font=f_live, fill=(255, 255, 255, 255))
    # Red Face
    draw.text((lx, ly - bbox_live[1]), status_text, font=f_live, fill=(225, 20, 20, 255))

    # 6. Blue Pill Badge: "2nd ODI" / "1st T20I" in Yellow
    f_badge = load_font(180)
    bbox_b = f_badge.getbbox(badge_text)
    bw = bbox_b[2] - bbox_b[0]
    bh = bbox_b[3] - bbox_b[1]
    bx = CANVAS_WIDTH // 2
    by = ly + lh + 140
    pad_x = 130
    pad_y = 35
    draw_pill(draw, (bx - bw//2 - pad_x, by - pad_y, bx + bw//2 + pad_x, by + bh + pad_y),
              fill_color=(12, 75, 175, 255), border_color=None, border_width=0, radius=60)
    draw.text((bx - bw//2, by - bbox_b[1]), badge_text, font=f_badge, fill=(255, 235, 10, 255))

    # 7. Team Banners (Overlaying the Players)
    banner_w = 1260
    banner_h = 320
    banner_y = CANVAS_HEIGHT - banner_h - 90
    draw_team_banner_pointing_inward(draw, banner_w, banner_h, banner_y, t1_name, side="left")
    draw_team_banner_pointing_inward(draw, banner_w, banner_h, banner_y, t2_name, side="right")

    # Combine Base and Overlay
    final_canvas = Image.alpha_composite(canvas, overlay)

    # 8. Top Flags (Corner Medallions)
    draw_circular_flag(final_canvas, f1_img, pos_x=65, pos_y=55, size=370)
    draw_circular_flag(final_canvas, f2_img, pos_x=CANVAS_WIDTH - 370 - 65, pos_y=55, size=370)

    return final_canvas


# --- 8. Streamlit App Interface ---
st.title("🏏 4K Sports Thumbnail Studio")

col_left, col_right = st.columns([1, 1.25])

with col_left:
    st.subheader("1. Player Image URLs (HD Cutouts)")
    p1_url = st.text_input(
        "Left Player URL (e.g. Healy / Rohit):",
        value="https://img1.hscicdn.com/image/upload/f_auto,t_ds_square_w_800,q_80/lsci/db/PICTURES/CMS/321600/321614.png"
    )
    p2_url = st.text_input(
        "Right Player URL (e.g. Kerr / Hope):",
        value="https://img1.hscicdn.com/image/upload/f_auto,t_ds_square_w_800,q_80/lsci/db/PICTURES/CMS/321600/321617.png"
    )

    st.subheader("2. Match & Teams Setup")
    c1, c2 = st.columns(2)
    with c1:
        team1 = st.text_input("Left Team Code/Name", value="AUS WOMEN").strip().upper()
    with c2:
        team2 = st.text_input("Right Team Code/Name", value="NZ WOMEN").strip().upper()

    c3, c4 = st.columns(2)
    with c3:
        status_text = st.text_input("Status Headline", value="LIVE")
    with c4:
        badge_text = st.text_input("Match Badge Info", value="1st T20I")

    st.subheader("3. Branding & Badges")
    cb1, cb2 = st.columns(2)
    with cb1:
        brand_p1 = st.text_input("Brand Word 1 (Black)", value="PREET")
    with cb2:
        brand_p2 = st.text_input("Brand Word 2 (Red)", value="SPORTS")

    st.subheader("4. Stadium Background (Optional)")
    custom_bg = st.file_uploader("Upload Custom 4K Stadium (PNG/JPG)", type=["png", "jpg", "jpeg"])

# Fetch Resources
with st.spinner("Rendering 4K Broadcast Graphic..."):
    img_p1 = fetch_online_image(p1_url)
    img_p2 = fetch_online_image(p2_url)

    # Resolve Flags from Team names
    f1_url = TEAM_FLAGS.get(team1) or TEAM_FLAGS.get(team1.split()[0], None)
    f2_url = TEAM_FLAGS.get(team2) or TEAM_FLAGS.get(team2.split()[0], None)
    flag1 = fetch_online_image(f1_url) if f1_url else None
    flag2 = fetch_online_image(f2_url) if f2_url else None

    # Resolve Stadium
    if custom_bg:
        bg_image = Image.open(custom_bg)
    else:
        bg_image = fetch_online_image(DEFAULT_STADIUM_URL)

with col_right:
    st.subheader("Live 4K Preview")
    result = generate_thumbnail(
        bg_img=bg_image,
        p1_img=img_p1,
        p2_img=img_p2,
        t1_name=team1,
        t2_name=team2,
        status_text=status_text,
        badge_text=badge_text,
        channel_p1=brand_p1,
        channel_p2=brand_p2,
        f1_img=flag1,
        f2_img=flag2
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
