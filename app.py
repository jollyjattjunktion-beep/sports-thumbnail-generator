        if left_captain_url.strip():
            attempted += 1
            img1 = fetch_online_image(left_captain_url.strip())
            if img1:
                st.session_state.p1_cutout = img1
                loaded += 1
            else:
                st.error("Could not load the left image. Check that this is a direct, publicly accessible image URL.")
        if right_captain_url.strip():
            attempted += 1
            img2 = fetch_online_image(right_captain_url.strip())
            if img2:
                st.session_state.p2_cutout = img2
                loaded += 1
            else:
                st.error("Could not load the right image. Check that this is a direct, publicly accessible image URL.")

        if attempted == 0:
            st.warning("Paste at least one captain image URL first.")
        elif loaded:
            st.success(f"Fetched {loaded} captain image{'s' if loaded != 1 else ''}. The preview will use them automatically.")

    st.subheader("2. Match & Teams Setup")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        team1 = st.text_input(
            "Team 1 Code",
            value=st.session_state.t1_code or "IND",
            key="team1_code_input",
        ).strip().upper()
    with col_t2:
        team2 = st.text_input(
            "Team 2 Code",
            value=st.session_state.t2_code or "WI",
            key="team2_code_input",
        ).strip().upper()

    col_txt1, col_txt2 = st.columns(2)
    with col_txt1:
        match_status = st.text_input("Main Status", value="LIVE")
    with col_txt2:
        match_badge = st.text_input("Badge Info", value="2nd ODI")

    channel_title = st.text_input("Channel Title", value="PREET SPORTS")

    st.subheader("3. Optional Manual Uploads")
    bg_file = st.file_uploader("Upload Custom 4K Stadium", type=["png", "jpg", "jpeg"])
    custom_p1 = st.file_uploader("Manual Left Cutout (PNG)", type=["png"])
    custom_p2 = st.file_uploader("Manual Right Cutout (PNG)", type=["png"])

# Resolve Captain & Image Assets
c1_info = CAPTAIN_DATABASE.get(team1, {})
c2_info = CAPTAIN_DATABASE.get(team2, {})

if custom_p1:
    p1_final = Image.open(custom_p1)
elif st.session_state.p1_cutout:
    p1_final = st.session_state.p1_cutout
elif c1_info.get("player_png"):
    p1_final = fetch_online_image(c1_info["player_png"])
else:
    p1_final = None

if custom_p2:
    p2_final = Image.open(custom_p2)
elif st.session_state.p2_cutout:
    p2_final = st.session_state.p2_cutout
elif c2_info.get("player_png"):
    p2_final = fetch_online_image(c2_info["player_png"])
else:
    p2_final = None

t1_flag = fetch_online_image(c1_info.get("flag")) if c1_info.get("flag") else None
t2_flag = fetch_online_image(c2_info.get("flag")) if c2_info.get("flag") else None
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
