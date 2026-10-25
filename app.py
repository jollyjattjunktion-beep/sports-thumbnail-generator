import io
import base64
import gc
import hashlib
import json
import os
import re
import secrets
import time
from urllib.parse import urlsplit, urlunsplit, urljoin, urlencode

import requests
import numpy as np
import streamlit as st
from bs4 import BeautifulSoup
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

# =========================================================
# PREET SPORTS — IMAGE 1 STYLE 4K CRICKET THUMBNAIL STUDIO
# 3840 x 2160 | URL-based captain images | realistic stadium BG
# =========================================================
st.set_page_config(page_title="PREET SPORTS 4K Thumbnail Studio", layout="wide")


# =========================================================
# Canva MCP — reference-image editing OAuth helpers
# Uses the official Canva MCP image-editing tool with MEDIA references.
# OAuth credentials must be set in the hosting environment, never committed here.
# =========================================================
CANVA_MCP_URL = "https://api.canva.com/connect/v1/mcp"
CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"

@st.cache_resource
def _canva_pending_oauth_store():
    """Short-lived server-memory store for PKCE verifiers across the OAuth redirect."""
    return {}


def _canva_oauth_redirect_uri():
    configured = str(os.environ.get("CANVA_REDIRECT_URI", "")).strip()
    return configured


def _canva_authorization_link():
    client_id = str(os.environ.get("CANVA_CLIENT_ID", "")).strip()
    client_secret = str(os.environ.get("CANVA_CLIENT_SECRET", "")).strip()
    redirect_uri = _canva_oauth_redirect_uri()
    if not client_id or not client_secret:
        return None, "Add CANVA_CLIENT_ID and CANVA_CLIENT_SECRET in Render Environment."
    if not redirect_uri:
        return None, "Add CANVA_REDIRECT_URI in Render Environment and register the same URL in Canva Developer Portal."
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest()).decode("ascii").rstrip("=")
    state = secrets.token_urlsafe(32)
    now = time.time()
    pending = _canva_pending_oauth_store()
    for old_state, value in list(pending.items()):
        if now - float(value.get("created_at", 0)) > 900:
            pending.pop(old_state, None)
    pending[state] = {"verifier": verifier, "created_at": now}
    query = urlencode({
        "client_id": client_id,
        "response_type": "code",
        "scope": "asset:read asset:write",
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "s256",
        "state": state,
    })
    return "https://www.canva.com/api/oauth/authorize?" + query, None


def _canva_process_oauth_callback():
    """Exchange a Canva OAuth code for tokens on the redirect back to this app."""
    try:
        query = st.query_params
        code = str(query.get("code", "") or "")
        state = str(query.get("state", "") or "")
        oauth_error = str(query.get("error_description", "") or query.get("error", "") or "")
        if not code and not state and not oauth_error:
            return
        if oauth_error:
            st.session_state["canva_oauth_error"] = oauth_error[:500]
        else:
            pending = _canva_pending_oauth_store().pop(state, None)
            if not pending or time.time() - float(pending.get("created_at", 0)) > 900:
                st.session_state["canva_oauth_error"] = "Canva authorization state expired. Please generate a new Connect Canva link and try again."
            else:
                client_id = str(os.environ.get("CANVA_CLIENT_ID", "")).strip()
                client_secret = str(os.environ.get("CANVA_CLIENT_SECRET", "")).strip()
                redirect_uri = _canva_oauth_redirect_uri()
                if not client_id or not client_secret or not redirect_uri:
                    st.session_state["canva_oauth_error"] = "Canva OAuth environment variables are incomplete."
                else:
                    token_response = requests.post(
                        CANVA_TOKEN_URL,
                        auth=(client_id, client_secret),
                        data={
                            "grant_type": "authorization_code",
                            "code": code,
                            "code_verifier": pending["verifier"],
                            "redirect_uri": redirect_uri,
                        },
                        timeout=(10, 30),
                    )
                    if token_response.status_code >= 400:
                        detail = token_response.text[:500]
                        st.session_state["canva_oauth_error"] = f"Canva token exchange failed (HTTP {token_response.status_code}): {detail}"
                    else:
                        token_data = token_response.json()
                        if not token_data.get("access_token"):
                            st.session_state["canva_oauth_error"] = "Canva token response did not contain an access token."
                        else:
                            st.session_state["canva_access_token"] = token_data["access_token"]
                            st.session_state["canva_refresh_token"] = token_data.get("refresh_token", "")
                            st.session_state["canva_token_expiry"] = time.time() + int(token_data.get("expires_in", 14400)) - 90
                            st.session_state["canva_oauth_error"] = ""
                            st.session_state["canva_connected_notice"] = "Canva authorization succeeded for this app session."
    except Exception as exc:
        st.session_state["canva_oauth_error"] = f"Could not complete Canva authorization: {exc}"
    finally:
        # Remove one-time OAuth values from the visible URL after handling the callback.
        try:
            for key in ("code", "state", "error", "error_description"):
                if key in st.query_params:
                    st.query_params.pop(key, None)
        except Exception:
            pass


def _canva_valid_access_token():
    """Return a usable Canva access token, refreshing it when possible."""
    access_token = str(st.session_state.get("canva_access_token", "") or "").strip()
    expires_at = float(st.session_state.get("canva_token_expiry", 0) or 0)
    if access_token and expires_at > time.time() + 30:
        return access_token, None
    refresh_token = str(st.session_state.get("canva_refresh_token", "") or "").strip()
    client_id = str(os.environ.get("CANVA_CLIENT_ID", "")).strip()
    client_secret = str(os.environ.get("CANVA_CLIENT_SECRET", "")).strip()
    if not refresh_token or not client_id or not client_secret:
        return None, "Canva is not connected in this browser session. Connect Canva in Section 8 before converting."
    try:
        response = requests.post(
            CANVA_TOKEN_URL,
            auth=(client_id, client_secret),
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            timeout=(10, 30),
        )
        if response.status_code >= 400:
            st.session_state.pop("canva_access_token", None)
            st.session_state.pop("canva_refresh_token", None)
            return None, f"Canva session expired or could not refresh (HTTP {response.status_code}). Reconnect Canva in Section 8."
        data = response.json()
        access_token = str(data.get("access_token", "") or "")
        if not access_token:
            return None, "Canva refresh response did not contain an access token. Reconnect Canva."
        st.session_state["canva_access_token"] = access_token
        st.session_state["canva_token_expiry"] = time.time() + int(data.get("expires_in", 14400)) - 90
        if data.get("refresh_token"):
            st.session_state["canva_refresh_token"] = data["refresh_token"]
        return access_token, None
    except Exception as exc:
        return None, f"Canva token refresh failed: {exc}"


def _canva_parse_mcp_response(response):
    """Parse JSON or Streamable-HTTP server-sent-event responses from Canva MCP."""
    if response.status_code >= 400:
        detail = response.text[:900]
        try:
            err_obj = response.json()
            detail = json.dumps(err_obj, ensure_ascii=False)[:900]
        except Exception:
            pass
        raise RuntimeError(f"Canva MCP HTTP {response.status_code}: {detail}")
    body = (response.text or "").strip()
    if not body:
        return {}
    content_type = str(response.headers.get("Content-Type", "")).lower()
    if "text/event-stream" in content_type:
        parsed_events = []
        data_lines = []
        for line in body.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif not line.strip() and data_lines:
                joined = "\n".join(data_lines)
                try:
                    parsed_events.append(json.loads(joined))
                except Exception:
                    pass
                data_lines = []
        if data_lines:
            try:
                parsed_events.append(json.loads("\n".join(data_lines)))
            except Exception:
                pass
        if parsed_events:
            return parsed_events[-1]
        raise RuntimeError("Canva MCP returned an event stream without a JSON result.")
    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"Canva MCP returned an unexpected response: {body[:500]}") from exc


def _canva_unpack_tool_result(envelope):
    if isinstance(envelope, dict) and envelope.get("error"):
        err = envelope["error"]
        raise RuntimeError(str(err.get("message", err))[:900] if isinstance(err, dict) else str(err)[:900])
    result = envelope.get("result", envelope) if isinstance(envelope, dict) else envelope
    if not isinstance(result, dict):
        return result
    if result.get("isError"):
        messages = [str(item.get("text", "")) for item in result.get("content", []) if isinstance(item, dict)]
        raise RuntimeError(("; ".join(m for m in messages if m) or "Canva tool returned an error.")[:900])
    for key in ("structuredContent", "structured_content"):
        if isinstance(result.get(key), dict):
            return result[key]
    for block in result.get("content", []):
        if not isinstance(block, dict) or not isinstance(block.get("text"), str):
            continue
        text_value = block["text"].strip()
        try:
            parsed = json.loads(text_value)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            continue
    return result


