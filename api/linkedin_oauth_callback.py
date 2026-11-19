"""LinkedIn OAuth callback for the plugin settings page.

LinkedIn redirects the browser here with `?code=...&state=...`. This is a real
browser navigation, so it cannot carry a CSRF token: the handler allows GET and
disables CSRF, but keeps session auth so only a logged-in operator can finish a
connect. The `state` nonce is single-use and bound to one account.

On success the token is written to that account's config and a small HTML page
tells the operator to close the tab. Secrets are never rendered.
"""
from __future__ import annotations

import re
from html import escape, unescape

from helpers.api import ApiHandler, Request, Response

import usr.plugins.linkedin.helpers.config as cfg
from usr.plugins.linkedin.helpers.linkedin_oauth import consume_state, exchange_code


def _plain(text: str) -> str:
    """LinkedIn sends HTML-entity encoded text; decode once so escape() is not doubled."""
    return unescape(str(text or "")).strip()


def _scope_hint(description: str) -> str:
    lowered = description.lower()
    if "unauthorized_scope_error" in lowered or "not authorized for your application" in lowered:
        match = re.search(r'scope\s+["\']?([A-Za-z0-9_.:-]+)["\']?\s+is not authorized', description, re.I)
        named = match.group(1) if match else ""
        lead = (
            f" The scope '{named}' is not enabled for the LinkedIn app behind this client id."
            if named
            else " That scope is not enabled for the LinkedIn app behind this client id."
        )
        return (
            lead
            + " Remove it from this account's Scopes, or add the matching product in the "
            "LinkedIn developer portal (openid/profile need 'Sign In with LinkedIn using "
            "OpenID Connect'; organization accounts do not need openid at all). "
            "Note: r_basicprofile is a retired legacy scope and is usually rejected."
        )
    if "invalid_client" in lowered or "redirect_uri" in lowered:
        return (
            " Check that this app's authorized redirect URL exactly matches the Redirect URI "
            "shown in the settings page."
        )
    return ""


class LinkedInOAuthCallback(ApiHandler):
    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET"]

    @classmethod
    def requires_csrf(cls) -> bool:
        # A LinkedIn redirect is a top-level browser navigation with no CSRF token.
        return False

    async def process(self, input: dict, request: Request) -> Response:
        args = request.args if request is not None else {}
        error = _plain(args.get("error"))
        error_description = _plain(args.get("error_description"))
        code = str(args.get("code") or "").strip()
        state_token = str(args.get("state") or "").strip()

        if error:
            detail = f"{error}: {error_description}".strip(": ")
            return self._page(
                False,
                "LinkedIn refused the authorization",
                detail + _scope_hint(detail),
            )
        if not code or not state_token:
            return self._page(False, "Missing authorization data", "The callback arrived without a code or state value.")

        state = consume_state(_plugin_dir(), state_token)
        if not state:
            return self._page(
                False,
                "This connect link expired or was already used",
                "Start the connection again from the LinkedIn settings page.",
            )

        account = str(state.get("account") or "").strip()
        redirect_uri = str(state.get("redirect_uri") or "").strip()
        current = cfg.load_config()
        names = cfg.get_profile_names(current)
        if account not in names:
            return self._page(False, "Unknown account", f"The account '{account}' no longer exists.")

        linkedin = cfg.get_profile_config(current, account)
        client_id = str(linkedin.get("client_id") or "").strip()
        client_secret = str(linkedin.get("client_secret") or "").strip()
        if not client_id or not client_secret:
            return self._page(
                False,
                "LinkedIn app credentials are missing",
                f"Add a client id and client secret for the '{account}' account, then start again.",
            )

        exchanged = exchange_code(
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
            timeout=int(linkedin.get("timeout_seconds") or 30),
        )
        if not exchanged.get("ok"):
            return self._page(
                False,
                "Token exchange failed",
                str(exchanged.get("error") or "LinkedIn did not return an access token."),
            )

        try:
            saved = _persist_token(current, account, exchanged, state)
        except Exception as exc:  # noqa: BLE001 - surface any storage failure to the page
            return self._page(False, "Could not save the token", str(exc))

        return self._page(
            True,
            "LinkedIn account connected",
            f"Saved the access token for '{escape(account)}'."
            f" Token preview: {saved}."
            " Close this tab and reload the plugin settings.",
        )

    def _page(self, ok: bool, title: str, detail: str) -> Response:
        color = "#0A66C2" if ok else "#7a2b2b"
        body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{escape(title)}</title></head>
<body style="font-family: system-ui, sans-serif; background:#121212; color:#e8e8e8; padding:40px;">
  <div style="max-width:640px; margin:0 auto; border:1px solid #333; border-radius:8px; padding:24px;">
    <h1 style="font-size:18px; margin:0 0 12px; color:{color};">{escape(title)}</h1>
    <p style="font-size:13px; line-height:1.6; color:#c9c9c9;">{escape(detail)}</p>
  </div>
</body></html>"""
        return Response(body, status=200 if ok else 400, mimetype="text/html")


def _plugin_dir() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parent.parent)


def _persist_token(current: dict, account: str, exchanged: dict, state: dict) -> str:
    """Write the fresh token (and granted scopes) into one account only."""
    import copy

    from usr.plugins.linkedin.helpers.sanitize import mask_secret

    merged = copy.deepcopy(current)
    profiles = merged.setdefault("profiles", {})
    entry = profiles.get(account)
    if not isinstance(entry, dict):
        entry = {"label": account, "linkedin": {}}
        profiles[account] = entry
    linkedin = entry.setdefault("linkedin", {})
    linkedin["access_token"] = exchanged.get("access_token", "")
    refresh = str(exchanged.get("refresh_token") or "").strip()
    if refresh:
        linkedin["refresh_token"] = refresh
    scopes = state.get("scopes") or []
    if scopes:
        linkedin["scopes"] = list(scopes)
    cfg.persist_config(cfg.sync_shared_defaults(merged))
    return mask_secret(str(exchanged.get("access_token") or ""))
