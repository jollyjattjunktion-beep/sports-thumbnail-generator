import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import requests
import io
import os
import json
import re
from bs4 import BeautifulSoup

# --- 1. Page Configuration ---
st.set_page_config(page_title="4K Sports Thumbnail Studio", layout="wide")

CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 2160

# --- 2. Fallback Captain & Flag Database ---
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

def load_robust_font(size):
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