class _CanvaMCPClient:
    """Small Streamable-HTTP MCP client scoped to one Canva image-edit workflow."""
    def __init__(self, token):
        self.token = token
        self.http = requests.Session()
        self.session_id = None
        self.request_id = 0
        self.protocol_version = "2025-03-26"
        self.initialized = False

    def _post(self, payload):
        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        # MCP requires the negotiated protocol version on requests after the
        # initialize handshake even when the server chooses stateless HTTP and
        # does not issue an Mcp-Session-Id. Do not send it on the initial request.
        if self.initialized:
            headers["MCP-Protocol-Version"] = self.protocol_version
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        try:
            response = self.http.post(CANVA_MCP_URL, json=payload, headers=headers, timeout=(15, 90))
        except Exception as exc:
            phase = "initialize request" if not self.initialized else str(payload.get("method", "MCP request"))
            raise RuntimeError(f"Canva MCP {phase} transport failed: {exc}") from exc
        self.session_id = response.headers.get("Mcp-Session-Id") or response.headers.get("MCP-Session-Id") or self.session_id
        try:
            return _canva_parse_mcp_response(response)
        except Exception as exc:
            phase = "initialize request" if not self.initialized else str(payload.get("method", "MCP request"))
            raise RuntimeError(f"Canva MCP {phase} failed: {exc}") from exc

    def initialize(self):
        self.request_id += 1
        init_result = self._post({
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "preet-sports-thumbnail-studio", "version": "1.0.0"},
            },
        })
        server_result = init_result.get("result", {}) if isinstance(init_result, dict) else {}
        accepted_version = server_result.get("protocolVersion")
        if accepted_version:
            self.protocol_version = accepted_version
        self.initialized = True
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call_tool(self, name, arguments):
        self.request_id += 1
        envelope = self._post({
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        return _canva_unpack_tool_result(envelope)


def _canva_mcp_edit_player(
    upload_bytes,
    prompt,
    *,
    aspect_ratio="PORTRAIT_4_5",
    max_edge=1400,
    user_intent="Edit the supplied cricket-player photo to a front-facing pose for the user's cricket thumbnail.",
    remove_magenta=True,
):
    """Upload a reference image to Canva MCP, run one image edit, and retrieve its preview."""
    token, token_error = _canva_valid_access_token()
    if not token:
        return None, token_error
    client = _CanvaMCPClient(token)
    stage = "opening the Canva MCP session"
    try:
        client.initialize()
        stage = "preparing the reference portrait and requesting a Canva upload URL"
        with Image.open(io.BytesIO(upload_bytes)) as opened:
            opened.load()
            source = opened.convert("RGBA")
            if max(source.size) > max_edge:
                scale = float(max_edge) / max(source.size)
                source = source.resize(
                    (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
                    Image.Resampling.LANCZOS,
                )
            upload_buffer = io.BytesIO()
            if source.getchannel("A").getextrema()[0] < 250:
                source.save(upload_buffer, format="PNG", optimize=False, compress_level=2)
                mime = "image/png"
            else:
                source.convert("RGB").save(upload_buffer, format="JPEG", quality=90, optimize=False)
                mime = "image/jpeg"

        upload_info = client.call_tool("create-upload-url", {})
        upload_url = upload_info.get("uploadUrl") or upload_info.get("upload_url")
        if not upload_url:
            raise RuntimeError("Canva did not return an upload URL. Check that asset:write is enabled for the Canva developer app.")
        stage = "uploading the reference portrait to Canva"
        upload_response = requests.post(
            upload_url,
            data=upload_buffer.getvalue(),
            headers={"Content-Type": "application/octet-stream"},
            timeout=(15, 60),
        )
        if upload_response.status_code >= 400:
            raise RuntimeError(f"Canva source-photo upload failed (HTTP {upload_response.status_code}): {upload_response.text[:500]}")
        upload_result = upload_response.json()
        media_id = upload_result.get("mediaId") or upload_result.get("media_id")
        if not media_id:
            raise RuntimeError("Canva accepted the upload but did not return mediaId.")

        stage = "submitting the front-facing pose request to Canva generate-image"
        job_result = client.call_tool(
            "generate-image",
            {
                "prompt": prompt,
                "imageReferences": [{"type": "MEDIA", "id": str(media_id)}],
                "aspectRatio": aspect_ratio,
                "user_intent": str(user_intent)[:255],
            },
        )
        job_id = job_result.get("jobId") or job_result.get("job_id")
        if not job_id and isinstance(job_result.get("job"), dict):
            job_id = job_result["job"].get("id")
        if not job_id:
            raise RuntimeError("Canva did not return an image-edit job ID. No second generation request was sent.")
        stage = "checking the Canva image-generation job"
        deadline = time.time() + 150
        completed_job = None
        while time.time() < deadline:
            time.sleep(2.0)
            status_result = client.call_tool("get-generate-image-job", {"jobId": job_id})
            status = str(status_result.get("status", "")).upper()
            if status in ("SUCCESS", "SUCCEEDED", "COMPLETED"):
                completed_job = status_result
                break
            if status in ("FAILURE", "FAILED", "CANCELED", "CANCELLED"):
                detail = status_result.get("failureMessage") or status_result.get("failure_message") or status_result.get("message") or status
                raise RuntimeError("Canva image edit failed: " + str(detail)[:700])
        if completed_job is None:
            raise RuntimeError("Canva is still processing this edit after 150 seconds. Check Canva before retrying so you don't spend another AI credit unnecessarily.")

        stage = "retrieving the generated portrait from Canva"
        result_obj = completed_job.get("result", {})
        results = result_obj.get("results", []) if isinstance(result_obj, dict) else []
        media_output = next((item for item in results if isinstance(item, dict) and item.get("type") == "MEDIA" and item.get("id")), None)
        if not media_output:
            # Allow a direct generated-image URL if Canva adds one to the response.
            direct_url = None
            if isinstance(result_obj, dict):
                direct_image = result_obj.get("image", {})
                if isinstance(direct_image, dict):
                    direct_url = direct_image.get("url") or direct_image.get("downloadUrl")
            if not direct_url:
                raise RuntimeError("Canva finished but returned no media reference or downloadable image URL.")
            image_response = requests.get(direct_url, timeout=(10, 60))
            image_response.raise_for_status()
            with Image.open(io.BytesIO(image_response.content)) as opened:
                opened.load()
                output_image = opened.convert("RGBA")
        else:
            media_output_id = str(media_output["id"])
            # Canva MCP returns a MEDIA reference. The documented asset endpoint exposes a time-limited thumbnail.
            # Prefer any direct source URL provided by the result; otherwise use that preview and report its resolution.
            asset_data = {}
            try:
                asset_response = requests.get(
                    "https://api.canva.com/rest/v1/assets/" + media_output_id,
                    headers={"Authorization": "Bearer " + token},
                    timeout=(10, 30),
                )
                asset_response.raise_for_status()
                asset_data = asset_response.json().get("asset", {})
            except Exception:
                # Some MCP media references are returned before they behave like regular REST assets.
                # Try Canva MCP's own asset lookup before returning a clear limitation.
                try:
                    asset_lookup = client.call_tool(
                        "get-assets",
                        {
                            "asset_ids": [media_output_id],
                            "user_intent": "Retrieve the preview of the front-facing player image just generated.",
                        },
                    )
                    if isinstance(asset_lookup, list) and asset_lookup:
                        asset_data = asset_lookup[0] if isinstance(asset_lookup[0], dict) else {}
                    elif isinstance(asset_lookup, dict):
                        asset_list = asset_lookup.get("assets") or asset_lookup.get("items") or []
                        if isinstance(asset_list, list) and asset_list and isinstance(asset_list[0], dict):
                            asset_data = asset_list[0].get("asset", asset_list[0])
                        else:
                            asset_data = asset_lookup.get("asset", asset_lookup)
                except Exception:
                    asset_data = {}
            thumbnail = asset_data.get("thumbnail", {}) if isinstance(asset_data, dict) else {}
            preview_url = thumbnail.get("url")
            if not preview_url:
                raise RuntimeError(
                    "Canva created the edited image, but the public API response has no downloadable image URL—only a Canva media reference. "
                    "Open the generated image in Canva and download the original, or use a provider that returns the image file directly."
                )
            image_response = requests.get(preview_url, timeout=(10, 60))
            image_response.raise_for_status()
            with Image.open(io.BytesIO(image_response.content)) as opened:
                opened.load()
                output_image = opened.convert("RGBA")
            w, h = output_image.size
            st.session_state["canva_pose_quality_note"] = (
                f"Canva returned an asset preview at {w} × {h} px, not a verified full-resolution original. "
                "The thumbnail canvas still exports at 3840 × 2160, but this portrait may look softer when enlarged."
            )
        if remove_magenta:
            try:
                output_image = _remove_magenta_chroma_background(output_image)
            except ValueError as exc:
                if output_image.getchannel("A").getextrema()[0] >= 250:
                    raise RuntimeError(str(exc)) from exc
        return output_image, None
    except Exception as exc:
        # Identify the failing stage so a generic upstream HTTP 500 can be separated
        # from OAuth, upload, job polling, or output-download problems. Do not auto-retry
        # generation here, because a server error can occur after a billable job starts.
        return None, f"Canva AI front-pose conversion failed while {stage}: {exc}"


# Process the callback when Canva redirects the browser back into this Streamlit app.
_canva_process_oauth_callback()


CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 2160
RENDER_PIPELINE_VERSION = "preet-sports-4k-v36-flag-outline-grade-labels"
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
    # Australia
    "AUS": "https://flagcdn.com/w320/au.png",
    "AUSTRALIA": "https://flagcdn.com/w320/au.png",
    "AUS WOMEN": "https://flagcdn.com/w320/au.png",
    "AUSTRALIA WOMEN": "https://flagcdn.com/w320/au.png",
    "AUS-W": "https://flagcdn.com/w320/au.png",
    "AUS W": "https://flagcdn.com/w320/au.png",
    # Bangladesh
    "BAN": "https://flagcdn.com/w320/bd.png",
    "BANGLADESH": "https://flagcdn.com/w320/bd.png",
    "BAN WOMEN": "https://flagcdn.com/w320/bd.png",
    "BANGLADESH WOMEN": "https://flagcdn.com/w320/bd.png",
    "BAN-W": "https://flagcdn.com/w320/bd.png",
    "BAN W": "https://flagcdn.com/w320/bd.png",
    # England
    "ENG": "https://flagcdn.com/w320/gb-eng.png",
    "ENGLAND": "https://flagcdn.com/w320/gb-eng.png",
    "ENG WOMEN": "https://flagcdn.com/w320/gb-eng.png",
    "ENGLAND WOMEN": "https://flagcdn.com/w320/gb-eng.png",
    "ENG-W": "https://flagcdn.com/w320/gb-eng.png",
    "ENG W": "https://flagcdn.com/w320/gb-eng.png",
    # India
    "IND": "https://flagcdn.com/w320/in.png",
    "INDIA": "https://flagcdn.com/w320/in.png",
    "IND WOMEN": "https://flagcdn.com/w320/in.png",
    "IND-W": "https://flagcdn.com/w320/in.png",
    "IND W": "https://flagcdn.com/w320/in.png",
    "INDIA WOMEN": "https://flagcdn.com/w320/in.png",
    # Ireland
    "IRE": "https://flagcdn.com/w320/ie.png",
    "IRELAND": "https://flagcdn.com/w320/ie.png",
    "IRE WOMEN": "https://flagcdn.com/w320/ie.png",
    "IRELAND WOMEN": "https://flagcdn.com/w320/ie.png",
    "IRE-W": "https://flagcdn.com/w320/ie.png",
    "IRE W": "https://flagcdn.com/w320/ie.png",
    # New Zealand
    "NZ": "https://flagcdn.com/w320/nz.png",
    "NEW ZEALAND": "https://flagcdn.com/w320/nz.png",
    "NZ WOMEN": "https://flagcdn.com/w320/nz.png",
    "NEW ZEALAND WOMEN": "https://flagcdn.com/w320/nz.png",
    "NZ-W": "https://flagcdn.com/w320/nz.png",
    "NZ W": "https://flagcdn.com/w320/nz.png",
    # Pakistan
    "PAK": "https://flagcdn.com/w320/pk.png",
    "PAKISTAN": "https://flagcdn.com/w320/pk.png",
    "PAK WOMEN": "https://flagcdn.com/w320/pk.png",
    "PAKISTAN WOMEN": "https://flagcdn.com/w320/pk.png",
    "PAK-W": "https://flagcdn.com/w320/pk.png",
    "PAK W": "https://flagcdn.com/w320/pk.png",
    # South Africa
    "SA": "https://flagcdn.com/w320/za.png",
    "RSA": "https://flagcdn.com/w320/za.png",
    "SOUTH AFRICA": "https://flagcdn.com/w320/za.png",
    "SA WOMEN": "https://flagcdn.com/w320/za.png",
    "SOUTH AFRICA WOMEN": "https://flagcdn.com/w320/za.png",
    "SA-W": "https://flagcdn.com/w320/za.png",
    "SA W": "https://flagcdn.com/w320/za.png",
    # Sri Lanka
    "SL": "https://flagcdn.com/w320/lk.png",
    "SRI LANKA": "https://flagcdn.com/w320/lk.png",
    "SL WOMEN": "https://flagcdn.com/w320/lk.png",
    "SRI LANKA WOMEN": "https://flagcdn.com/w320/lk.png",
    "SL-W": "https://flagcdn.com/w320/lk.png",
    "SL W": "https://flagcdn.com/w320/lk.png",
    # West Indies uses the cricket-team flag/logo rather than an individual country flag.
    "WI": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "WEST INDIES": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "WEST INDIES WOMEN": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "WI WOMEN": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "WI-W": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    "WI W": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Flag_of_the_West_Indies_cricket_team.svg/320px-Flag_of_the_West_Indies_cricket_team.svg.png",
    # Zimbabwe
    "ZIM": "https://flagcdn.com/w320/zw.png",
    "ZIMBABWE": "https://flagcdn.com/w320/zw.png",
    "ZIM-W": "https://flagcdn.com/w320/zw.png",
    "ZIM W": "https://flagcdn.com/w320/zw.png",
    "ZIM WOMEN": "https://flagcdn.com/w320/zw.png",
    "ZIMBABWE WOMEN": "https://flagcdn.com/w320/zw.png",
    # Current / recent ICC Women's World Cup teams and common associate sides.
    "NED": "https://flagcdn.com/w320/nl.png",
    "NETHERLANDS": "https://flagcdn.com/w320/nl.png",
    "NED WOMEN": "https://flagcdn.com/w320/nl.png",
    "NETHERLANDS WOMEN": "https://flagcdn.com/w320/nl.png",
    "NED-W": "https://flagcdn.com/w320/nl.png",
    "NED W": "https://flagcdn.com/w320/nl.png",
    "SCOT": "https://flagcdn.com/w320/gb-sct.png",
    "SCOTLAND": "https://flagcdn.com/w320/gb-sct.png",
    "SCOT WOMEN": "https://flagcdn.com/w320/gb-sct.png",
    "SCOTLAND WOMEN": "https://flagcdn.com/w320/gb-sct.png",
    "SCOT-W": "https://flagcdn.com/w320/gb-sct.png",
    "SCOT W": "https://flagcdn.com/w320/gb-sct.png",
    "THA": "https://flagcdn.com/w320/th.png",
    "THAILAND": "https://flagcdn.com/w320/th.png",
    "THA WOMEN": "https://flagcdn.com/w320/th.png",
    "THAILAND WOMEN": "https://flagcdn.com/w320/th.png",
    "THA-W": "https://flagcdn.com/w320/th.png",
    "PNG": "https://flagcdn.com/w320/pg.png",
    "PAPUA NEW GUINEA": "https://flagcdn.com/w320/pg.png",
    "PNG WOMEN": "https://flagcdn.com/w320/pg.png",
    "PNG-W": "https://flagcdn.com/w320/pg.png",
    "USA": "https://flagcdn.com/w320/us.png",
    "USA WOMEN": "https://flagcdn.com/w320/us.png",
    "USA-W": "https://flagcdn.com/w320/us.png",
    "UAE": "https://flagcdn.com/w320/ae.png",
    "UNITED ARAB EMIRATES": "https://flagcdn.com/w320/ae.png",
    "UAE WOMEN": "https://flagcdn.com/w320/ae.png",
    "NEP": "https://flagcdn.com/w320/np.png",
    "NEPAL": "https://flagcdn.com/w320/np.png",
    "NEP WOMEN": "https://flagcdn.com/w320/np.png",
    "NAM": "https://flagcdn.com/w320/na.png",
    "NAMIBIA": "https://flagcdn.com/w320/na.png",
    "NAM WOMEN": "https://flagcdn.com/w320/na.png",
    "UGA": "https://flagcdn.com/w320/ug.png",
    "UGANDA": "https://flagcdn.com/w320/ug.png",
    "UGA WOMEN": "https://flagcdn.com/w320/ug.png",
    "HKG": "https://flagcdn.com/w320/hk.png",
    "HONG KONG": "https://flagcdn.com/w320/hk.png",
    "HKG WOMEN": "https://flagcdn.com/w320/hk.png",
    "TAN": "https://flagcdn.com/w320/tz.png",
    "TANZANIA": "https://flagcdn.com/w320/tz.png",
    "NIG": "https://flagcdn.com/w320/ng.png",
    "NIGERIA": "https://flagcdn.com/w320/ng.png",
    "RWA": "https://flagcdn.com/w320/rw.png",
    "RWANDA": "https://flagcdn.com/w320/rw.png",
    "KEN": "https://flagcdn.com/w320/ke.png",
    "KENYA": "https://flagcdn.com/w320/ke.png",
    "GER": "https://flagcdn.com/w320/de.png",
    "GERMANY": "https://flagcdn.com/w320/de.png",
    "ITA": "https://flagcdn.com/w320/it.png",
    "ITALY": "https://flagcdn.com/w320/it.png",
    "JPN": "https://flagcdn.com/w320/jp.png",
    "JAPAN": "https://flagcdn.com/w320/jp.png",
    "VAN": "https://flagcdn.com/w320/vu.png",
    "VANUATU": "https://flagcdn.com/w320/vu.png",
    "SAM": "https://flagcdn.com/w320/ws.png",
    "SAMOA": "https://flagcdn.com/w320/ws.png",
    "KUW": "https://flagcdn.com/w320/kw.png",
    "KUWAIT": "https://flagcdn.com/w320/kw.png",
    # Men's aliases kept for compatibility.
    "AFG": "https://flagcdn.com/w320/af.png",
    "AFGHANISTAN": "https://flagcdn.com/w320/af.png",
    "NEP": "https://flagcdn.com/w320/np.png",
    "NEPAL": "https://flagcdn.com/w320/np.png",
    "OMAN": "https://flagcdn.com/w320/om.png",
    "NED": "https://flagcdn.com/w320/nl.png",
}

# Historical fallback photos are used only if no URL image has been fetched.
# For best results, paste match-specific, high-resolution, transparent player PNG/WebP URLs.
CAPTAIN_DATABASE = {
    "IND": {
        "name": "Shreyas Iyer",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/63961.png",
    },
    "INDIA": {
        "name": "Shreyas Iyer",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/63961.png",
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
    # ICC women's player profile fallback supplied by the user (Sophie Molineux, ICC ID 67041).
    # The same profile resolver can fetch any other ICC player's image from their profile URL.
    "AUS-W": {
        "name": "Sophie Molineux",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/67041.png",
    },
    "AUS W": {
        "name": "Sophie Molineux",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/67041.png",
    },
    "AUS WOMEN": {
        "name": "Sophie Molineux",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/67041.png",
    },
    "AUSTRALIA WOMEN": {
        "name": "Sophie Molineux",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/67041.png",
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
        "name": "Mitchell Santner",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/57903.png",
    },
    "IND-W": {
        "name": "Smriti Mandhana",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/63992.png",
    },
    "IND W": {
        "name": "Smriti Mandhana",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/63992.png",
    },
    "IND WOMEN": {
        "name": "Smriti Mandhana",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/63992.png",
    },
    "INDIA WOMEN": {
        "name": "Smriti Mandhana",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/63992.png",
    },
    "NZ-W": {
        "name": "Amelia Kerr",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/66632.png",
    },
    "NZ W": {
        "name": "Amelia Kerr",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/66632.png",
    },
    "NEW ZEALAND WOMEN": {
        "name": "Amelia Kerr",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/66632.png",
    },
    "BAN-W": {
        "name": "Nahida Akter",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/65721.png",
    },
    "BAN W": {
        "name": "Nahida Akter",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/65721.png",
    },
    "BAN WOMEN": {
        "name": "Nahida Akter",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/65721.png",
    },
    "BANGLADESH WOMEN": {
        "name": "Nahida Akter",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/65721.png",
    },
    "ZIM-W": {
        "name": "Josephine Nkomo",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/67315.png",
    },
    "ZIM W": {
        "name": "Josephine Nkomo",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/67315.png",
    },
    "ZIM WOMEN": {
        "name": "Josephine Nkomo",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/67315.png",
    },
    "ZIMBABWE WOMEN": {
        "name": "Josephine Nkomo",
        "player_png": "https://images.icc-cricket.com/image/upload/t_player-headshot-portrait-lg-webp/prd/assets/players/generic/colored/67315.png",
    },
}


def normalize_team_name(team_name):
    """Normalize team labels to make flag lookups work for e.g. AUS WOMEN."""
    return re.sub(r"\s+", " ", str(team_name or "").strip().upper().replace("_", " "))


def normalize_team_base(team_name):
    """Normalize common women/men team labels to their base team label."""
    key = normalize_team_name(team_name)
    key = re.sub(r"(?:\s+WOMEN|\s+WOMENS|\s+WOMAN|[-_\s]+W)$", "", key)
    key = re.sub(r"[-_\s]+MEN$", "", key)
    return key.strip()


# Official ICC player-profile URLs used when the user enters team names without URLs.
# Captaincy varies by format, so profiles are selected using the Match Format / Badge field.
ICC_TEAM_CAPTAIN_PROFILES = {
    "IND": {
        "T20": "https://www.icc-cricket.com/rankings/63961/shreyas-iyer",
        "ODI": "https://www.icc-cricket.com/rankings/66818/shubman-gill",
        "TEST": "https://www.icc-cricket.com/rankings/66818/shubman-gill",
        "DEFAULT": "https://www.icc-cricket.com/rankings/63961/shreyas-iyer",
    },
    "NZ": {
        "T20": "https://www.icc-cricket.com/rankings/57903/mitchell-santner",
        "ODI": "https://www.icc-cricket.com/rankings/57903/mitchell-santner",
        "DEFAULT": "https://www.icc-cricket.com/rankings/57903/mitchell-santner",
    },
    "AUS": {
        "T20": "https://www.icc-cricket.com/rankings/10094/mitchell-marsh",
        "ODI": "https://www.icc-cricket.com/rankings/56964/pat-cummins",
        "TEST": "https://www.icc-cricket.com/rankings/56964/pat-cummins",
        "DEFAULT": "https://www.icc-cricket.com/rankings/10094/mitchell-marsh",
    },
    "ENG": {
        "T20": "https://www.icc-cricket.com/rankings/66374/harry-brook",
        "ODI": "https://www.icc-cricket.com/rankings/66374/harry-brook",
        "DEFAULT": "https://www.icc-cricket.com/rankings/66374/harry-brook",
    },
    "WI": {
        "T20": "https://www.icc-cricket.com/rankings/63797/shai-hope",
        "ODI": "https://www.icc-cricket.com/rankings/63797/shai-hope",
        "DEFAULT": "https://www.icc-cricket.com/rankings/63797/shai-hope",
    },
    "SA": {
        "T20": "https://www.icc-cricket.com/rankings/64219/aiden-markram",
        "DEFAULT": "https://www.icc-cricket.com/rankings/64219/aiden-markram",
    },
    "IND-W": {
        "T20": "https://www.icc-cricket.com/rankings/63992/smriti-mandhana",
        "ODI": "https://www.icc-cricket.com/rankings/63992/smriti-mandhana",
        "TEST": "https://www.icc-cricket.com/rankings/63992/smriti-mandhana",
        "DEFAULT": "https://www.icc-cricket.com/rankings/63992/smriti-mandhana",
    },
    "NZ-W": {
        "T20": "https://www.icc-cricket.com/rankings/66632/amelia-kerr",
        "ODI": "https://www.icc-cricket.com/rankings/66632/amelia-kerr",
        "DEFAULT": "https://www.icc-cricket.com/rankings/66632/amelia-kerr",
    },
    "AUS-W": {
        "T20": "https://www.icc-cricket.com/rankings/67041/sophie-molineux",
        "ODI": "https://www.icc-cricket.com/rankings/67041/sophie-molineux",
        "DEFAULT": "https://www.icc-cricket.com/rankings/67041/sophie-molineux",
    },
    "ENG-W": {
        "T20": "https://www.icc-cricket.com/rankings/63998/nat-sciver-brunt",
        "ODI": "https://www.icc-cricket.com/rankings/63998/nat-sciver-brunt",
        "DEFAULT": "https://www.icc-cricket.com/rankings/63998/nat-sciver-brunt",
    },
    "SA-W": {
        "T20": "https://www.icc-cricket.com/rankings/66176/laura-wolvaardt",
        "ODI": "https://www.icc-cricket.com/rankings/66176/laura-wolvaardt",
        "DEFAULT": "https://www.icc-cricket.com/rankings/66176/laura-wolvaardt",
    },
    "BAN-W": {
        "ODI": "https://www.icc-cricket.com/rankings/65720/nigar-sultana",
        "T20": "https://www.icc-cricket.com/rankings/65721/nahida-akter",
        "DEFAULT": "https://www.icc-cricket.com/rankings/65720/nigar-sultana",
    },
    "PAK-W": {
        "T20": "https://www.icc-cricket.com/rankings/71759/fatima-sana",
        "ODI": "https://www.icc-cricket.com/rankings/71759/fatima-sana",
        "DEFAULT": "https://www.icc-cricket.com/rankings/71759/fatima-sana",
    },
    "ZIM-W": {
        "T20": "https://www.icc-cricket.com/rankings/67315/josephine-nkomo",
        "ODI": "https://www.icc-cricket.com/rankings/67315/josephine-nkomo",
        "DEFAULT": "https://www.icc-cricket.com/rankings/67315/josephine-nkomo",
    },
}


def get_icc_team_captain_profile_url(team_name, match_format="T20"):
    """Choose a known ICC player profile for the entered team and format."""
    raw = normalize_team_name(team_name)
    if not raw:
        return None
    is_women = bool(re.search(r"(?:\bWOMEN\b|\bWOMENS\b|\bWOMAN\b|[-_\s]W$)", raw))
    base = normalize_team_base(raw)
    aliases = {
        "INDIA": "IND",
        "NEW ZEALAND": "NZ",
        "AUSTRALIA": "AUS",
        "ENGLAND": "ENG",
        "WEST INDIES": "WI",
        "SOUTH AFRICA": "SA",
        "BANGLADESH": "BAN",
        "PAKISTAN": "PAK",
        "SRI LANKA": "SL",
        "ZIMBABWE": "ZIM",
    }
    code = aliases.get(base, base) + ("-W" if is_women else "")
    badge = normalize_team_name(match_format)
    if "T20" in badge:
        fmt = "T20"
    elif "ODI" in badge or "ONE DAY" in badge:
        fmt = "ODI"
    elif "TEST" in badge:
        fmt = "TEST"
    else:
        fmt = "DEFAULT"
    profiles = ICC_TEAM_CAPTAIN_PROFILES.get(code, {})
    if fmt == "DEFAULT":
        return profiles.get("DEFAULT") or profiles.get("T20")
    # Don't reuse a different format's captain when this format has no mapped profile.
    return profiles.get(fmt)


def get_team_flag_url(team_name):
    """Return the country/team flag for men's and women's naming variants."""
    key = normalize_team_name(team_name)
    if key in TEAM_FLAG_DATABASE:
        return TEAM_FLAG_DATABASE[key]
    base = normalize_team_base(key)
    if base in TEAM_FLAG_DATABASE:
        return TEAM_FLAG_DATABASE[base]
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


@st.cache_resource(show_spinner=False)
def _get_local_rembg_session(model_name="u2netp"):
    """Load the lightweight local segmentation model once per running app process."""
    model_home = (
        os.environ.get("PREET_REMBG_HOME")
        or os.environ.get("U2NET_HOME")
        or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".preet_models", "u2net")
    )
    os.makedirs(model_home, exist_ok=True)
    os.environ["U2NET_HOME"] = model_home
    from rembg import new_session
    return new_session(model_name)


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 30, max_entries=64)
def _fast_local_cutout_cached(source_bytes, algorithm_version="cached-u2netp-512-opencv-v6"):

    """Create a local transparent cutout using cached U2NETP if preloaded, else OpenCV.

    No hosted API is called, and model weights are never downloaded during a user request.
    """
    import cv2

    try:
        cv2.setNumThreads(1)
    except Exception:
        pass

    with Image.open(io.BytesIO(source_bytes)) as opened:
        opened.load()
        source = opened.convert("RGB")

    # Limit intermediate memory on small Render instances.
    max_output_side = 1800
    if max(source.size) > max_output_side:
        scale_out = max_output_side / float(max(source.size))
        source = source.resize(
            (max(1, round(source.width * scale_out)), max(1, round(source.height * scale_out))),
            Image.Resampling.LANCZOS,
        )

    original_size = source.size

    # Use local U2NETP only if its weights already exist on disk. Never download model
    # weights during a user request: on small Render instances that caused long waits and
    # HTTP 502 errors. If preloaded weights are missing or inference fails, use OpenCV.
    model_name = os.environ.get("REMBG_MODEL", "u2netp").strip() or "u2netp"
    model_home = (
        os.environ.get("PREET_REMBG_HOME")
        or os.environ.get("U2NET_HOME")
        or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".preet_models", "u2net")
    )
    weights_exist = os.path.isfile(os.path.join(model_home, f"{model_name}.onnx"))
    use_rembg = os.environ.get("PREET_ENABLE_REMBG", "1").strip().lower() not in {"0", "false", "no", "off"}
    if use_rembg and weights_exist:
        try:
            # U2NETP at 512px is a practical accuracy/speed compromise for Render CPU.
            model_side = max(384, min(512, int(os.environ.get("PREET_REMBG_MAX_SIDE", "512"))))
            model_input = source
            if max(model_input.size) > model_side:
                model_scale = model_side / float(max(model_input.size))
                model_input = model_input.resize(
                    (max(1, round(model_input.width * model_scale)), max(1, round(model_input.height * model_scale))),
                    Image.Resampling.LANCZOS,
                )
            model_buffer = io.BytesIO()
            model_input.save(model_buffer, format="PNG", optimize=False)
            from rembg import remove as rembg_remove
            local_session = _get_local_rembg_session(model_name)
            rembg_result_bytes = rembg_remove(
                model_buffer.getvalue(), session=local_session, alpha_matting=False, post_process_mask=True
            )
            with Image.open(io.BytesIO(rembg_result_bytes)) as rembg_opened:
                rembg_result = rembg_opened.convert("RGBA")
            if rembg_result.size != original_size:
                rembg_result = rembg_result.resize(original_size, Image.Resampling.LANCZOS)
            rembg_alpha = rembg_result.getchannel("A")
            transparent_fraction = float(np.asarray(rembg_alpha, dtype=np.uint8).__lt__(250).mean())
            if rembg_alpha.getextrema()[0] < 250 and 0.005 < transparent_fraction < 0.97:
                alpha_bounds = rembg_alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
                if alpha_bounds:
                    l, t, r, b = alpha_bounds
                    pad = max(3, int(max(rembg_result.size) * 0.008))
                    rembg_result = rembg_result.crop((
                        max(0, l - pad), max(0, t - pad),
                        min(rembg_result.width, r + pad), min(rembg_result.height, b + pad),
                    ))
                rembg_buffer = io.BytesIO()
                rembg_result.save(rembg_buffer, format="PNG", optimize=False, compress_level=1)
                return rembg_buffer.getvalue()
        except Exception:
            # Any model/inference failure falls through to OpenCV; don't block the app.
            pass

    max_segmentation_side = int(os.environ.get("PREET_GRABCUT_MAX_SIDE", "512"))
    max_segmentation_side = max(320, min(max_segmentation_side, 640))
    scale = min(1.0, max_segmentation_side / float(max(source.size)))
    small = source if scale >= 1.0 else source.resize(
        (max(1, round(source.width * scale)), max(1, round(source.height * scale))),
        Image.Resampling.LANCZOS,
    )

    rgb = np.asarray(small, dtype=np.uint8)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    if width < 40 or height < 40:
        raise ValueError("Image crop is too small. Use a player crop at least 40 × 40 pixels.")

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    face = None
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
        detector = cv2.CascadeClassifier(cascade_path)
        if not detector.empty():
            detected = detector.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=4,
                minSize=(max(32, int(width * 0.11)), max(32, int(height * 0.11))),
            )
            if len(detected):
                # Cropped player images normally have one large face; small flag/logo
                # detections are discarded in favor of the largest plausible face.
                plausible = [tuple(map(int, f)) for f in detected if f[2] >= width * 0.16 and f[3] >= height * 0.12]
                if plausible:
                    face = max(plausible, key=lambda f: f[2] * f[3])
    except Exception:
        face = None

    mask = np.full((height, width), cv2.GC_BGD, dtype=np.uint8)

    if face is not None:
        fx, fy, fw, fh = face
        cx = fx + fw / 2.0
        # Portrait silhouette: tightly follows the head/face and expands down into
        # shoulders/torso. The areas outside this polygon are definite background, so
        # flags and colored panels at the top corners cannot become part of the cutout.
        def clipx(value):
            return int(max(0, min(width - 1, round(value))))

        def clipy(value):
            return int(max(0, min(height - 1, round(value))))

        top = max(0, int(fy - 0.42 * fh))
        points = np.array([
            [clipx(cx - 0.36 * fw), clipy(top)],
            [clipx(cx + 0.36 * fw), clipy(top)],
            [clipx(fx + 0.98 * fw), clipy(fy - 0.04 * fh)],
            [clipx(fx + 1.03 * fw), clipy(fy + 0.25 * fh)],
            [clipx(fx + 1.03 * fw), clipy(fy + 0.70 * fh)],
            [clipx(fx + 1.10 * fw), clipy(fy + 0.95 * fh)],
            [clipx(cx + 0.88 * fw), clipy(fy + 1.15 * fh)],
            [clipx(cx + 1.30 * fw), clipy(fy + 1.38 * fh)],
            [width - 1, clipy(fy + 1.48 * fh)],
            [width - 1, height - 1],
            [0, height - 1],
            [0, clipy(fy + 1.48 * fh)],
            [clipx(cx - 1.30 * fw), clipy(fy + 1.38 * fh)],
            [clipx(cx - 0.88 * fw), clipy(fy + 1.15 * fh)],
            [clipx(fx - 0.10 * fw), clipy(fy + 0.95 * fh)],
            [clipx(fx - 0.04 * fw), clipy(fy + 0.70 * fh)],
            [clipx(fx - 0.04 * fw), clipy(fy + 0.25 * fh)],
            [clipx(fx + 0.02 * fw), clipy(fy - 0.04 * fh)],
        ], dtype=np.int32)
        cv2.fillPoly(mask, [points], cv2.GC_PR_FGD)

        # Sure-foreground seeds inside the face and central jersey. These help GrabCut
        # learn the player colors while keeping outside panels as hard background.
        face_center = (clipx(cx), clipy(fy + 0.56 * fh))
        cv2.ellipse(
            mask,
            face_center,
            (max(5, int(fw * 0.33)), max(5, int(fh * 0.42))),
            0, 0, 360, cv2.GC_FGD, -1,
        )
        torso_top = clipy(fy + 0.96 * fh)
        torso_left = clipx(cx - 0.22 * fw)
        torso_right = clipx(cx + 0.22 * fw)
        if torso_top < height - 2:
            cv2.rectangle(mask, (torso_left, torso_top), (torso_right, height - 1), cv2.GC_FGD, -1)
    else:
        # Fallback for non-portrait images such as products, pets, or a missed face.
        margin_x = max(2, int(width * 0.035))
        margin_y = max(2, int(height * 0.025))
        rect = (margin_x, margin_y, max(1, width - 2 * margin_x), max(1, height - 2 * margin_y))
        cv2.grabCut(bgr, mask, rect, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 3, cv2.GC_INIT_WITH_RECT)

    bg_model = np.zeros((1, 65), dtype=np.float64)
    fg_model = np.zeros((1, 65), dtype=np.float64)
    cv2.grabCut(bgr, mask, None, bg_model, fg_model, 4 if face is not None else 1, cv2.GC_INIT_WITH_MASK if face is not None else cv2.GC_EVAL)

    alpha_small = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
    ).astype(np.uint8)
    if face is not None:
        # Keep only the foreground component connected to the detected face.
        count, labels, stats, _ = cv2.connectedComponentsWithStats((alpha_small > 0).astype(np.uint8), 8)
        fx, fy, fw, fh = face
        seed_x = max(0, min(width - 1, int(fx + fw / 2)))
        seed_y = max(0, min(height - 1, int(fy + fh * 0.56)))
        component_id = int(labels[seed_y, seed_x])
        if component_id > 0:
            alpha_small = np.where(labels == component_id, 255, 0).astype(np.uint8)

    # Remove small specks and smooth only the mask edge. Keep genuine semi-transparent
    # pixels at the edge so hair and jersey contours don't look like hard stickers.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    alpha_small = cv2.morphologyEx(alpha_small, cv2.MORPH_CLOSE, kernel, iterations=1)
    foreground_fraction = float(np.count_nonzero(alpha_small)) / float(alpha_small.size)
    if foreground_fraction < 0.04 or foreground_fraction > 0.98:
        raise ValueError(
            "The player mask was not reliable. Crop closer around one player, include the complete head/shoulders, and exclude the neighboring flag or graphics."
        )

    alpha = Image.fromarray(alpha_small, mode="L")
    if original_size != alpha.size:
        alpha = alpha.resize(original_size, Image.Resampling.LANCZOS)
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.45))
    result = source.convert("RGBA")
    result.putalpha(alpha)

    bbox = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
    if not bbox:
        raise ValueError("No foreground pixels were detected in this crop.")
    left, top, right, bottom = bbox
    padding = max(3, int(max(result.size) * 0.008))
    result = result.crop((
        max(0, left - padding), max(0, top - padding),
        min(result.width, right + padding), min(result.height, bottom + padding),
    ))

    output = io.BytesIO()
    result.save(output, format="PNG", optimize=False, compress_level=1)
    return output.getvalue()

