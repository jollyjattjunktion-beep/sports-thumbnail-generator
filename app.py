import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import io
import os

# --- Page Config ---
st.set_page_config(page_title="4K Sports Thumbnail Studio", layout="wide")

CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 2160

def draw_pill_badge(draw, bbox, fill_color, border_color=None, border_width=0, radius=50):
    """Draws a rounded pill banner with an optional border."""
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill_color)
    if border_color and border_width > 0:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, outline=border_color, width=border_width)

def draw_arrow_banner(draw, x, y, width, height, text, font, direction="left"):
    """Draws the sharp team name banner (e.g. IND, WI) with pointed edge."""
    # Base polygon with pointed arrow
    if direction == "left":
        points = [
            (x, y),
            (x + width - height // 2, y),
            (x + width, y + height // 2),
            (x + width - height // 2, y + height),
            (x, y + height)
        ]
    else:  # right-pointing arrow
        points = [
            (x + height // 2, y),
            (x + width, y),
            (x + width, y + height),
            (x + height // 2, y + height),
            (x, y + height // 2)
        ]
    
    # Draw dark backing and white border
    draw.polygon(points, fill=(10, 10, 10))
    # Border
    draw.line(points + [points[0]], fill=(255, 255, 255), width=8)

    # Text rendering centered
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
        canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (25, 40, 70, 255))

    # 2. Add Left Player (India / Player 1)
    if p1_img:
        p1 = p1_img.convert("RGBA")
        p1_aspect = p1.width / p1.height
        target_h = int(CANVAS_HEIGHT * 0.95)
        target_w = int(target_h * p1_aspect)
        p1 = p1.resize((target_w, target_h), Image.Resampling.LANCZOS)
        # Position anchored bottom-left
        canvas.paste(p1, (int(CANVAS_WIDTH * 0.05), CANVAS_HEIGHT - target_h), p1)

    # 3. Add Right Player (West Indies / Player 2)
    if p2_img:
        p2 = p2_img.convert("RGBA")
        p2_aspect = p2.width / p2.height
        target_h = int(CANVAS_HEIGHT * 0.95)
        target_w = int(target_h * p2_aspect)
        p2 = p2.resize((target_w, target_h), Image.Resampling.LANCZOS)
        # Position anchored bottom-right
        canvas.paste(p2, (CANVAS_WIDTH - target_w - int(CANVAS_WIDTH * 0.05), CANVAS_HEIGHT - target_h), p2)

    # Overlay & Draw setup
    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Load system or local TTF fonts (Fallbacks to default if not found)
    try:
        font_live = ImageFont.truetype("arialbd.ttf", 460)
        font_sub = ImageFont.truetype("arialbd.ttf", 160)
        font_team = ImageFont.truetype("arialbd.ttf", 220)
        font_brand = ImageFont.truetype("arialbd.ttf", 110)
    except:
        font_live = ImageFont.load_default()
        font_sub = font_live
        font_team = font_live
        font_brand = font_live

    # 4. Top Branding Pill ("PREET SPORTS")
    brand_bbox = font_brand.getbbox(channel_text)
    bw, bh = brand_bbox[2] - brand_bbox[0], brand_bbox[3] - brand_bbox[1]
    px, py = CANVAS_WIDTH // 2, 160
    pad_x, pad_y = 70, 30
    draw_pill_badge(draw, (px - bw//2 - pad_x, py - pad_y, px + bw//2 + pad_x, py + bh + pad_y),
                    fill_color=(255, 255, 255), border_color=(220, 30, 30), border_width=12, radius=60)
    draw.text((px - bw//2, py - brand_bbox[1]), channel_text, font=font_brand, fill=(220, 20, 20))

    # 5. Center "LIVE" Text with 3D White Outline & Shadow
    live_bbox = font_live.getbbox(match_status)
    lw, lh = live_bbox[2] - live_bbox[0], live_bbox[3] - live_bbox[1]
    lx, ly = (CANVAS_WIDTH - lw) // 2, (CANVAS_HEIGHT // 2) - 450

    # Thick White Border for LIVE
    border_px = 24
    for dx in range(-border_px, border_px + 1, 4):
        for dy in range(-border_px, border_px + 1, 4):
            draw.text((lx + dx, ly + dy - live_bbox[1]), match_status, font=font_live, fill=(255, 255, 255))
    # Red Front Face
    draw.text((lx, ly - live_bbox[1]), match_status, font=font_live, fill=(225, 25, 25))

    # 6. "2nd ODI" Blue Sub-Badge
    sub_bbox = font_sub.getbbox(match_badge)
    sw, sh = sub_bbox[2] - sub_bbox[0], sub_bbox[3] - sub_bbox[1]
    sx, sy = CANVAS_WIDTH // 2, ly + lh + 130
    spad_x, spad_y = 120, 35
    draw_pill_badge(draw, (sx - sw//2 - spad_x, sy - spad_y, sx + sw//2 + spad_x, sy + sh + spad_y),
                    fill_color=(15, 75, 175), border_color=(255, 255, 255), border_width=10, radius=50)
    draw.text((sx - sw//2, sy - sub_bbox[1]), match_badge, font=font_sub, fill=(255, 230, 0))

    # 7. Bottom Team Badges (IND & WI banners)
    banner_w, banner_h = 1100, 300
    draw_arrow_banner(draw, 100, CANVAS_HEIGHT - banner_h - 100, banner_w, banner_h, t1_name, font_team, "left")
    draw_arrow_banner(draw, CANVAS_WIDTH - banner_w - 100, CANVAS_HEIGHT - banner_h - 100, banner_w, banner_h, t2_name, font_team, "right")

    # 8. Circle Flags (Top Left & Top Right)
    flag_size = 380
    if t1_flag:
        flag1 = t1_flag.convert("RGBA").resize((flag_size, flag_size), Image.Resampling.LANCZOS)
        # Circular mask
        mask = Image.new("L", (flag_size, flag_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, flag_size, flag_size), fill=255)
        overlay.paste(flag1, (100, 100), mask)
        draw.ellipse((95, 95, 100 + flag_size + 5, 100 + flag_size + 5), outline=(255, 255, 255), width=16)

    if t2_flag:
        flag2 = t2_flag.convert("RGBA").resize((flag_size, flag_size), Image.Resampling.LANCZOS)
        mask2 = Image.new("L", (flag_size, flag_size), 0)
        ImageDraw.Draw(mask2).ellipse((0, 0, flag_size, flag_size), fill=255)
        overlay.paste(flag2, (CANVAS_WIDTH - flag_size - 100, 100), mask2)
        draw.ellipse((CANVAS_WIDTH - flag_size - 105, 95, CANVAS_WIDTH - 95, 100 + flag_size + 5), outline=(255, 255, 255), width=16)

    return Image.alpha_composite(canvas, overlay)


# --- UI Layout ---
st.title("🏏 4K Sports Thumbnail Generator")
st.write("Generate clean, crisp, human-designed sports thumbnails without AI facial distortions.")

col_ctrl, col_preview = st.columns([1, 1.2])

with col_ctrl:
    st.subheader("1. Match Details")
    channel_title = st.text_input("Channel Branding", value="PREET SPORTS")
    live_text = st.text_input("Header Status", value="LIVE")
    match_badge = st.text_input("Sub-Heading / Match Info", value="2nd ODI")

    st.subheader("2. Teams & Flags")
    c1, c2 = st.columns(2)
    with c1:
        t1_code = st.text_input("Team 1 Code", value="IND")
        t1_flag_file = st.file_uploader("Upload Team 1 Flag", type=["png", "jpg", "webp"], key="flag1")
    with c2:
        t2_code = st.text_input("Team 2 Code", value="WI")
        t2_flag_file = st.file_uploader("Upload Team 2 Flag", type=["png", "jpg", "webp"], key="flag2")

    st.subheader("3. Assets & Cutouts")
    bg_file = st.file_uploader("Upload Stadium Background (4K)", type=["png", "jpg"])
    p1_file = st.file_uploader("Upload Left Player (Transparent PNG)", type=["png"])
    p2_file = st.file_uploader("Upload Right Player (Transparent PNG)", type=["png"])

with col_preview:
    st.subheader("Thumbnail Live Preview")
    
    # Load Image instances
    bg = Image.open(bg_file) if bg_file else None
    p1 = Image.open(p1_file) if p1_file else None
    p2 = Image.open(p2_file) if p2_file else None
    f1 = Image.open(t1_flag_file) if t1_flag_file else None
    f2 = Image.open(t2_flag_file) if t2_flag_file else None

    # Generate
    result = generate_thumbnail(
        bg_img=bg,
        p1_img=p1,
        p2_img=p2,
        channel_text=channel_title,
        match_status=live_text,
        match_badge=match_badge,
        t1_name=t1_code,
        t2_name=t2_code,
        t1_flag=f1,
        t2_flag=f2
    )

    st.image(result, use_container_width=True)

    # 4K Download Buffer
    buf = io.BytesIO()
    result.save(buf, format="PNG", quality=100)
    st.download_button(
        label="⬇️ Download 4K Thumbnail (3840 x 2160)",
        data=buf.getvalue(),
        file_name=f"{t1_code}_vs_{t2_code}_4K_thumbnail.png",
        mime="image/png",
        use_container_width=True
    )
