"""OAuth 2.0 (3-legged) helpers for the LinkedIn plugin.

Implements the browser flow so a user can connect an account from the settings
page instead of pasting a token by hand:

1. `build_authorize_url()` sends the browser to LinkedIn.
2. LinkedIn redirects back to the plugin callback with `code` and `state`.
3. `exchange_code()` swaps the code for an access token.

`state` is a single-use nonce written to a small JSON file with a short TTL, so
a stale or replayed callback cannot overwrite an account's credentials.
"""
from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
STATE_FILE_NAME = ".oauth_state.json"
STATE_TTL_SECONDS = 900
DEFAULT_REDIRECT_PATH = "api/plugins/linkedin/linkedin_oauth_callback"


def authorize_url(client_id: str, redirect_uri: str, scopes: list[str], state: str) -> str:
    """Build the LinkedIn authorization URL."""
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def _state_path(plugin_dir: str | Path) -> Path:
    return Path(plugin_dir) / STATE_FILE_NAME


def _load_states(plugin_dir: str | Path) -> dict:
    path = _state_path(plugin_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_states(plugin_dir: str | Path, states: dict) -> None:
    path = _state_path(plugin_dir)
    try:
        path.write_text(json.dumps(states, indent=2), encoding="utf-8")
    except OSError:
        pass


def create_state(plugin_dir: str | Path, account: str, redirect_uri: str, scopes: list[str]) -> str:
    """Issue a single-use state nonce bound to one account."""
    now = int(time.time())
    states = {k: v for k, v in _load_states(plugin_dir).items() if int(v.get("created", 0)) > now - STATE_TTL_SECONDS}
    token = secrets.token_urlsafe(24)
    states[token] = {
        "account": account,
        "redirect_uri": redirect_uri,
        "scopes": scopes,
        "created": now,
    }
    _write_states(plugin_dir, states)
    return token


def consume_state(plugin_dir: str | Path, token: str) -> dict | None:
    """Validate and remove a state nonce. Returns its payload or None."""
    if not token:
        return None
    states = _load_states(plugin_dir)
    entry = states.pop(str(token), None)
    _write_states(plugin_dir, states)
    if not isinstance(entry, dict):
        return None
    created = int(entry.get("created", 0))
    if created <= int(time.time()) - STATE_TTL_SECONDS:
        return None
    return entry


def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    timeout: int = 30,
) -> dict:
    """Exchange an authorization code for an access token.

    Returns `{ok, status, access_token, expires_in, error}`. The code and client
    secret are never echoed in the result.
    """
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except (URLError, OSError) as exc:
        return {"ok": False, "status": 0, "error": f"Token exchange failed: {exc}"}

    try:
        parsed = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        parsed = {}

    token = str(parsed.get("access_token") or "").strip()
    if not token:
        message = str(parsed.get("error_description") or parsed.get("error") or raw or "").strip()
        return {
            "ok": False,
            "status": status,
            "error": message[:300] or f"LinkedIn returned HTTP {status} without an access token.",
        }
    return {
        "ok": True,
        "status": status,
        "access_token": token,
        "expires_in": parsed.get("expires_in"),
        "refresh_token": parsed.get("refresh_token", ""),
    }


def resolve_redirect_uri(request_root: str, override: str = "") -> str:
    """Redirect URI the browser should return to, and register at LinkedIn."""
    configured = str(override or "").strip()
    if configured:
        return configured
    return f"{str(request_root or '').rstrip('/')}/{DEFAULT_REDIRECT_PATH}"