def remove_background_from_any_image(upload_bytes, filename="image", subject_instruction=None):
    """Remove background locally with cached U2NETP when preloaded, else OpenCV GrabCut.

    No hosted API is called. Model weights are never downloaded during an app interaction.
    """
    try:
        with Image.open(io.BytesIO(upload_bytes)) as opened:
            opened.load()
            source = opened.convert("RGBA")
            # If the input already has meaningful transparency, retain it and avoid segmentation.
            alpha = source.getchannel("A")
            if alpha.getextrema()[0] < 250:
                bbox = alpha.getbbox()
                if bbox:
                    source = source.crop(bbox)
                return source, None

            # Limit cache input size to reduce memory; output cutout keeps up to 1800px detail.
            rgb = source.convert("RGB")
            max_source_side = 1800
            if max(rgb.size) > max_source_side:
                scale = max_source_side / float(max(rgb.size))
                rgb = rgb.resize(
                    (max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale))),
                    Image.Resampling.LANCZOS,
                )
            normalized = io.BytesIO()
            rgb.save(normalized, format="JPEG", quality=90, optimize=False)
            normalized_bytes = normalized.getvalue()
    except Exception as exc:
        return None, f"Could not read the uploaded image: {exc}"

    try:
        result_bytes = _fast_local_cutout_cached(normalized_bytes, "cached-u2netp-512-opencv-v6")
        with Image.open(io.BytesIO(result_bytes)) as output_image:
            output_image.load()
            result = output_image.convert("RGBA")
        alpha_extrema = result.getchannel("A").getextrema()
        if alpha_extrema == (255, 255):
            return None, "No transparent foreground was created. Try adjusting the crop around the player."
        return result, None
    except Exception as exc:
        return None, (
            f"Fast local background removal failed: {exc}. Make the crop include the full player and a small border of background, then retry."
        )

def convert_player_to_front_facing(upload_bytes, filename, side):
    """Use Canva MCP when connected, otherwise Replicate Qwen Image Edit Plus when configured."""
    side_label = "left" if side == "left" else "right"
    prompt = (
        "Edit the provided reference photo, do not create a different person. Turn this same real cricket player "
        "to face directly toward the camera, with both eyes visible and shoulders nearly square. Preserve identity "
        "as closely as possible: face shape, eye spacing, nose, lips, jaw, skin tone, age, hairline, hairstyle, "
        "expression, body build, and exact cricket jersey colours and visible details. Keep realistic photographic "
        "skin texture. Do not beautify or replace the person. Do not add text, flags, logos, watermarks, props, "
        "or extra people. Show the full head, both ears where anatomically visible, shoulders, and upper torso with "
        "generous margin; do not crop hair or shoulders. Use a flat pure magenta (#FF00FF) background edge-to-edge, "
        "without gradient or shadow, so the app can remove it locally. Portrait for the " + side_label +
        " side of a cricket YouTube thumbnail."
    )

    # Prefer Canva's reference-image edit when the user has connected their Canva account.
    # This launches one Canva image-generation job per click and consumes applicable Canva AI credits.
    if str(st.session_state.get("canva_access_token", "") or "").strip():
        return _canva_mcp_edit_player(upload_bytes, prompt)

    # Hosted reference-image editing. No API request is sent until the user clicks Convert.
    # Replicate currently lists Qwen Image Edit Plus at about US$0.03 per output image.
    replicate_token = str(os.environ.get("REPLICATE_API_TOKEN", "")).strip()
    if replicate_token:
        try:
            with Image.open(io.BytesIO(upload_bytes)) as opened:
                opened.load()
                source = opened.convert("RGBA")
                if max(source.size) > 1400:
                    scale = 1400 / float(max(source.size))
                    source = source.resize((max(1, int(source.width * scale)), max(1, int(source.height * scale))), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                if source.getchannel("A").getextrema()[0] < 250:
                    source.save(buf, format="PNG", optimize=False)
                    mime = "image/png"
                else:
                    source.convert("RGB").save(buf, format="JPEG", quality=90, optimize=False)
                    mime = "image/jpeg"
            data_uri = "data:" + mime + ";base64," + base64.b64encode(buf.getvalue()).decode("ascii")
            headers = {
                "Authorization": "Bearer " + replicate_token,
                "Content-Type": "application/json",
                "Prefer": "wait=60",
            }
            response = requests.post(
                "https://api.replicate.com/v1/models/qwen/qwen-image-edit-plus/predictions",
                headers=headers,
                json={"input": {
                    "image": [data_uri],
                    "prompt": prompt,
                    "go_fast": True,
                    "aspect_ratio": "match_input_image",
                    "output_format": "png",
                    "output_quality": 95,
                }},
                timeout=(15, 120),
            )
            if response.status_code >= 400:
                return None, (
                    f"Replicate image edit failed (HTTP {response.status_code}): {response.text[:700]}. "
                    "Check the REPLICATE_API_TOKEN secret and your Replicate billing/credits."
                )
            prediction = response.json()
            poll_url = prediction.get("urls", {}).get("get")
            time_module = __import__("time")
            deadline = time_module.time() + 240
            while prediction.get("status") not in ("succeeded", "failed", "canceled"):
                if not poll_url or time_module.time() >= deadline:
                    return None, "The hosted image edit is still processing or timed out. Try again in a moment."
                time_module.sleep(2)
                poll_response = requests.get(poll_url, headers={"Authorization": "Bearer " + replicate_token}, timeout=(10, 30))
                poll_response.raise_for_status()
                prediction = poll_response.json()
            if prediction.get("status") != "succeeded":
                return None, "Replicate image edit did not complete: " + str(prediction.get("error") or prediction.get("status"))
            outputs = prediction.get("output") or []
            output_url = outputs[0] if isinstance(outputs, list) and outputs else outputs if isinstance(outputs, str) else None
            if not output_url:
                return None, "Replicate completed but returned no output image."
            image_response = requests.get(output_url, timeout=(10, 60))
            image_response.raise_for_status()
            with Image.open(io.BytesIO(image_response.content)) as edited:
                edited.load()
                return edited.convert("RGBA"), None
        except Exception as exc:
            return None, f"Hosted image edit error: {exc}"

    return None, (
        "Front-facing conversion requires Canva to be connected or REPLICATE_API_TOKEN to be configured. "
        "The original portrait and 4K thumbnail workflow remain available without pose conversion."
    )

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
        player_id_match = re.search(r"/(?:rankings|players|player|profile)/(\d+)(?:/|$)", parsed.path, re.I)
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


def fetch_icc_player_image(profile_url, attempts=3):
    """Fetch official ICC profile portraits with retries and longer timeouts.

    Intentionally not cached on failure: the general image fetcher caches None for 24 hours,
    which can make a temporary ICC/CDN timeout look permanent until the cache expires.
    Returns (PIL image or None, short error reason or None).
    """
    image_url = resolve_player_image_url(profile_url)
    if not image_url or not image_url.startswith(("http://", "https://")):
        return None, "invalid profile/image URL"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://www.icc-cricket.com/",
    }
    last_error = "unknown download error"
    import time
    for attempt in range(max(1, int(attempts))):
        response = None
        try:
            response = requests.get(image_url, headers=headers, timeout=(5, 15))
            if response.status_code in (408, 429) or response.status_code >= 500:
                last_error = f"temporary HTTP {response.status_code}"
                if attempt + 1 < attempts:
                    time.sleep(0.6 * (attempt + 1))
                    continue
            response.raise_for_status()
            payload = response.content
            if not payload or len(payload) > 30 * 1024 * 1024:
                return None, "empty or unusually large image response"
            with Image.open(io.BytesIO(payload)) as opened:
                opened.load()
                image = opened.convert("RGBA")
            if image.width < 80 or image.height < 80:
                return None, "downloaded image is unexpectedly small"
            return image, None
        except requests.Timeout:
            last_error = "request timed out"
        except requests.HTTPError:
            last_error = f"HTTP {response.status_code}" if response is not None else "HTTP error"
        except requests.RequestException as exc:
            last_error = f"network error ({type(exc).__name__})"
        except Exception as exc:
            last_error = f"invalid image response ({type(exc).__name__})"
            # Image decoding failures are unlikely to be fixed by another network retry.
            if response is not None and response.content:
                return None, last_error
        if attempt + 1 < attempts:
            time.sleep(0.6 * (attempt + 1))
    return None, last_error


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



