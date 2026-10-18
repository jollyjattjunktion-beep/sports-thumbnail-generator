import json
import re
from bs4 import BeautifulSoup

@st.cache_data(show_spinner=False)
def fetch_from_cricinfo_url(url):
    """
    Scrapes ESPNcricinfo squad/match page, extracts team names,
    captains (marked with 'c' or 'captain'), and their official headshot URLs.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return None, "Unable to access Cricinfo page. Check the URL."

        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. Inspect Next.js application payload for structured match data
        next_data_tag = soup.find("script", id="__NEXT_DATA__")
        match_info = {}

        if next_data_tag:
            data = json.loads(next_data_tag.string)
            props = data.get("props", {}).get("appPageProps", {})
            
            # Extract squad / team data
            squad_data = props.get("data", {}).get("squads", []) or props.get("data", {}).get("teams", [])
            
            teams_found = []
            for team in squad_data:
                team_name = team.get("team", {}).get("name") or team.get("name", "TEAM")
                team_abbrev = team.get("team", {}).get("abbreviation") or team_name[:3].upper()
                
                captain_name = None
                captain_img = None
                
                # Search for player marked as captain
                players = team.get("players", [])
                for p in players:
                    player_obj = p.get("player", p)
                    is_capt = p.get("isCaptain", False) or "(c)" in player_obj.get("name", "").lower()
                    
                    if is_capt and not captain_name:
                        captain_name = player_obj.get("name", "").replace("(c)", "").strip()
                        # Headshot image URL
                        img_obj = player_obj.get("image", {})
                        if isinstance(img_obj, dict):
                            captain_img = img_obj.get("url")
                        elif isinstance(img_obj, str):
                            captain_img = img_obj
                        break
                
                # Fallback to first player if no explicit captain tag is present
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

        # 2. HTML Fallback parsing if JSON isn't directly exposed
        players_html = soup.find_all(["div", "li"], class_=re.compile(r"player|squad", re.I))
        # Returns parsed data or error message
        return None, "Could not automatically isolate captains from this specific URL. You can paste the direct image URLs below."
        
    except Exception as e:
        return None, f"Error reading URL: {str(e)}"