@st.cache_data(show_spinner=False, ttl=1800, max_entries=64)
def fetch_from_icc_match_url(url):
    """Resolve captain photo profiles from an ICC match URL.

    The supplied ICC match page (274145) is mapped to its official captain profiles as a
    resilient fallback because the ICC match page's client-rendered squad payload is not
    always exposed to simple HTTP clients. Other ICC pages are inspected for squad JSON.
    """
    parsed = urlsplit(str(url or "").strip())
    if "icc-cricket.com" not in (parsed.netloc or "").lower() or not parsed.path.startswith("/matches/"):
        return None, "Paste an ICC match URL such as https://www.icc-cricket.com/matches/274145/pakistan-vs-england."

    match_id = None
    match = re.search(r"/matches/(\d+)(?:/|$)", parsed.path, flags=re.IGNORECASE)
    if match:
        match_id = match.group(1)

    # Verified from the official ICC page for this exact supplied match:
    # England — Harry Brook (c); Pakistan — Shaheen Afridi (c).
    known_icc_matches = {
        "274145": [
            {
                "name": "England", "code": "ENG", "captain": "Harry Brook",
                "img_url": "https://www.icc-cricket.com/rankings/66374/harry-brook", "match_badge": "4th ODI",
            },
            {
                "name": "Pakistan", "code": "PAK", "captain": "Shaheen Afridi",
                "img_url": "https://www.icc-cricket.com/rankings/66833/shaheen-afridi/", "match_badge": "4th ODI",
            },
        ],
    }
    if match_id in known_icc_matches:
        return known_icc_matches[match_id], None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def walk_json(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk_json(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk_json(child)

    def team_record_from_json(team):
        if not isinstance(team, dict):
            return None
        team_obj = team.get("team") if isinstance(team.get("team"), dict) else team
        team_name = team_obj.get("name") or team_obj.get("displayName") or team.get("teamName")
        roster = None
        for roster_key in ("players", "squad", "members", "lineup", "squadMembers"):
            if isinstance(team.get(roster_key), list):
                roster = team[roster_key]
                break
        if not team_name or not roster:
            return None

        captain_name = None
        captain_obj = None
        for record in roster:
            if not isinstance(record, dict):
                continue
            player_obj = record.get("player") if isinstance(record.get("player"), dict) else record
            player_name = str(player_obj.get("name") or player_obj.get("fullName") or player_obj.get("displayName") or "")
            marker = (
                record.get("isCaptain") is True
                or player_obj.get("isCaptain") is True
                or player_obj.get("captain") is True
                or re.search(r"\(\s*c\s*\)", player_name, re.I)
                or "captain" in str(player_obj.get("role", "")).lower()
            )
            if marker:
                captain_obj = player_obj
                captain_name = re.sub(r"\s*\(\s*c\s*\)\s*", "", player_name, flags=re.I).strip()
                break
        if not captain_obj:
            explicit_captain = team.get("captain") or team_obj.get("captain")
            if isinstance(explicit_captain, dict):
                captain_obj = explicit_captain.get("player") if isinstance(explicit_captain.get("player"), dict) else explicit_captain
                captain_name = str(captain_obj.get("name") or captain_obj.get("fullName") or "").strip()
        if not captain_obj:
            return None
        image_url = _player_image_from_object(captain_obj)
        if not image_url:
            for key in ("profileUrl", "playerUrl", "url", "href", "link"):
                possible = captain_obj.get(key)
                if isinstance(possible, str) and re.search(r"icc-cricket\.com/(?:rankings|players|player|profile)/\d+", possible, re.I):
                    image_url = possible
                    break
        if not image_url:
            return None
        return {
            "name": str(team_name),
            "code": str(team_obj.get("abbreviation") or team_obj.get("shortName") or team.get("code") or re.sub(r"[^A-Za-z]", "", str(team_name))[:3]).upper(),
            "captain": captain_name or "Captain",
            "img_url": urljoin(url, image_url),
        }

    try:
        response = requests.get(url, headers=headers, timeout=(8, 18))
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        payloads = []
        for script in soup.find_all("script"):
            script_text = script.string or script.get_text()
            if not script_text or not script_text.strip():
                continue
            is_json = script.get("type") == "application/ld+json" or script.get("id") == "__NEXT_DATA__"
            if is_json:
                try:
                    payloads.append(json.loads(script_text))
                except Exception:
                    pass

        for payload in payloads:
            candidate_teams = []
            for node in walk_json(payload):
                for roster_key in ("squads", "teams", "teamSquads", "matchSquads", "participants"):
                    team_list = node.get(roster_key) if isinstance(node, dict) else None
                    if isinstance(team_list, list):
                        candidate_teams.extend(team_list)
                candidate = team_record_from_json(node)
                if candidate:
                    candidate_teams.append(candidate)
            cleaned, seen = [], set()
            for item in candidate_teams:
                parsed_team = item if isinstance(item, dict) and item.get("img_url") else team_record_from_json(item)
                if not parsed_team:
                    continue
                key = re.sub(r"[^a-z]", "", parsed_team["name"].lower())
                if key not in seen:
                    cleaned.append(parsed_team)
                    seen.add(key)
            if len(cleaned) >= 2:
                return cleaned[:2], None

        # DOM fallback: locate captain markers and their nearby ICC profile links.
        captain_results = []
        for text_node in soup.find_all(string=re.compile(r"\(\s*c\s*\)", re.I)):
            label = re.sub(r"\s+", " ", str(text_node)).strip()
            name = re.sub(r"\s*\(\s*c\s*\)\s*", "", label, flags=re.I).strip()
            if not name or len(name) > 60:
                continue
            parent = text_node.parent
            found_profile = None
            found_image = None
            scope = parent
            for _ in range(7):
                if scope is None:
                    break
                for anchor in scope.find_all("a", href=True):
                    href = urljoin(url, anchor.get("href", ""))
                    if re.search(r"icc-cricket\.com/(?:rankings|players|player|profile)/\d+", href, re.I):
                        found_profile = href
                        break
                for img_tag in scope.find_all("img"):
                    alt = str(img_tag.get("alt", "")).lower()
                    if name.lower() in alt or alt in name.lower():
                        found_image = (
                            img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
                            or img_tag.get("data-original")
                        )
                        if not found_image and img_tag.get("srcset"):
                            found_image = img_tag.get("srcset").split(",")[-1].strip().split(" ")[0]
                        break
                if found_profile or found_image:
                    break
                scope = scope.parent
            captain_url = found_profile or (urljoin(url, found_image) if found_image else None)
            if captain_url and all(name.lower() != row["captain"].lower() for row in captain_results):
                captain_results.append({
                    "name": name,
                    "code": "",
                    "captain": name,
                    "img_url": captain_url,
                })
        if len(captain_results) >= 2:
            # ICC match pages display the first team squad followed by the second team squad.
            # The captain-card order is preserved; team labels are inferred from the match slug when possible.
            slug = parsed.path.rstrip("/").split("/")[-1]
            if "-vs-" in slug:
                teams_in_slug = [part.replace("-", " ").title() for part in slug.split("-vs-", 1)]
                # Match text/search results sometimes render team cards in reverse URL order.
                for row in captain_results[:2]:
                    row["name"] = teams_in_slug[0] if len([r for r in captain_results[:2] if r["name"] == teams_in_slug[0]]) else row["name"]
            return captain_results[:2], None
        return None, "ICC page loaded, but two captain-marked player cards with profile/image links were not found. Try the direct ICC captain profile URLs in Section 2."
    except Exception as exc:
        return None, f"Could not read the ICC match page: {exc}. Try the direct ICC captain profile URLs in Section 2."


def fetch_from_match_url(url):
    """Dispatch ICC match URLs to the ICC parser and ESPNcricinfo squad URLs to the existing parser."""
    host = (urlsplit(str(url or "").strip()).netloc or "").lower()
    if "icc-cricket.com" in host:
        return fetch_from_icc_match_url(url)
    if "cricinfo.com" in host:
        return fetch_from_cricinfo_url(url)
    return None, "Use an ICC match URL or an ESPNcricinfo match/squad URL."


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
    """Apply the same restrained grade and mild luminance normalization to both cutouts."""
    if image is None:
        return None
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")

    # Pull back excess jersey saturation and keep both source photos on one consistent grade.
    rgb = ImageEnhance.Color(rgb).enhance(1.03)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.04)

    # A small, capped exposure adjustment helps source portraits match without bleaching kits.
    try:
        red, green, blue = ImageStat.Stat(rgb, mask=alpha).mean
        visible_luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        brightness_factor = max(0.94, min(1.06, 112.0 / max(1.0, visible_luma)))
        rgb = ImageEnhance.Brightness(rgb).enhance(brightness_factor)
    except (ValueError, ZeroDivisionError):
        pass

    rgb = ImageEnhance.Sharpness(rgb).enhance(1.16)
    graded = rgb.convert("RGBA")
    graded.putalpha(alpha)
    return graded


# Exact player placement boxes measured from the 16:9 reference thumbnail.
# Canvas: 3840 x 2160 px. The independent left/right sizes intentionally match the reference.
LEFT_PLAYER_WIDTH = 1700
LEFT_PLAYER_HEIGHT = 2025
LEFT_PLAYER_X = 0
LEFT_PLAYER_Y = CANVAS_HEIGHT - LEFT_PLAYER_HEIGHT  # 135 px from top

RIGHT_PLAYER_WIDTH = 1660
RIGHT_PLAYER_HEIGHT = 2000
RIGHT_PLAYER_X = CANVAS_WIDTH - RIGHT_PLAYER_WIDTH  # 2180 px from left
RIGHT_PLAYER_Y = CANVAS_HEIGHT - RIGHT_PLAYER_HEIGHT  # 160 px from top


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
    font = load_robust_font(86)  # Slightly larger but consistently anchored top-centre.
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
    y0, y1 = 34, 34 + total_h + 2 * pad_y
    radius = (y1 - y0) // 2
    draw_pill_badge(draw, (x0, y0, x1, y1), (255, 255, 255, 255), (10, 10, 10, 255), 7, radius)
    draw.rounded_rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), radius=radius + 4, outline=(22, 70, 150, 255), width=4)
    text_x = center_x - total_w // 2
    text_y = y0 + (y1 - y0 - total_h) // 2 - bbox1[1]
    draw.text((text_x, text_y), first, font=font, fill=(7, 7, 7, 255))
    if second:
        draw.text((text_x + w1 + gap, text_y), second, font=font, fill=(12, 72, 155, 255))


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


# Official-ish broadcast palettes chosen by common team labels. These are graphic
# theme colours, not claims about a team's official brand specification.
TEAM_COLOR_PALETTES = {
    "IND": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "INDIA": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "IND WOMEN": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "IND-W": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "IND W": ((20, 83, 225), (255, 132, 30), (5, 35, 112)),
    "PAK": ((0, 111, 67), (190, 245, 120), (0, 53, 35)),
    "PAKISTAN": ((0, 111, 67), (190, 245, 120), (0, 53, 35)),
    "SL": ((15, 54, 125), (255, 190, 20), (4, 24, 65)),
    "SRI LANKA": ((15, 54, 125), (255, 190, 20), (4, 24, 65)),
    "AUS": ((0, 70, 170), (255, 190, 0), (0, 28, 83)),
    "AUSTRALIA": ((0, 70, 170), (255, 190, 0), (0, 28, 83)),
    "AUS WOMEN": ((0, 70, 170), (255, 190, 0), (0, 28, 83)),
    "NZ": ((16, 28, 48), (0, 184, 220), (3, 9, 20)),
    "NEW ZEALAND": ((16, 28, 48), (0, 184, 220), (3, 9, 20)),
    "NZ WOMEN": ((16, 28, 48), (0, 184, 220), (3, 9, 20)),
    "WI": ((16, 45, 110), (255, 205, 20), (5, 21, 58)),
    "WEST INDIES": ((16, 45, 110), (255, 205, 20), (5, 21, 58)),
    "ENG": ((15, 49, 112), (210, 230, 255), (4, 18, 55)),
    "ENGLAND": ((15, 49, 112), (210, 230, 255), (4, 18, 55)),
    "ZIM": ((0, 112, 75), (255, 203, 0), (0, 56, 38)),
    "ZIMBABWE": ((0, 112, 75), (255, 203, 0), (0, 56, 38)),
    "ZIM-W": ((0, 112, 75), (255, 203, 0), (0, 56, 38)),
    "ZIM W": ((0, 112, 75), (255, 203, 0), (0, 56, 38)),
    "SA": ((0, 105, 76), (255, 205, 0), (0, 43, 34)),
    "SOUTH AFRICA": ((0, 105, 76), (255, 205, 0), (0, 43, 34)),
    "BAN": ((0, 106, 78), (235, 245, 235), (0, 48, 36)),
    "BANGLADESH": ((0, 106, 78), (235, 245, 235), (0, 48, 36)),
    "AFG": ((25, 75, 160), (75, 190, 120), (8, 35, 90)),
    "AFGHANISTAN": ((25, 75, 160), (75, 190, 120), (8, 35, 90)),
}


def team_palette(team_name):
    """Return (main, accent, shadow) colors for men's and women's team label variants."""
    key = normalize_team_name(team_name)
    palette = TEAM_COLOR_PALETTES.get(key)
    if palette:
        return palette
    base = normalize_team_base(key)
    return TEAM_COLOR_PALETTES.get(base, ((24, 77, 185), (255, 145, 25), (5, 25, 75)))


def draw_team_flag_watermark(canvas, flag_image, x, y, size, main_color, accent_color, opacity=225):
    """Draw one circular team badge behind the portrait, preserving the whole flag aspect ratio."""
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.ellipse((3, 3, size - 4, size - 4), fill=(*main_color, min(240, opacity)),
               outline=(255, 255, 255, 245), width=18)
    bd.ellipse((17, 17, size - 18, size - 18), outline=(*accent_color, 255), width=9)

    if flag_image is not None:
        flag = flag_image.convert("RGBA")
        # Contain-fit the full rectangular flag on the badge; don't crop away its identifying details.
        max_flag = int(size * 0.72)
        scale = min(max_flag / max(1, flag.width), max_flag / max(1, flag.height))
        flag = flag.resize((max(1, int(flag.width * scale)), max(1, int(flag.height * scale))), Image.Resampling.LANCZOS)
        fa = flag.getchannel("A").point(lambda value: int(value * opacity / 255))
        flag.putalpha(fa)
        fx = (size - flag.width) // 2
        fy = (size - flag.height) // 2
        badge.alpha_composite(flag, (fx, fy))

    # Outer rings keep a clear logo edge when it sits over the tinted team panel.
    bd = ImageDraw.Draw(badge)
    bd.ellipse((3, 3, size - 4, size - 4), outline=(255, 255, 255, 250), width=18)
    bd.ellipse((17, 17, size - 18, size - 18), outline=(*accent_color, 255), width=8)
    canvas.alpha_composite(badge, (x, y))


def draw_team_color_backplates(canvas, team1_name, team2_name, flag1, flag2):
    """Add diagonal team-colour panels, accent slashes and flag watermarks behind players.

    The stadium remains visible through the colour panels and across the central pitch,
    mimicking compact team-colour YouTube live thumbnails rather than using a flat backdrop.
    """
    left_main, left_accent, left_dark = team_palette(team1_name)
    right_main, right_accent, right_dark = team_palette(team2_name)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = canvas.size
    panel_bottom = int(h * 0.86)
    left_inner_x = int(w * 0.34)
    left_outer_diag_x = int(w * 0.435)
    right_inner_x = int(w * 0.66)
    right_outer_diag_x = int(w * 0.565)

    # Main tinted side panels.
    d.polygon([(0, 0), (left_inner_x, 0), (left_outer_diag_x, panel_bottom), (0, panel_bottom)],
              fill=(*left_main, 88))
    d.polygon([(w, 0), (w - left_inner_x, 0), (w - left_outer_diag_x, panel_bottom), (w, panel_bottom)],
              fill=(*right_main, 88))

    # Rich darker insets add depth behind the player portraits.
    d.polygon([(0, 0), (int(w * .19), 0), (int(w * .29), panel_bottom), (0, panel_bottom)],
              fill=(*left_dark, 34))
    d.polygon([(w, 0), (int(w * .81), 0), (int(w * .71), panel_bottom), (w, panel_bottom)],
              fill=(*right_dark, 34))

    # Diagonal team-colour slashes, inspired by the reference channel's split panels.
    d.polygon([(int(w * .245), 0), (int(w * .276), 0), (int(w * .356), panel_bottom),
               (int(w * .325), panel_bottom)], fill=(*left_accent, 150))
    d.polygon([(int(w * .755), 0), (int(w * .724), 0), (int(w * .644), panel_bottom),
               (int(w * .675), panel_bottom)], fill=(*right_accent, 150))
    # Thin white separation pinstripes add sharp thumbnail contrast.
    d.line([(int(w * .282), 0), (int(w * .362), panel_bottom)], fill=(255, 255, 255, 112), width=7)
    d.line([(int(w * .718), 0), (int(w * .638), panel_bottom)], fill=(255, 255, 255, 112), width=7)
    canvas.alpha_composite(layer)

    # Large faded team logos/flags sit BEHIND the players. Player cutouts are composited next.
    watermark_size = 285
    draw_team_flag_watermark(canvas, flag1, 30, 58, watermark_size, left_main, left_accent, opacity=145)
    draw_team_flag_watermark(canvas, flag2, w - watermark_size - 30, 58, watermark_size, right_main, right_accent, opacity=145)


def generate_thumbnail(bg_img, p1_img, p2_img, channel_text, match_status, match_badge,
                       t1_name, t2_name, t1_flag, t2_flag, commentary_text="HINDI COMMENTARY",
                       design_style="PREET SPORTS — Match Talk (High Contrast)", live_scale=1.0):
    if design_style == "PREET SPORTS — Match Talk (High Contrast)":
        return generate_thumbnail_match_talk(
            bg_img=bg_img, p1_img=p1_img, p2_img=p2_img,
            channel_text=channel_text, match_status=match_status, match_badge=match_badge,
            t1_name=t1_name, t2_name=t2_name, t1_flag=t1_flag, t2_flag=t2_flag,
            commentary_text=commentary_text, live_scale=live_scale,
        )
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

    # Reference channel style: diagonal team-colour panels and muted team logos BEHIND players.
    draw_team_color_backplates(canvas, t1_name, t2_name, t1_flag, t2_flag)

    # Captain cutouts are layered above the stadium and team panels, below the text.
    render_player_cutout(canvas, p1_img, "left")
    render_player_cutout(canvas, p2_img, "right")

    overlay = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw_brand_pill(draw, channel_text)

    # Central stack — keep the user's requested order and proportions:
    # LIVE (largest) -> blue T20 / match-format pill -> compact Hindi commentary.
    # The stack is narrower and positioned in the open centre to avoid covering player faces.
    font_live = load_robust_font(470)
    live_y = 430
    _, _, _, live_h = draw_centered_text(
        draw, CANVAS_WIDTH, str(match_status or "LIVE"), live_y, font_live,
        (232, 15, 23, 255), stroke_width=22, stroke_fill=(255, 255, 255, 255)
    )

    # Match-format pill follows LIVE dynamically instead of using a fixed coordinate.
    font_sub = load_robust_font(175)
    badge_text = str(match_badge or "T20").strip().upper()
    sub_bbox = draw.textbbox((0, 0), badge_text, font=font_sub, stroke_width=0)
    sw, sh = sub_bbox[2] - sub_bbox[0], sub_bbox[3] - sub_bbox[1]
    badge_pad_x = 76
    badge_w = sw + badge_pad_x * 2
    badge_h = max(190, sh + 34)
    bx0 = (CANVAS_WIDTH - badge_w) // 2
    by0 = live_y + live_h + 24
    draw_pill_badge(
        draw, (bx0, by0, bx0 + badge_w, by0 + badge_h),
        (0, 72, 205, 255), (255, 255, 255, 255), 8, badge_h // 2
    )
    tx = (CANVAS_WIDTH - sw) // 2
    ty = by0 + (badge_h - sh) // 2 - sub_bbox[1]
    draw.text((tx, ty), badge_text, font=font_sub, fill=(255, 230, 0, 255))

    # Compact Hindi Commentary banner directly under the format pill.
    # Keep existing wording editable and avoid adding any extra slogans.
    commentary_label = str(commentary_text or "HINDI COMMENTARY").strip().upper()
    if commentary_label:
        font_commentary = load_robust_font(78)
        while font_commentary.size > 56 and draw.textbbox((0, 0), commentary_label, font=font_commentary)[2] > 1450:
            font_commentary = load_robust_font(font_commentary.size - 4)
        cbbox = draw.textbbox((0, 0), commentary_label, font=font_commentary)
        ctext_w = cbbox[2] - cbbox[0]
        ctext_h = cbbox[3] - cbbox[1]
        commentary_pad_x = 42
        commentary_w = ctext_w + commentary_pad_x * 2
        commentary_h = max(88, ctext_h + 26)
        commentary_x = (CANVAS_WIDTH - commentary_w) // 2
        commentary_y = by0 + badge_h + 12
        # Keep the banner compact and safely above the bottom team nameplates.
        banner_top = CANVAS_HEIGHT - 360 - 95
        commentary_y = min(commentary_y, banner_top - commentary_h - 20)
        draw.rounded_rectangle(
            (commentary_x, commentary_y, commentary_x + commentary_w, commentary_y + commentary_h),
            radius=commentary_h // 2,
            fill=(8, 24, 55, 248),
            outline=(255, 170, 20, 255),
            width=9,
        )
        inner_pad = 8
        draw.rounded_rectangle(
            (commentary_x + inner_pad, commentary_y + inner_pad,
             commentary_x + commentary_w - inner_pad, commentary_y + commentary_h - inner_pad),
            radius=max(18, commentary_h // 2 - inner_pad),
            outline=(255, 255, 255, 235),
            width=3,
        )
        # Split the default label: yellow HINDI, white COMMENTARY.
        if commentary_label == "HINDI COMMENTARY":
            first_word, second_word = "HINDI", "COMMENTARY"
            first_bbox = draw.textbbox((0, 0), first_word, font=font_commentary)
            second_bbox = draw.textbbox((0, 0), second_word, font=font_commentary)
            first_w = first_bbox[2] - first_bbox[0]
            second_w = second_bbox[2] - second_bbox[0]
            spacing = 14
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

    # Team flag/logo badges are deliberately behind the portraits, not on top of the players' heads.

    return Image.alpha_composite(canvas, overlay)



def high_ctr_team_label(team_name):
    """Compact team abbreviations for the bold bottom banners used in Match Talk style."""
    key = normalize_team_name(team_name).strip().upper()
    aliases = {
        "INDIA": "IND", "IND": "IND", "INDIA WOMEN": "IND-W", "IND WOMEN": "IND-W",
        "IND-W": "IND-W", "IND W": "IND-W", "ENGLAND": "ENG", "ENG": "ENG",
        "ENGLAND WOMEN": "ENG-W", "ENG WOMEN": "ENG-W", "ENG-W": "ENG-W",
        "PAKISTAN": "PAK", "PAK": "PAK", "NEW ZEALAND": "NZ", "NZ": "NZ",
        "NEW ZEALAND WOMEN": "NZ-W", "NZ WOMEN": "NZ-W", "NZ-W": "NZ-W",
        "AUSTRALIA": "AUS", "AUS": "AUS", "AUSTRALIA WOMEN": "AUS-W", "AUS WOMEN": "AUS-W",
        "SOUTH AFRICA": "SA", "SA": "SA", "SOUTH AFRICA WOMEN": "SA-W", "SA WOMEN": "SA-W",
        "SRI LANKA": "SL", "SL": "SL", "WEST INDIES": "WI", "WI": "WI",
        "BANGLADESH": "BAN", "BAN": "BAN", "AFGHANISTAN": "AFG", "AFG": "AFG",
        "ZIMBABWE": "ZIM", "ZIM": "ZIM", "IRELAND": "IRE", "IRE": "IRE",
        "NETHERLANDS": "NED", "NED": "NED", "SCOTLAND": "SCO", "SCO": "SCO",
        "NEPAL": "NEP", "NEP": "NEP", "USA": "USA", "UAE": "UAE",
        "NAMIBIA": "NAM", "NAM": "NAM", "CANADA": "CAN", "CAN": "CAN",
        "HONG KONG": "HK", "HK": "HK",
    }
    if key in aliases:
        return aliases[key]
    if key.endswith(" WOMEN"):
        base = key[:-6].strip()
        if base in aliases:
            return aliases[base] + "-W"
    if key.endswith("-W") and key[:-2] in aliases:
        return aliases[key[:-2]] + "-W"
    words = re.findall(r"[A-Z0-9]+", key)
    if len(words) >= 2:
        return "".join(word[0] for word in words[:4])[:5] or key[:4]
    return key[:5] or "TEAM"


def render_match_talk_player(canvas, player_img, side):
    """Large upper-body cutout with a thin white keyline and restrained shadow."""
    if player_img is None:
        return
    player = get_image_alpha_content(apply_sports_color_grade(player_img)).convert("RGBA")

    # Keep both portraits at matching visual height. Use a strong chest-up scale while
    # preserving each source's aspect ratio; the lower team plates will cover the waist.
    max_w = int(CANVAS_WIDTH * 0.385)
    max_h = int(CANVAS_HEIGHT * 0.94)
    scale = min(max_w / max(1, player.width), max_h / max(1, player.height))
    new_w = max(1, int(round(player.width * scale)))
    new_h = max(1, int(round(player.height * scale)))
    player = player.resize((new_w, new_h), Image.Resampling.LANCZOS)

    x = 0 if side == "left" else CANVAS_WIDTH - new_w
    y = max(0, CANVAS_HEIGHT - new_h)

    alpha = player.getchannel("A")

    # Draw the shadow first. The white keyline is composited after it so the edge stays crisp.
    shadow_alpha = alpha.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(8))
    shadow_alpha = shadow_alpha.point(lambda value: int(value * 0.17))
    shadow = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    canvas.alpha_composite(shadow, (x, y))

    # 25 px at 4K scales to roughly 3-4 px in the 1280 × 720 preview.
    outline_alpha = ImageChops.subtract(alpha.filter(ImageFilter.MaxFilter(25)), alpha)
    outline_alpha = outline_alpha.filter(ImageFilter.GaussianBlur(0.45))
    outline = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 0))
    outline.putalpha(outline_alpha.point(lambda value: int(value * 0.96)))
    canvas.alpha_composite(outline, (x, y))
    canvas.alpha_composite(player, (x, y))


def draw_match_talk_arrow(draw, x, y, width, height, label, side):
    """Slim bottom nameplate with a yellow border and pointed inner end."""
    tip = max(26, int(height * 0.48))
    if side == "left":
        points = [(x, y), (x + width - tip, y), (x + width, y + height // 2),
                  (x + width - tip, y + height), (x, y + height)]
    else:
        points = [(x + tip, y), (x + width, y), (x + width, y + height),
                  (x + tip, y + height), (x, y + height // 2)]
    draw.polygon(points, fill=(0, 0, 0, 255))
    draw.line(points + [points[0]], fill=(255, 205, 0, 255), width=max(8, int(height * 0.055)), joint="curve")

    label_font = load_robust_font(int(height * 1.12))
    max_w = int(width * 0.69)
    while label_font.size > 42:
        box = draw.textbbox((0, 0), label, font=label_font)
        if box[2] - box[0] <= max_w:
            break
        label_font = load_robust_font(label_font.size - 6)
    box = draw.textbbox((0, 0), label, font=label_font)
    tw, th = box[2] - box[0], box[3] - box[1]
    # Place text on the wide outer half, not over the inward point.
    if side == "left":
        tx = x + max(8, int((width - tip - tw) * 0.50))
    else:
        tx = x + tip + max(8, int((width - tip - tw) * 0.50))
    ty = y + (height - th) // 2 - box[1]
    draw.text((tx, ty), label, font=label_font, fill=(255, 255, 255, 255))


def _center_font_fitted(draw, text, start_size, max_width, min_size=42):
    font = load_robust_font(start_size)
    while font.size > min_size:
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            break
        font = load_robust_font(font.size - 6)
    return font


def generate_thumbnail_match_talk(bg_img, p1_img, p2_img, channel_text, match_status, match_badge,
                                  t1_name, t2_name, t1_flag, t2_flag, commentary_text="MATCH TALK",
                                  live_scale=1.0):
    """High-contrast 16:9 Match Talk layout, designed on a 4K canvas for clean export."""
    w, h = CANVAS_WIDTH, CANVAS_HEIGHT
    if bg_img is None:
        bg_img = fetch_default_stadium_background()
    if bg_img is not None:
        canvas = resize_cover(bg_img, w, h)
        canvas = canvas.filter(ImageFilter.GaussianBlur(0.25))
        canvas = ImageEnhance.Brightness(canvas).enhance(1.12)
        canvas = ImageEnhance.Color(canvas).enhance(1.27)
        canvas = ImageEnhance.Contrast(canvas).enhance(1.14)
        canvas = ImageEnhance.Sharpness(canvas).enhance(1.25)
    else:
        canvas = generate_procedural_stadium()

    # Brighter blue sky and readable green pitch, with stronger separation between layers.
    bg_tint = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tint_draw = ImageDraw.Draw(bg_tint)
    blue_end = int(h * 0.64)
    for y in range(0, blue_end, 8):
        progress = y / max(1, blue_end)
        alpha = int(108 * (1 - progress) + 15)
        tint_draw.line((0, y, w, y), fill=(0, 91, 255, alpha), width=8)
    green_start = int(h * 0.70)
    for y in range(green_start, h, 8):
        progress = (y - green_start) / max(1, h - green_start)
        alpha = int(10 + 27 * progress)
        tint_draw.line((0, y, w, y), fill=(0, 95, 18, alpha), width=8)
    canvas = Image.alpha_composite(canvas, bg_tint)

    # Team-colour side lanes; the central pitch remains visible behind the title stack.
    panel_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel_layer)
    pd.polygon([(0, 0), (int(w * 0.205), 0), (int(w * 0.125), int(h * 0.84)), (0, int(h * 0.84))],
               fill=(8, 38, 205, 180))
    pd.polygon([(w, 0), (int(w * 0.795), 0), (int(w * 0.875), int(h * 0.84)), (w, int(h * 0.84))],
               fill=(8, 38, 205, 180))
    pd.polygon([(int(w * 0.205), 0), (int(w * 0.222), 0),
                (int(w * 0.142), int(h * 0.84)), (int(w * 0.125), int(h * 0.84))],
               fill=(255, 202, 0, 255))
    pd.polygon([(int(w * 0.795), 0), (int(w * 0.778), 0),
                (int(w * 0.858), int(h * 0.84)), (int(w * 0.875), int(h * 0.84))],
               fill=(255, 202, 0, 255))
    canvas = Image.alpha_composite(canvas, panel_layer)

    # Both flags are drawn in the upper corners first, then partly hidden by the players.
    left_main, left_accent, _ = team_palette(t1_name)
    right_main, right_accent, _ = team_palette(t2_name)
    emblem_size = int(h * 0.174)  # both flags reduced by about 15%
    emblem_y = int(h * 0.006)     # move both badges closer to the top edge
    outer_margin = int(w * 0.003)
    draw_team_flag_watermark(canvas, t1_flag, outer_margin, emblem_y, emblem_size,
                             left_main, left_accent, opacity=242)
    draw_team_flag_watermark(canvas, t2_flag, w - emblem_size - outer_margin, emblem_y,
                             emblem_size, right_main, right_accent, opacity=242)

    # Prominent player cutouts sit in the outer thirds. This preserves a usable centre lane.
    render_match_talk_player(canvas, p1_img, "left")
    render_match_talk_player(canvas, p2_img, "right")

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Consistent small brand plate at top centre.
    brand_text = str(channel_text or "PREET SPORTS").strip().upper()
    brand_font = _center_font_fitted(draw, brand_text, 92, int(w * 0.30), 40)
    brand_box = draw.textbbox((0, 0), brand_text, font=brand_font)
    brand_tw, brand_th = brand_box[2] - brand_box[0], brand_box[3] - brand_box[1]
    brand_w = max(int(w * 0.255), brand_tw + 82)
    brand_h = max(int(h * 0.064), brand_th + 36)
    brand_x = (w - brand_w) // 2
    brand_y = int(h * 0.012)
    draw.rectangle((brand_x - 6, brand_y - 6, brand_x + brand_w + 6, brand_y + brand_h + 6),
                   fill=(5, 18, 38, 255), outline=(255, 208, 0, 255), width=8)
    draw.rectangle((brand_x, brand_y, brand_x + brand_w, brand_y + brand_h), fill=(9, 58, 151, 255))
    draw.rectangle((brand_x, brand_y, brand_x + brand_w, brand_y + 10), fill=(235, 20, 28, 255))
    brand_tx = (w - brand_tw) // 2
    brand_ty = brand_y + (brand_h - brand_th) // 2 - brand_box[1]
    draw.text((brand_tx, brand_ty), brand_text, font=brand_font, fill=(255, 255, 255, 255),
              stroke_width=2, stroke_fill=(0, 0, 0, 255))

    # LIVE is the first focal point: ~45% canvas width, thick white edge and black depth.
    live_text = str(match_status or "LIVE").strip().upper()
    live_scale = max(1.0, min(1.10, float(live_scale or 1.0)))
    live_max_width = int(w * (0.455 if live_scale <= 1.01 else 0.50))
    live_font = _center_font_fitted(draw, live_text, int(500 * live_scale), live_max_width, 56)
    live_bbox = draw.textbbox((0, 0), live_text, font=live_font, stroke_width=18)
    live_h = live_bbox[3] - live_bbox[1]
    live_y = int(h * 0.095)
    draw_centered_text(draw, w, live_text, live_y + 16, live_font, (0, 0, 0, 255),
                       stroke_width=27, stroke_fill=(0, 0, 0, 255))
    draw_centered_text(draw, w, live_text, live_y, live_font, (255, 255, 255, 255),
                       stroke_width=18, stroke_fill=(255, 255, 255, 255))
    draw_centered_text(draw, w, live_text, live_y, live_font, (232, 15, 23, 255))
    live_bottom = live_y + live_h

    # Split ordinal/format badge, tightly stacked under LIVE.
    badge_text = str(match_badge or "T20").strip()
    ordinal_match = re.match(
        r"^\s*((?:\d+(?:st|nd|rd|th)|FINAL|QUALIFIER|ELIMINATOR))\s+(.+?)\s*$",
        badge_text, flags=re.IGNORECASE
    )
    if ordinal_match:
        ordinal_text = ordinal_match.group(1)
        format_text = ordinal_match.group(2).upper()
        badge_w = int(w * 0.325)
        left_panel_w = int(badge_w * 0.43)
    else:
        ordinal_text = ""
        format_text = badge_text.upper()
        badge_w = int(w * 0.325)
        left_panel_w = 0
    badge_h = int(h * 0.118)
    badge_x = (w - badge_w) // 2
    badge_y = max(int(h * 0.265), live_bottom + int(h * 0.008))
    draw.rectangle((badge_x - 12, badge_y - 12, badge_x + badge_w + 12, badge_y + badge_h + 12),
                   fill=(3, 7, 15, 255))
    draw.rectangle((badge_x, badge_y, badge_x + badge_w, badge_y + badge_h),
                   fill=(0, 0, 0, 255), outline=(255, 203, 0, 255), width=18)
    inset = 9
    if ordinal_text:
        split_x = badge_x + left_panel_w
        draw.rectangle((badge_x + inset, badge_y + inset, split_x, badge_y + badge_h - inset),
                       fill=(250, 250, 250, 255))
        draw.rectangle((split_x, badge_y + inset, badge_x + badge_w - inset, badge_y + badge_h - inset),
                       fill=(0, 0, 0, 255))
        draw.line((split_x, badge_y + inset, split_x, badge_y + badge_h - inset),
                  fill=(255, 203, 0, 255), width=8)
        ordinal_font = _center_font_fitted(draw, ordinal_text, 195, left_panel_w - 48, 44)
        ob = draw.textbbox((0, 0), ordinal_text, font=ordinal_font)
        ow, oh = ob[2] - ob[0], ob[3] - ob[1]
        ox = badge_x + (left_panel_w - ow) // 2
        oy = badge_y + (badge_h - oh) // 2 - ob[1]
        draw.text((ox, oy), ordinal_text, font=ordinal_font, fill=(0, 0, 0, 255))
        format_area_x, format_area_w = split_x, badge_w - left_panel_w
    else:
        format_area_x, format_area_w = badge_x, badge_w
    format_font = _center_font_fitted(draw, format_text, 205, format_area_w - 38, 44)
    fb = draw.textbbox((0, 0), format_text, font=format_font)
    fw, fh = fb[2] - fb[0], fb[3] - fb[1]
    fx = format_area_x + (format_area_w - fw) // 2
    fy = badge_y + (badge_h - fh) // 2 - fb[1]
    draw.text((fx, fy), format_text, font=format_font, fill=(255, 221, 0, 255),
              stroke_width=2, stroke_fill=(15, 15, 15, 255))

    # Compact MATCH TALK panel directly under the format badge.
    talk_text = str(commentary_text or "MATCH TALK").strip().upper()
    talk_font = _center_font_fitted(draw, talk_text, 205, int(w * 0.50) - 58, 42)
    talk_box = draw.textbbox((0, 0), talk_text, font=talk_font)
    talk_tw, talk_th = talk_box[2] - talk_box[0], talk_box[3] - talk_box[1]
    talk_w = min(int(w * 0.50), max(int(w * 0.43), talk_tw + 74))
    talk_h = int(h * 0.112)
    talk_x = (w - talk_w) // 2
    talk_y = badge_y + badge_h + int(h * 0.012)
    # Keep a minimum clear gap before the bottom team plates.
    team_h = int(h * 0.158)
    team_y = int(h * 0.82)
    talk_y = min(talk_y, team_y - talk_h - int(h * 0.014))
    draw.rectangle((talk_x - 10, talk_y - 10, talk_x + talk_w + 10, talk_y + talk_h + 10),
                   fill=(4, 8, 15, 255))
    draw.rectangle((talk_x, talk_y, talk_x + talk_w, talk_y + talk_h),
                   fill=(233, 13, 24, 255), outline=(255, 210, 0, 255), width=18)
    talk_tx = (w - talk_tw) // 2
    talk_ty = talk_y + (talk_h - talk_th) // 2 - talk_box[1]
    draw.text((talk_tx, talk_ty), talk_text, font=talk_font, fill=(255, 255, 255, 255),
              stroke_width=2, stroke_fill=(20, 12, 12, 255))

    # Bottom team bars occupy approximately 15.8% of canvas height, not 20%+.
    draw_match_talk_arrow(draw, 0, team_y, int(w * 0.405), team_h, high_ctr_team_label(t1_name), "left")
    draw_match_talk_arrow(draw, w - int(w * 0.405), team_y, int(w * 0.405), team_h,
                          high_ctr_team_label(t2_name), "right")

    return Image.alpha_composite(canvas, overlay)

# =========================================================
# STREAMLIT UI
# =========================================================
st.title("🏏 PREET SPORTS — 4K Cricket Thumbnail Studio")
st.caption("High-CTR Match Talk layout · wider LIVE · both team flags · chest-up player cutouts · 3840 × 2160 PNG export.")

for key in [
    "p1_cutout", "p2_cutout", "p1_ai_front", "p2_ai_front",
    "p1_ai_source_hash", "p2_ai_source_hash", "t1_code", "t2_code", "auto_bg",
    "reference_left_cutout", "reference_right_cutout", "reference_thumbnail_hash",
    "p1_cutout_source", "p2_cutout_source", "reference_cutout_matchup_key",
    "reference_cutouts_origin",
]:
    if key not in st.session_state:
        st.session_state[key] = None
if "_reference_pending_extractions" not in st.session_state:
    st.session_state["_reference_pending_extractions"] = []
if "_reference_extraction_messages" not in st.session_state:
    st.session_state["_reference_extraction_messages"] = []

col_left, col_right = st.columns([1, 1.2], gap="large")

with col_left:
    st.subheader("1. Match & Captain Auto-Fetch")
    # Seed the requested ICC match URL once for existing sessions whose old ESPN URL field was blank.
    if not st.session_state.get("_match_url_default_initialized"):
        if not str(st.session_state.get("match_page_url", "") or "").strip():
            st.session_state["match_page_url"] = "https://www.icc-cricket.com/matches/274145/pakistan-vs-england"
        st.session_state["_match_url_default_initialized"] = True
    match_url = st.text_input(
        "Paste ICC Match URL or ESPNcricinfo Match / Squad URL",
        value="https://www.icc-cricket.com/matches/274145/pakistan-vs-england",
        placeholder="https://www.icc-cricket.com/matches/... or an ESPNcricinfo match-squads URL",
        key="match_page_url",
    )
    if st.button("🚀 Auto-Extract Captains from Match Page", type="primary", use_container_width=True):
        if not match_url.strip():
            st.warning("Paste an ICC match URL or ESPNcricinfo match/squad URL first.")
        elif not any(host in match_url.lower() for host in ("icc-cricket.com", "cricinfo.com")):
            st.warning("Use an ICC match URL or an ESPNcricinfo match/squad page URL, or paste direct player image URLs below.")
        else:
            with st.spinner("Reading the match page and fetching both captain portraits..."):
                teams, err = fetch_from_match_url(match_url.strip())
                if teams and len(teams) >= 2:
                    st.session_state.t1_code = teams[0]["name"]
                    st.session_state.t2_code = teams[1]["name"]
                    st.session_state["team1_name_input"] = teams[0]["name"]
                    st.session_state["team2_name_input"] = teams[1]["name"]
                    if teams[0].get("match_badge"):
                        st.session_state["match_badge_input"] = teams[0]["match_badge"]
                    photo_errors = []
                    for index, side in enumerate(("left", "right")):
                        team = teams[index]
                        captain_url = team.get("img_url")
                        if not captain_url:
                            photo_errors.append(f"{team['name']}: captain image URL not found")
                            continue
                        if "icc-cricket.com" in captain_url.lower():
                            image, image_error = fetch_icc_player_image(captain_url, attempts=3)
                        else:
                            image = fetch_online_image(captain_url)
                            image_error = None if image is not None else "image download failed"
                        if image is None:
                            photo_errors.append(f"{team['name']} ({team.get('captain', 'captain')}): {image_error or 'image download failed'}")
                            continue
                        if side == "left":
                            st.session_state.p1_cutout = image
                            st.session_state["p1_cutout_source"] = "captain_url"
                            st.session_state["left_captain_image_url"] = captain_url
                        else:
                            st.session_state.p2_cutout = image
                            st.session_state["p2_cutout_source"] = "captain_url"
                            st.session_state["right_captain_image_url"] = captain_url
                    if not photo_errors:
                        st.success(
                            f"Fetched captain portraits: {teams[0].get('captain', teams[0]['name'])} ({teams[0]['name']}) and "
                            f"{teams[1].get('captain', teams[1]['name'])} ({teams[1]['name']})."
                        )
                    else:
                        st.warning("Match teams found, but some captain photos failed: " + "; ".join(photo_errors))
                else:
                    st.warning(err or "Could not identify both match captains. Try the direct ICC profile URLs in Section 2.")

    st.subheader("2. Direct Captain Image URLs")
    st.caption("Paste a direct image URL or an ICC player-profile URL for EACH side. ICC URLs such as https://www.icc-cricket.com/rankings/67041/sophie-molineux are resolved to the matching official ICC player image. One profile URL supplies one player, not every team captain. Women’s team aliases and flags are supported; Australia Women defaults to Sophie Molineux unless you enter a different profile URL.")
    left_captain_url = st.text_input(
        "Left Player Image / ICC Profile URL",
        value="",
        placeholder="Paste a direct image or ICC player-profile URL",
        key="left_captain_image_url",
    )
    right_captain_url = st.text_input(
        "Right Player Image / ICC Profile URL",
        value="",
        placeholder="Paste a direct image or ICC player-profile URL",
        key="right_captain_image_url",
    )
    if st.button("🖼️ Fetch / Refresh Captain Images", use_container_width=True):
        attempts, loaded = 0, 0
        if left_captain_url.strip():
            attempts += 1
            image_left, left_error = fetch_icc_player_image(left_captain_url.strip(), attempts=3)
            if image_left is not None:
                st.session_state.p1_cutout = image_left
                st.session_state["p1_cutout_source"] = "captain_url"
                loaded += 1
            else:
                st.error(
                    "Left player image fetch failed: "
                    + str(left_error or "unknown download error")
                    + ". Check the URL or try a direct public image link."
                )
        if right_captain_url.strip():
            attempts += 1
            image_right, right_error = fetch_icc_player_image(right_captain_url.strip(), attempts=3)
            if image_right is not None:
                st.session_state.p2_cutout = image_right
                st.session_state["p2_cutout_source"] = "captain_url"
                loaded += 1
            else:
                st.error(
                    "Right player image fetch failed: "
                    + str(right_error or "unknown download error")
                    + ". Check the URL or try a direct public image link."
                )
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

    # Automatically fetch mapped official ICC player portraits when team names or match format change.
    # Cached image downloads keep ordinary page reruns fast and prevent repeated network calls.
    auto_format = st.session_state.get("match_badge_input", "T20")
    auto_signature = (
        normalize_team_name(team1),
        normalize_team_name(team2),
        normalize_team_name(auto_format),
    )
    previous_signature = st.session_state.get("_icc_team_image_signature")
    retry_icc_fetch = st.button(
        "🔄 Retry automatic ICC photo fetch",
        key="retry_icc_team_image_fetch",
        help="Retries official ICC image downloads without using the long-lived cache for failed requests.",
        use_container_width=True,
    )
    if previous_signature != auto_signature or retry_icc_fetch:
        # Do not carry an automatically selected ICC portrait across a team/format change.
        if st.session_state.get("p1_cutout_source") == "team_icc_auto":
            st.session_state.p1_cutout = None
            st.session_state["p1_cutout_source"] = None
        if st.session_state.get("p2_cutout_source") == "team_icc_auto":
            st.session_state.p2_cutout = None
            st.session_state["p2_cutout_source"] = None
        st.session_state["_icc_team_image_signature"] = auto_signature
        auto_loaded = 0
        auto_missing = []
        auto_failed = []
        for side, team_name in (("left", team1), ("right", team2)):
            # A manually fetched match-squad or URL image takes priority over an automatic team default.
            source_key = "p1_cutout_source" if side == "left" else "p2_cutout_source"
            if st.session_state.get(source_key) == "captain_url":
                continue
            profile_url = get_icc_team_captain_profile_url(team_name, auto_format)
            if not profile_url:
                if team_name:
                    auto_missing.append(team_name)
                continue
            image, image_error = fetch_icc_player_image(profile_url, attempts=3)
            if image is None:
                auto_failed.append(f"{team_name} ({image_error or 'download failed'})")
                continue
            if side == "left":
                st.session_state.p1_cutout = image
                st.session_state["p1_cutout_source"] = "team_icc_auto"
            else:
                st.session_state.p2_cutout = image
                st.session_state["p2_cutout_source"] = "team_icc_auto"
            auto_loaded += 1
        if auto_loaded:
            st.success(f"Auto-fetched {auto_loaded} official ICC player photo(s) from the team names.")
        if auto_missing:
            st.info(
                "No automatic ICC captain profile is mapped for: "
                + ", ".join(auto_missing)
                + ". For an exact match-specific captain, paste an ESPNcricinfo match/squad URL or an ICC player-profile URL above."
            )
        st.session_state["_icc_team_image_failed"] = list(auto_failed)
        if auto_failed:
            st.warning(
                "Could not download these official ICC portraits after 3 attempts: "
                + ", ".join(auto_failed)
                + ". Tap ‘Retry automatic ICC photo fetch’ once more. If it keeps failing, use a direct image URL in Section 2. "
                "The general image cache is bypassed here so temporary failures are not cached for a full day."
            )

    st.caption("ICC portraits auto-load for recognized team names. Match-specific teams without a mapped captain still work through the squad URL or the ICC profile URL fields above.")
    swap_player_photos = st.checkbox(
        "Swap LEFT / RIGHT player photos (use if extracted players are in reverse order)",
        value=False,
        key="swap_player_photos_v1",
        help="Swaps only the player images. Team names, flags and team panels remain in their left/right positions.",
    )

    # Locked to the supplied reference layout; no extra style variants.
    design_style = "PREET SPORTS — Match Talk (High Contrast)"

    col_status, col_badge = st.columns(2)
    with col_status:
        match_status = st.text_input("Main Text", value="LIVE", key="match_status_input")
    with col_badge:
        match_badge = st.text_input(
            "Match Format / Number Badge (e.g. 2nd T20, 1st ODI)",
            value="4th ODI",
            key="match_badge_input",
        )
    commentary_text = st.text_input(
        "Red strip below the format badge",
        value="MATCH TALK",
        key="commentary_text_matchtalk_input",
    )
    channel_title = st.text_input("Channel Brand", value="PREET SPORTS", key="channel_title_input")
    enlarge_live_title = st.checkbox(
        "Optional: enlarge LIVE by about 10% (leave off if it touches either face)",
        value=False,
        key="enlarge_live_title_v1",
    )
    live_scale = 1.10 if enlarge_live_title else 1.0

    st.subheader("4. Remove Background from Any Image")
    st.caption(
        "Background removal uses local U2NETP only when weights are already cached; otherwise it quickly falls back to OpenCV GrabCut. "
        "No Gemini API request is made. Results are cached for 30 days; cropping and 4K composition remain local."
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
            with st.spinner("Removing background locally… uses cached U2NETP if available; otherwise fast OpenCV fallback."):
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

    st.subheader("5. Remove Background from Cropped Player Images (Local)")
    st.caption(
        "Upload a cropped player photo OR paste its direct image URL for each side. The app fetches the URL, removes the background locally, and applies the transparent cutout to the corresponding thumbnail side. "
        "No Gemini API call is used. Direct image URLs such as JPG/WebP links with query parameters are supported; a player profile webpage is not the same as a direct image URL."
    )
    cutout_left_col, cutout_right_col = st.columns(2)

    def _remote_image_as_upload_bytes(remote_image):
        """Convert a fetched PIL image to compact bytes for the local cutout pipeline."""
        image = remote_image.convert("RGBA")
        max_side = 1800
        if max(image.size) > max_side:
            scale = max_side / float(max(image.size))
            image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
        buf = io.BytesIO()
        alpha = image.getchannel("A")
        if alpha.getextrema()[0] < 250:
            image.save(buf, format="PNG", optimize=False, compress_level=1)
            extension = ".png"
        else:
            image.convert("RGB").save(buf, format="JPEG", quality=88, optimize=False)
            extension = ".jpg"
        return buf.getvalue(), extension

    def _activate_remote_player_cutout(side, cutout, url):
        """Store a URL-extracted cutout directly in the selected thumbnail player slot."""
        current_matchup = (normalize_team_name(team1), normalize_team_name(team2))
        old_origin = st.session_state.get("reference_cutouts_origin")
        if old_origin == "reference_thumbnail":
            # Don't combine half of a new URL pair with the other side from an old reference image.
            if side == "left":
                st.session_state["reference_right_cutout"] = None
            else:
                st.session_state["reference_left_cutout"] = None
        st.session_state["reference_cutouts_origin"] = "manual_cropped_upload"
        st.session_state["reference_cutout_matchup_key"] = current_matchup
        st.session_state["reference_cutouts_from_remote_urls"] = True
        if side == "left":
            st.session_state["cropped_left_transparent"] = cutout
            st.session_state["reference_left_cutout"] = cutout
            st.session_state.p1_cutout = cutout
            st.session_state["p1_cutout_source"] = "remote_player_url"
            st.session_state.p1_ai_front = None
            st.session_state.p1_ai_source_hash = None
            st.session_state["remote_left_cutout_source_url"] = url
        else:
            st.session_state["cropped_right_transparent"] = cutout
            st.session_state["reference_right_cutout"] = cutout
            st.session_state.p2_cutout = cutout
            st.session_state["p2_cutout_source"] = "remote_player_url"
            st.session_state.p2_ai_front = None
            st.session_state.p2_ai_source_hash = None
            st.session_state["remote_right_cutout_source_url"] = url

    with cutout_left_col:
        remote_left_player_url = st.text_input(
            "Or direct image URL for LEFT player",
            value=st.session_state.get("remote_left_player_url_v1", ""),
            placeholder="https://example.com/left-player.jpg",
            key="remote_left_player_url_v1",
            help="Paste the direct image URL, not a page containing the image.",
        )
        if st.button("🌐 Fetch URL + remove LEFT background", use_container_width=True, key="remove_remote_left_bg_v1"):
            url = remote_left_player_url.strip()
            if not url:
                st.warning("Paste the LEFT player's direct image URL first.")
            elif not url.lower().startswith(("https://", "http://")):
                st.error("The image URL must begin with http:// or https://.")
            else:
                with st.spinner("Fetching the LEFT player image…"):
                    remote_image = fetch_online_image(url)
                if remote_image is None:
                    st.error("Could not fetch an image from that URL. Check that it is a public, direct image link.")
                else:
                    try:
                        source_bytes, source_ext = _remote_image_as_upload_bytes(remote_image)
                        with st.spinner("Removing the LEFT background locally…"):
                            cutout, cutout_error = remove_background_from_any_image(
                                source_bytes, f"remote_left_player{source_ext}"
                            )
                        if cutout is not None:
                            _activate_remote_player_cutout("left", cutout, url)
                            st.success("LEFT image background removed and applied to the thumbnail.")
                        else:
                            st.error(cutout_error or "Could not remove the LEFT image background.")
                    except Exception as exc:
                        st.error(f"LEFT image processing failed: {exc}")

        cropped_left_upload = st.file_uploader(
            "Upload cropped LEFT player image",
            type=["png", "jpg", "jpeg", "webp"],
            key="cropped_player_left_upload_v1",
        )
        if cropped_left_upload is not None:
            left_source_bytes = cropped_left_upload.getvalue()
            left_source_hash = hashlib.sha1(left_source_bytes).hexdigest()
            if st.session_state.get("cropped_left_source_hash") != left_source_hash:
                st.session_state["cropped_left_source_hash"] = left_source_hash
                st.session_state["cropped_left_transparent"] = None
            if st.button("✂️ Remove LEFT background", use_container_width=True, key="remove_cropped_left_bg_v1"):
                with st.spinner("Removing the LEFT background locally…"):
                    cutout, cutout_error = remove_background_from_any_image(left_source_bytes, cropped_left_upload.name)
                if cutout is not None:
                    st.session_state["cropped_left_transparent"] = cutout
                    st.session_state.p1_cutout = cutout
                    st.session_state["reference_left_cutout"] = cutout
                    # Do not let an old reference-extracted right player silently survive
                    # when a new manual left cutout becomes the active source.
                    if st.session_state.get("reference_cutouts_origin") == "reference_thumbnail":
                        st.session_state["reference_right_cutout"] = None
                    st.session_state["reference_cutouts_origin"] = "manual_cropped_upload"
                    st.session_state["p1_cutout_source"] = "manual_cropped_upload"
                    st.success("Left player background removed. This transparent cutout is now selected for the thumbnail.")
                else:
                    st.error(cutout_error or "Could not remove the left background.")
            if st.session_state.get("cropped_left_transparent") is not None:
                left_transparent = st.session_state["cropped_left_transparent"]
                st.image(left_transparent, caption="LEFT player — transparent preview", use_container_width=True)
                left_transparent_buffer = io.BytesIO()
                left_transparent.save(left_transparent_buffer, format="PNG", optimize=False)
                st.download_button(
                    "⬇️ Download LEFT transparent PNG",
                    data=left_transparent_buffer.getvalue(),
                    file_name="left_player_transparent.png",
                    mime="image/png",
                    use_container_width=True,
                    key="download_cropped_left_transparent_v1",
                )
    with cutout_right_col:
        remote_right_player_url = st.text_input(
            "Or direct image URL for RIGHT player",
            value=st.session_state.get("remote_right_player_url_v1", ""),
            placeholder="https://static.cricbuzz.com/a/img/v1/i1/c1005820/melie-kerr.jpg?d=low&p=gthumb",
            key="remote_right_player_url_v1",
            help="Example: a public Cricbuzz player image URL ending in .jpg, including any query parameters.",
        )
        if st.button("🌐 Fetch URL + remove RIGHT background", use_container_width=True, key="remove_remote_right_bg_v1"):
            url = remote_right_player_url.strip()
            if not url:
                st.warning("Paste the RIGHT player's direct image URL first.")
            elif not url.lower().startswith(("https://", "http://")):
                st.error("The image URL must begin with http:// or https://.")
            else:
                with st.spinner("Fetching the RIGHT player image…"):
                    remote_image = fetch_online_image(url)
                if remote_image is None:
                    st.error("Could not fetch an image from that URL. Check that it is a public, direct image link.")
                else:
                    try:
                        source_bytes, source_ext = _remote_image_as_upload_bytes(remote_image)
                        with st.spinner("Removing the RIGHT background locally…"):
                            cutout, cutout_error = remove_background_from_any_image(
                                source_bytes, f"remote_right_player{source_ext}"
                            )
                        if cutout is not None:
                            _activate_remote_player_cutout("right", cutout, url)
                            st.success("RIGHT image background removed and applied to the thumbnail.")
                        else:
                            st.error(cutout_error or "Could not remove the RIGHT image background.")
                    except Exception as exc:
                        st.error(f"RIGHT image processing failed: {exc}")

        cropped_right_upload = st.file_uploader(
            "Upload cropped RIGHT player image",
            type=["png", "jpg", "jpeg", "webp"],
            key="cropped_player_right_upload_v1",
        )
        if cropped_right_upload is not None:
            right_source_bytes = cropped_right_upload.getvalue()
            right_source_hash = hashlib.sha1(right_source_bytes).hexdigest()
            if st.session_state.get("cropped_right_source_hash") != right_source_hash:
                st.session_state["cropped_right_source_hash"] = right_source_hash
                st.session_state["cropped_right_transparent"] = None
            if st.button("✂️ Remove RIGHT background", use_container_width=True, key="remove_cropped_right_bg_v1"):
                with st.spinner("Removing the RIGHT background locally…"):
                    cutout, cutout_error = remove_background_from_any_image(right_source_bytes, cropped_right_upload.name)
                if cutout is not None:
                    st.session_state["cropped_right_transparent"] = cutout
                    st.session_state.p2_cutout = cutout
                    st.session_state["reference_right_cutout"] = cutout
                    st.success("Right player background removed. This transparent cutout is now selected for the thumbnail.")
                else:
                    st.error(cutout_error or "Could not remove the right background.")
            if st.session_state.get("cropped_right_transparent") is not None:
                right_transparent = st.session_state["cropped_right_transparent"]
                st.image(right_transparent, caption="RIGHT player — transparent preview", use_container_width=True)
                right_transparent_buffer = io.BytesIO()
                right_transparent.save(right_transparent_buffer, format="PNG", optimize=False)
                st.download_button(
                    "⬇️ Download RIGHT transparent PNG",
                    data=right_transparent_buffer.getvalue(),
                    file_name="right_player_transparent.png",
                    mime="image/png",
                    use_container_width=True,
                    key="download_cropped_right_transparent_v1",
                )

    st.subheader("6. Reference Thumbnail Player Extractor")
    st.caption(
        "Upload another cricket thumbnail, crop around each player, and create transparent PNG cutouts using cached local U2NETP when available, with a fast OpenCV fallback. "
        "This avoids Gemini API calls. Players are processed one at a time to reduce memory use and help avoid Render 502 disconnects. "
        "Segmentation may leave text or graphics that touch/overlap the player, and it cannot reconstruct hidden pixels. "
        "Use only images you have permission to reuse. Successful extractions are cached for 30 days."
    )
    st.markdown("**Option A — Load reference thumbnail from an image URL**")
    reference_thumbnail_url = st.text_input(
        "Reference thumbnail image URL",
        placeholder="https://example.com/cricket-thumbnail.jpg",
        key="reference_thumbnail_image_url",
        help="Use a direct, publicly accessible image URL ending in JPG, PNG, or WebP. A normal webpage URL may not work.",
    )
    if st.button("🌐 Load thumbnail from URL", use_container_width=True, key="load_reference_thumbnail_url"):
        if not reference_thumbnail_url.strip():
            st.warning("Paste a direct thumbnail image URL first.")
        else:
            with st.spinner("Fetching reference thumbnail from URL…"):
                fetched_reference = fetch_online_image(reference_thumbnail_url.strip())
            if fetched_reference is None:
                st.error("Could not load that URL as an image. Use a direct, public JPG/PNG/WebP image URL, not a webpage or a private/expired link.")
            else:
                ref_buffer = io.BytesIO()
                fetched_reference.convert("RGB").save(ref_buffer, format="PNG")
                st.session_state["reference_thumbnail_url_bytes"] = ref_buffer.getvalue()
                st.session_state["reference_thumbnail_url_name"] = "reference_thumbnail_from_url.png"
                st.session_state["reference_thumbnail_url_loaded"] = reference_thumbnail_url.strip()
                st.session_state["reference_thumbnail_hash"] = None
                st.session_state["reference_left_cutout"] = None
                st.session_state["reference_right_cutout"] = None
                st.session_state["reference_cutout_matchup_key"] = None
                st.session_state["reference_cutouts_origin"] = None
                if st.session_state.get("p1_cutout_source") == "reference_thumbnail":
                    st.session_state.p1_cutout = None
                    st.session_state["p1_cutout_source"] = None
                if st.session_state.get("p2_cutout_source") == "reference_thumbnail":
                    st.session_state.p2_cutout = None
                    st.session_state["p2_cutout_source"] = None
                st.success("Reference thumbnail loaded. Adjust the crop sliders, then extract both players.")

    st.markdown("**Option B — Upload a reference thumbnail file**")
    reference_thumbnail = st.file_uploader(
        "Upload reference thumbnail (PNG/JPG/WebP)",
        type=["png", "jpg", "jpeg", "webp"],
        key="reference_thumbnail_upload",
    )
    # Uploaded file takes priority. Otherwise use the image previously loaded from URL.
    if reference_thumbnail is not None:
        reference_thumbnail_bytes = reference_thumbnail.getvalue()
        reference_thumbnail_name = reference_thumbnail.name
        # Keep uploaded bytes in this user's Streamlit session so normal reruns and
        # transient websocket reconnects don't discard the source image.
        st.session_state["reference_thumbnail_uploaded_bytes"] = reference_thumbnail_bytes
        st.session_state["reference_thumbnail_uploaded_name"] = reference_thumbnail_name
    else:
        reference_thumbnail_bytes = st.session_state.get("reference_thumbnail_url_bytes")
        reference_thumbnail_name = st.session_state.get("reference_thumbnail_url_name", "reference_thumbnail_from_url.png")
        if reference_thumbnail_bytes is None:
            reference_thumbnail_bytes = st.session_state.get("reference_thumbnail_uploaded_bytes")
            reference_thumbnail_name = st.session_state.get("reference_thumbnail_uploaded_name", "reference_thumbnail_recovered.png")

    use_reference_cutouts = st.checkbox(
        "Use extracted reference players in my PREET SPORTS thumbnail",
        value=True,
        key="use_reference_cutouts_checkbox",
    )
    if reference_thumbnail_bytes is not None:
        ref_bytes = reference_thumbnail_bytes
        ref_hash = hashlib.sha1(ref_bytes).hexdigest()
        if st.session_state.get("reference_thumbnail_hash") != ref_hash:
            st.session_state["reference_thumbnail_hash"] = ref_hash
            st.session_state["reference_left_cutout"] = None
            st.session_state["reference_right_cutout"] = None
            st.session_state["reference_cutout_matchup_key"] = None
            st.session_state["reference_cutouts_origin"] = None
            if st.session_state.get("p1_cutout_source") == "reference_thumbnail":
                st.session_state.p1_cutout = None
                st.session_state["p1_cutout_source"] = None
            if st.session_state.get("p2_cutout_source") == "reference_thumbnail":
                st.session_state.p2_cutout = None
                st.session_state["p2_cutout_source"] = None
        try:
            with Image.open(io.BytesIO(ref_bytes)) as ref_opened:
                ref_image = ref_opened.convert("RGB")
            st.image(ref_image, caption=f"Reference thumbnail: {ref_image.width} × {ref_image.height}", use_container_width=True)
            st.caption("Adjust each crop so it contains one player as fully as possible. Avoid including the LIVE text and team banners.")
            crop_left_col, crop_right_col = st.columns(2)
            with crop_left_col:
                st.markdown("**Left player crop**")
                # Reference-thumbnail defaults: keep the left player on the left third,
                # exclude most of the central LIVE/text area, and include the full torso.
                # Versioned widget keys reset previously saved slider positions on deploy.
                left_x_range = st.slider("Horizontal range (%) — left", 0, 100, (0, 43), key="ref_left_x_range_v3")
                left_y_range = st.slider("Vertical range (%) — left", 0, 100, (8, 100), key="ref_left_y_range_v3")
            with crop_right_col:
                st.markdown("**Right player crop**")
                right_x_range = st.slider("Horizontal range (%) — right", 0, 100, (50, 100), key="ref_right_x_range_v3")
                right_y_range = st.slider("Vertical range (%) — right", 0, 100, (8, 100), key="ref_right_y_range_v3")

            def _reference_crop(image, x_range, y_range):
                x0 = int(image.width * x_range[0] / 100)
                x1 = int(image.width * x_range[1] / 100)
                y0 = int(image.height * y_range[0] / 100)
                y1 = int(image.height * y_range[1] / 100)
                x1 = max(x0 + 1, min(image.width, x1))
                y1 = max(y0 + 1, min(image.height, y1))
                return image.crop((x0, y0, x1, y1))

            ref_left_crop = _reference_crop(ref_image, left_x_range, left_y_range)
            ref_right_crop = _reference_crop(ref_image, right_x_range, right_y_range)
            crop_prev1, crop_prev2 = st.columns(2)
            with crop_prev1:
                st.image(ref_left_crop, caption="Left crop preview", use_container_width=True)
                left_crop_buffer = io.BytesIO()
                ref_left_crop.save(left_crop_buffer, format="PNG")
                st.download_button(
                    "Download LEFT raw crop (background included)",
                    data=left_crop_buffer.getvalue(),
                    file_name="reference_left_crop.png",
                    mime="image/png",
                    use_container_width=True,
                    key="download_ref_left_crop_only",
                )
            with crop_prev2:
                st.image(ref_right_crop, caption="Right crop preview", use_container_width=True)
                right_crop_buffer = io.BytesIO()
                ref_right_crop.save(right_crop_buffer, format="PNG")
                st.download_button(
                    "Download RIGHT raw crop (background included)",
                    data=right_crop_buffer.getvalue(),
                    file_name="reference_right_crop.png",
                    mime="image/png",
                    use_container_width=True,
                    key="download_ref_right_crop_only",
                )

            extract_both_clicked = st.button(
                "✂️ Extract BOTH players & apply to thumbnail",
                use_container_width=True,
                type="primary",
                key="extract_reference_both_apply",
                help="Runs face-guided local segmentation, saves transparent PNG cutouts, and assigns them directly to the left/right thumbnail slots. No manual PNG download is needed.",
            )
            extract_col1, extract_col2 = st.columns(2)
            with extract_col1:
                extract_left_clicked = st.button("✂️ Extract LEFT only", use_container_width=True, key="extract_reference_left")
            with extract_col2:
                extract_right_clicked = st.button("✂️ Extract RIGHT only", use_container_width=True, key="extract_reference_right")

            def _crop_jpeg_bytes(crop):
                # Convert crop to a compact local-model input. No API request is made.
                crop_rgb = crop.convert("RGB")
                max_side = int(os.environ.get("PREET_GRABCUT_MAX_SIDE", "512"))
                max_side = max(320, min(max_side, 640))
                if max(crop_rgb.size) > max_side:
                    scale = max_side / max(crop_rgb.size)
                    crop_rgb = crop_rgb.resize((max(1, int(crop_rgb.width * scale)), max(1, int(crop_rgb.height * scale))), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                crop_rgb.save(buf, format="JPEG", quality=84, optimize=False)
                return buf.getvalue()

            def _queue_reference_extraction(side, crop):
                # Persist compact crop bytes in Session State. Process one crop per
                # Streamlit run to lower peak RAM and avoid a single long request
                # that can cause a Render 502/disconnect.
                return {
                    "side": side,
                    "source_bytes": _crop_jpeg_bytes(crop),
                    "filename": f"reference_{side}_player.jpg",
                    "matchup_key": (normalize_team_name(team1), normalize_team_name(team2)),
                }

            if extract_both_clicked:
                st.session_state["_reference_pending_extractions"] = [
                    _queue_reference_extraction("left", ref_left_crop),
                    _queue_reference_extraction("right", ref_right_crop),
                ]
                st.session_state["_reference_extraction_messages"] = []
                st.rerun()
            elif extract_left_clicked:
                st.session_state["_reference_pending_extractions"] = [
                    _queue_reference_extraction("left", ref_left_crop)
                ]
                st.session_state["_reference_extraction_messages"] = []
                st.rerun()
            elif extract_right_clicked:
                st.session_state["_reference_pending_extractions"] = [
                    _queue_reference_extraction("right", ref_right_crop)
                ]
                st.session_state["_reference_extraction_messages"] = []
                st.rerun()

            # Handle exactly one local GrabCut segmentation per request. After each inference,
            # save its result in session state and rerun so temporary arrays are released
            # before the next player or 4K composition.
            pending_extractions = st.session_state.get("_reference_pending_extractions", [])
            if pending_extractions:
                task = pending_extractions[0]
                st.session_state["_reference_pending_extractions"] = pending_extractions[1:]
                side = task["side"]
                with st.spinner(
                    f"Removing {side} player background… using cached local U2NETP if installed, otherwise the fast OpenCV fallback."
                ):
                    cutout, extract_error = remove_background_from_any_image(
                        task["source_bytes"], task.get("filename", f"reference_{side}_player.jpg")
                    )

                messages = st.session_state.setdefault("_reference_extraction_messages", [])
                if cutout is not None:
                    st.session_state["reference_cutout_matchup_key"] = tuple(
                        task.get("matchup_key") or (normalize_team_name(team1), normalize_team_name(team2))
                    )
                    st.session_state["reference_cutouts_origin"] = "reference_thumbnail"
                    if side == "left":
                        st.session_state["reference_left_cutout"] = cutout
                        st.session_state.p1_cutout = cutout
                        st.session_state["p1_cutout_source"] = "reference_thumbnail"
                        st.session_state.p1_ai_front = None
                        st.session_state.p1_ai_source_hash = None
                    else:
                        st.session_state["reference_right_cutout"] = cutout
                        st.session_state.p2_cutout = cutout
                        st.session_state["p2_cutout_source"] = "reference_thumbnail"
                        st.session_state.p2_ai_front = None
                        st.session_state.p2_ai_source_hash = None
                    messages.append(f"{side.title()} player extracted and applied to the thumbnail for {task.get('matchup_key') or 'the current matchup'}.")
                else:
                    messages.append(f"{side.title()} player extraction failed: {extract_error or 'Unknown local segmentation error.'}")

                # Release local inference/result buffers before next queued crop or
                # the 4K renderer. No neural model session is needed.
                del cutout
                gc.collect()
                if st.session_state.get("_reference_pending_extractions"):
                    st.rerun()
                # Run one more clean pass before rendering the large 4K thumbnail.
                st.rerun()

            for extraction_message in st.session_state.get("_reference_extraction_messages", []):
                if "extraction failed:" in extraction_message.lower():
                    st.error(extraction_message)
                else:
                    st.success(extraction_message)

            saved_left, saved_right = st.columns(2)
            with saved_left:
                if st.session_state.get("reference_left_cutout") is not None:
                    st.image(st.session_state["reference_left_cutout"], caption="Extracted left player", use_container_width=True)
                    left_png = io.BytesIO()
                    st.session_state["reference_left_cutout"].save(left_png, format="PNG")
                    st.download_button("Download left cutout PNG", left_png.getvalue(), "reference_left_player.png", "image/png", use_container_width=True, key="download_ref_left_cutout")
            with saved_right:
                if st.session_state.get("reference_right_cutout") is not None:
                    st.image(st.session_state["reference_right_cutout"], caption="Extracted right player", use_container_width=True)
                    right_png = io.BytesIO()
                    st.session_state["reference_right_cutout"].save(right_png, format="PNG")
                    st.download_button("Download right cutout PNG", right_png.getvalue(), "reference_right_player.png", "image/png", use_container_width=True, key="download_ref_right_cutout")

            if st.button("🧹 Clear extracted reference players", key="clear_reference_cutouts"):
                st.session_state["reference_left_cutout"] = None
                st.session_state["reference_right_cutout"] = None
                st.session_state["reference_cutout_matchup_key"] = None
                st.session_state["reference_cutouts_origin"] = None
                if st.session_state.get("p1_cutout_source") == "reference_thumbnail":
                    st.session_state.p1_cutout = None
                    st.session_state["p1_cutout_source"] = None
                if st.session_state.get("p2_cutout_source") == "reference_thumbnail":
                    st.session_state.p2_cutout = None
                    st.session_state["p2_cutout_source"] = None
                st.rerun()
        except Exception as exc:
            st.error(f"Could not read the reference thumbnail: {exc}")
    else:
        use_reference_cutouts = False
        st.caption("Load a thumbnail using the URL option above or upload an image file to enable player extraction.")

    st.subheader("7. Background (optional override)")
    stadium_url = st.text_input(
        "Custom Stadium Background URL",
        value="",
        placeholder="Leave blank to use the built-in cricket stadium photo",
        key="stadium_background_url",
    )
    bg_file = st.file_uploader("Or upload your own 16:9 stadium background", type=["png", "jpg", "jpeg", "webp"])
    st.subheader("8. AI Front-Facing Pose Conversion — Canva / Replicate")
    st.info(
        "Canva or Replicate can edit the reference player photo to a front-facing pose. The model may still alter facial details, "
        "so inspect the result before exporting."
    )
    st.markdown("**Canva AI reference-photo editing**")
    st.caption(
        "When connected, the front-pose buttons below use Canva's official MCP generate-image tool with the uploaded photo as a reference. "
        "One conversion launches one Canva image-edit job and uses your account's applicable AI allowance. Canva Free has access to image tools, "
        "but daily/monthly AI limits are controlled by Canva."
    )
    canva_client_id = str(os.environ.get("CANVA_CLIENT_ID", "")).strip()
    canva_client_secret = str(os.environ.get("CANVA_CLIENT_SECRET", "")).strip()
    canva_redirect_uri = _canva_oauth_redirect_uri()
    if st.session_state.get("canva_access_token"):
        st.success("Canva is connected for this browser session. The front-pose buttons will use Canva first.")
        if st.button("Disconnect Canva for this session", key="canva_disconnect_session"):
            for token_key in ("canva_access_token", "canva_refresh_token", "canva_token_expiry"):
                st.session_state.pop(token_key, None)
            st.session_state["canva_oauth_error"] = ""
            st.rerun()
    elif not canva_client_id or not canva_client_secret:
        st.warning(
            "To enable Canva, create an app at canva.com/developers, enable **Canva MCP** and **Canva REST APIs** under Outside Canva, "
            "enable the asset:read and asset:write scopes, and add CANVA_CLIENT_ID, CANVA_CLIENT_SECRET, and CANVA_REDIRECT_URI to Render Environment. "
            "Register the same redirect URL in Canva Developer Portal. Never paste the client secret into this page or commit it to GitHub."
        )
        st.markdown("[Open Canva Developer Portal](https://www.canva.com/developers/)")
    elif not canva_redirect_uri:
        st.warning("Set CANVA_REDIRECT_URI to this app's public Render URL and register the identical URL in Canva Developer Portal.")
    else:
        cached_auth_url = st.session_state.get("canva_authorize_url")
        cached_auth_created = float(st.session_state.get("canva_authorize_created_at", 0) or 0)
        if not cached_auth_url or time.time() - cached_auth_created > 600:
            cached_auth_url, auth_error = _canva_authorization_link()
            if cached_auth_url:
                st.session_state["canva_authorize_url"] = cached_auth_url
                st.session_state["canva_authorize_created_at"] = time.time()
            else:
                st.session_state["canva_oauth_error"] = auth_error
        if st.session_state.get("canva_authorize_url"):
            st.link_button("🔗 Connect Canva AI", st.session_state["canva_authorize_url"], use_container_width=True)
            st.caption("Approve access in Canva, then continue from the tab Canva redirects back to this app.")
    if st.session_state.get("canva_oauth_error"):
        st.error(str(st.session_state["canva_oauth_error"]))
    if st.session_state.get("canva_pose_quality_note"):
        st.warning(str(st.session_state["canva_pose_quality_note"]))
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
            st.session_state["p1_cutout_source"] = "captain_url"
    except Exception:
        pass
if st.session_state.p2_cutout is None and right_captain_url.strip():
    try:
        initial_right_url = resolve_player_image_url(right_captain_url.strip())
        initial_right_img = fetch_online_image(initial_right_url) if initial_right_url else None
        if initial_right_img is not None:
            st.session_state.p2_cutout = initial_right_img
            st.session_state["p2_cutout_source"] = "captain_url"
    except Exception:
        pass

# Reference-thumbnail cutouts are tied to the team pair present when extracted.
# This prevents a cutout from a previous match (e.g. ZIM vs AFG) being silently reused
# after the user changes the labels to a different match (e.g. IND-W vs ZIM-W).
current_matchup_key = (normalize_team_name(team1), normalize_team_name(team2))
reference_origin = st.session_state.get("reference_cutouts_origin")
reference_pair_key = st.session_state.get("reference_cutout_matchup_key")
if reference_origin is None and (st.session_state.get("reference_left_cutout") is not None or st.session_state.get("reference_right_cutout") is not None):
    # Legacy session from older app versions: without a recorded team pair, treat as unverified.
    reference_origin = "legacy_unverified_reference"
reference_pair_matches = tuple(reference_pair_key or ()) == current_matchup_key
reference_cutouts_usable = (
    reference_origin == "manual_cropped_upload"
    or (reference_origin == "reference_thumbnail" and reference_pair_matches)
)
if reference_origin in ("reference_thumbnail", "legacy_unverified_reference") and not reference_pair_matches:
    st.warning(
        "Saved reference-player cutouts do not match the current team names. They will not be reused automatically. "
        "Load a reference thumbnail for this match and extract again, or fetch the correct player image URLs."
    )

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
elif use_reference_cutouts and reference_cutouts_usable and st.session_state.get("reference_left_cutout") is not None:
    p1_final = st.session_state["reference_left_cutout"]
elif custom_p1 and left_is_cutout:
    p1_final = Image.open(io.BytesIO(custom_p1.getvalue())).convert("RGBA")
elif st.session_state.p1_cutout is not None and not (
    not reference_pair_matches
    and (
        st.session_state.get("p1_cutout_source") == "reference_thumbnail"
        or reference_origin == "legacy_unverified_reference"
    )
):
    p1_final = st.session_state.p1_cutout
elif c1_info.get("player_png"):
    p1_final = fetch_online_image(c1_info["player_png"])
else:
    p1_final = None

if custom_p2 and st.session_state.p2_ai_front is not None and st.session_state.p2_ai_source_hash == right_upload_hash:
    p2_final = st.session_state.p2_ai_front
elif use_reference_cutouts and reference_cutouts_usable and st.session_state.get("reference_right_cutout") is not None:
    p2_final = st.session_state["reference_right_cutout"]
elif custom_p2 and right_is_cutout:
    p2_final = Image.open(io.BytesIO(custom_p2.getvalue())).convert("RGBA")
elif st.session_state.p2_cutout is not None and not (
    not reference_pair_matches
    and (
        st.session_state.get("p2_cutout_source") == "reference_thumbnail"
        or reference_origin == "legacy_unverified_reference"
    )
):
    p2_final = st.session_state.p2_cutout
elif c2_info.get("player_png"):
    p2_final = fetch_online_image(c2_info["player_png"])
else:
    p2_final = None

# Optional correction for reference thumbnails whose player order is reversed.
if swap_player_photos:
    p1_final, p2_final = p2_final, p1_final


def _pose_source_png_bytes(image):
    """Serialize a selected portrait in a stable, hashable PNG representation."""
    if image is None:
        return None
    buffer = io.BytesIO()
    image.convert("RGBA").save(buffer, format="PNG", optimize=False, compress_level=1)
    return buffer.getvalue()


def _pose_source_hash(image):
    payload = _pose_source_png_bytes(image)
    return hashlib.sha1(payload).hexdigest() if payload else None


# These buttons work with the portraits already selected for the thumbnail, including
# ICC auto-fetched images. They are separate from the optional manual-upload controls above.
st.markdown("**Front-face the current thumbnail portraits**")
st.caption(
    "Priority: connected Canva MCP reference-photo editing (uses Canva AI allowance, one generation job per click); otherwise Replicate if configured; "
    "otherwise the original portrait is retained. Canva MCP's documented result is a media reference, and the current public asset endpoint may return only a preview thumbnail, "
    "so inspect the output quality before using it for a 4K thumbnail. The original portrait is retained if conversion fails."
)
pose_left_col, pose_right_col = st.columns(2)
with pose_left_col:
    convert_selected_left = st.button(
        "🎯 Front-face CURRENT LEFT portrait", use_container_width=True, key="convert_selected_left_front_v1"
    )
with pose_right_col:
    convert_selected_right = st.button(
        "🎯 Front-face CURRENT RIGHT portrait", use_container_width=True, key="convert_selected_right_front_v1"
    )

if convert_selected_left:
    if p1_final is None:
        st.warning("No LEFT portrait is currently selected. Fetch or choose an image first.")
    else:
        source_bytes = _pose_source_png_bytes(p1_final)
        source_hash = hashlib.sha1(source_bytes).hexdigest()
        with st.spinner("Creating a front-facing LEFT portrait with the configured image-edit model…"):
            edited, error = convert_player_to_front_facing(source_bytes, "selected_left_player.png", "left")
        if edited is not None:
            st.session_state["p1_selected_pose_front"] = edited
            st.session_state["p1_selected_pose_source_hash"] = source_hash
            st.success("Front-facing LEFT portrait generated. Review the preview before downloading.")
        else:
            st.error(error)

if convert_selected_right:
    if p2_final is None:
        st.warning("No RIGHT portrait is currently selected. Fetch or choose an image first.")
    else:
        source_bytes = _pose_source_png_bytes(p2_final)
        source_hash = hashlib.sha1(source_bytes).hexdigest()
        with st.spinner("Creating a front-facing RIGHT portrait with the configured image-edit model…"):
            edited, error = convert_player_to_front_facing(source_bytes, "selected_right_player.png", "right")
        if edited is not None:
            st.session_state["p2_selected_pose_front"] = edited
            st.session_state["p2_selected_pose_source_hash"] = source_hash
            st.success("Front-facing RIGHT portrait generated. Review the preview before downloading.")
        else:
            st.error(error)

# Apply cached generated portraits only to the exact source image used to create them.
# When the team or captain changes, the old AI edit will not silently replace the new player.
if p1_final is not None and st.session_state.get("p1_selected_pose_source_hash") == _pose_source_hash(p1_final):
    p1_final = st.session_state.get("p1_selected_pose_front") or p1_final
if p2_final is not None and st.session_state.get("p2_selected_pose_source_hash") == _pose_source_hash(p2_final):
    p2_final = st.session_state.get("p2_selected_pose_front") or p2_final

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
    bool(swap_player_photos),
    str(channel_title),
    str(match_status),
    str(match_badge),
    str(commentary_text),
    str(design_style),
    bool(enlarge_live_title),
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
            design_style=design_style,
            live_scale=live_scale,
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
    st.subheader("Live 4K Preview — Updated Match Talk Layout")
    # Send a lightweight preview to the browser; the download remains full 4K.
    preview_image = result.resize((1280, 720), Image.Resampling.LANCZOS)
    st.image(preview_image, use_container_width=True)
    st.caption(
        f"Preview: 1280 × 720 px for speed. Download: {result.width} × {result.height} px PNG (4K UHD). Keep the lower-right corner clear for YouTube’s duration badge."
    )

    st.download_button(
        label="⬇️ Download 4K Thumbnail (3840 × 2160 PNG)",
        data=output_png,
        file_name=f"{normalize_team_name(team1).replace(' ', '_')}_vs_{normalize_team_name(team2).replace(' ', '_')}_4K.png",
        mime="image/png",
        use_container_width=True,
    )

    st.markdown("**Canva AI front-pose finishing step**")
    st.caption(
        "When both player portraits are inserted, open your saved Canva AI thread to edit the completed thumbnail. "
        "The original 4K download above stays unchanged. The browser cannot automatically attach that PNG to the Canva thread, "
        "so upload the downloaded PNG in Canva AI and paste the instruction below."
    )
    if p1_final is not None and p2_final is not None:
        st.success("Both player portraits are present. Your thumbnail is ready for the Canva AI front-pose step.")
        st.link_button(
            "🎨 Open Canva AI — Front-Face Both Players",
            "https://www.canva.com/ai/thread/d6f8e609-0db7-41ea-99df-c35972f16edc",
            use_container_width=True,
        )
        front_pose_prompt = (
            f"Edit this uploaded {channel_title} {team1} vs {team2} cricket YouTube thumbnail. Change BOTH visible players only: "
            f"the LEFT player representing {team1} and the RIGHT player representing {team2} should face directly toward the camera, "
            "with both eyes visible and shoulders nearly square. Keep each same person and preserve their identity, face, age, skin tone, "
            "hair, facial hair, expression, body build, exact team jersey colours, patterns, crests and sponsor logos. Keep both players "
            "in the exact same left/right positions and at similar scale; show the full head, hair and shoulders without cropping. "
            f"Do NOT change anything else: preserve the {channel_title} branding, {match_status}, {match_badge}, {commentary_text}, "
            f"{high_ctr_team_label(team1)} and {high_ctr_team_label(team2)} team labels, flags, stadium, crowd, grass, lighting, colours, "
            "typography, borders, diagonal panels, spacing and composition. Do not redraw, move, misspell, remove or replace any text, "
            "flags, badges, or logos. Do not add people or objects. Only adjust the two players' poses. Keep the same 16:9 layout and "
            "make the result photorealistic."
        )
        st.text_area(
            "Prompt to paste into Canva AI after uploading the downloaded thumbnail",
            value=front_pose_prompt,
            height=190,
            key="canva_browser_frontpose_prompt",
            disabled=True,
        )
    else:
        st.info("Select or fetch both player portraits first. The Canva AI front-pose link appears when both players are in the thumbnail.")

st.divider()
st.caption("LOCAL-FIRST: player selection, cached local U2NETP/OpenCV background removal, composition, and 3840 × 2160 PNG export run on the app server. Use the Canva AI browser link below the preview to manually upload the completed thumbnail and request front-facing poses; the app does not send your thumbnail to Canva automatically. AI may alter facial identity or design details.")
