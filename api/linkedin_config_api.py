"""LinkedIn plugin config API.

Supports whole-config get/set plus explicit per-account CRUD so a single plugin
installation can hold many LinkedIn credentials (apps, members, and pages).
"""
from __future__ import annotations

import copy
import os
import re

try:
    from helpers.api import ApiHandler  # type: ignore
except Exception:  # pragma: no cover
    class ApiHandler:
        async def handle(self, **kwargs):
            raise NotImplementedError

from usr.plugins.linkedin.helpers.config import (
    get_profile_config,
    get_profile_names,
    list_accounts,
    load_config,
    load_schema,
    mask_config,
    persist_config,
    profile_target,
    sync_shared_defaults,
)
from usr.plugins.linkedin.helpers.linkedin_auth import LinkedInAuthHelper

SECRET_FIELDS = ("access_token", "client_secret", "refresh_token")

# Legacy LinkedIn scopes that are retired. Requesting one makes LinkedIn reject
# the entire authorization request with unauthorized_scope_error.
RETIRED_SCOPES = ("r_basicprofile", "r_liteprofile", "r_emailaddress")

# Non-secret settings that legitimately come from the Runtime tab and apply to
# every account. Secrets and identity fields (tokens, person URN, organization
# URNs) must never propagate between accounts.
ACCOUNT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,63}$")


def _looks_masked(value: object) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return bool(stripped) and all(ch == '*' for ch in stripped[:-4]) and len(stripped) >= 4


def _preserve_masked_secrets(existing: dict, incoming: dict) -> dict:
    """Keep the stored secret when the UI sends back its own masked preview."""
    if not isinstance(incoming, dict):
        return incoming
    result = dict(incoming)
    for key, value in list(result.items()):
        if key in SECRET_FIELDS and _looks_masked(value):
            prev = existing.get(key) if isinstance(existing, dict) else None
            if isinstance(prev, str) and prev.strip():
                result[key] = prev
        elif isinstance(value, dict):
            prev = existing.get(key, {}) if isinstance(existing, dict) else {}
            result[key] = _preserve_masked_secrets(prev if isinstance(prev, dict) else {}, value)
    return result


def _sanitize_linkedin_payload(linkedin: dict) -> dict:
    if not isinstance(linkedin, dict):
        return {}
    cleaned = dict(linkedin)
    cleaned.pop('scopes_text', None)
    cleaned.pop('organization_urns_text', None)
    return cleaned


def _account_linkedin(payload: dict | None) -> dict:
    """Accept either a full profile object or a bare linkedin block."""
    if not isinstance(payload, dict):
        return {}
    nested = payload.get('linkedin')
    return _sanitize_linkedin_payload(nested if isinstance(nested, dict) else payload)


def _sync_shared_defaults(config: dict) -> dict:
    """Delegate to the shared implementation used by the save hook too."""
    return sync_shared_defaults(config)


class LinkedInConfigApi(ApiHandler):
    async def process(self, input: dict, request=None) -> dict:
        """HTTP entry point: POST /api/plugins/linkedin/linkedin_config_api."""
        payload = dict(input or {})
        action = str(payload.pop("action", "get") or "get")
        if request is not None and "request_root" not in payload:
            try:
                payload["request_root"] = str(request.host_url or "").rstrip("/")
            except Exception:
                payload["request_root"] = ""
        return await self.handle(action=action, **payload)

    async def handle(
        self,
        action: str = "get",
        config: dict | None = None,
        name: str | None = None,
        profile: dict | None = None,
        target: str | None = None,
        access_token: str | None = None,
        redirect_uri: str | None = None,
        urns: list | None = None,
        request_root: str = "",
        **_: object,
    ) -> dict:
        if action == "get":
            current = load_config()
            return {
                "ok": True,
                "action": action,
                "config": mask_config(current),
                "schema": load_schema(),
                "accounts": list_accounts(current),
            }

        if action == "set":
            current = load_config()
            incoming = _preserve_masked_secrets(current, config or {})
            saved = persist_config(_sync_shared_defaults(incoming))
            return {
                "ok": True,
                "action": action,
                "config": mask_config(saved),
                "accounts": list_accounts(saved),
            }

        if action == "test":
            current = load_config()
            target_profile = str(name or current.get('active_profile') or 'default')
            names = get_profile_names(current)
            if target_profile not in names:
                return {
                    "ok": False,
                    "action": action,
                    "message": f"Unknown LinkedIn account '{target_profile}'. Available: {', '.join(names)}.",
                }
            account_config = {
                "linkedin": get_profile_config(current, target_profile),
                "active_profile": target_profile,
                "profiles": current.get('profiles', {}),
            }
            auth = LinkedInAuthHelper(account_config)
            return {
                "ok": True,
                "action": action,
                "account": target_profile,
                "auth": auth.get_auth_state(),
            }

        if action == "accounts":
            current = load_config()
            return {
                "ok": True,
                "action": action,
                "active_profile": current.get('active_profile'),
                "accounts": list_accounts(current),
            }

        if action == "account_save":
            account_name = str(name or "").strip().lower()
            if not account_name:
                return {"ok": False, "action": action, "message": "A non-empty 'name' is required."}
            if not ACCOUNT_NAME_RE.match(account_name):
                return {
                    "ok": False,
                    "action": action,
                    "message": "Account names must be 2-64 characters of lowercase letters, digits, dot, dash or underscore.",
                }
            current = load_config()
            existing = current.get('profiles', {}).get(account_name, {})
            if not isinstance(existing, dict):
                existing = {}
            # Secrets live one level down, inside the profile's `linkedin` block,
            # so the masked-value comparison must run against that block.
            existing_linkedin = existing.get('linkedin') if isinstance(existing.get('linkedin'), dict) else {}
            payload = _preserve_masked_secrets(existing_linkedin, _account_linkedin(profile))
            if not payload.get('access_token') and existing_linkedin:
                payload['access_token'] = existing_linkedin.get('access_token', '')
            label = ""
            if isinstance(profile, dict):
                label = str(profile.get('label') or "").strip()
            merged = copy.deepcopy(current)
            profiles = merged.setdefault('profiles', {})
            profiles[account_name] = {
                'label': label or str(existing.get('label') or account_name),
                'linkedin': payload,
            }
            if not merged.get('active_profile'):
                merged['active_profile'] = account_name
            saved = persist_config(_sync_shared_defaults(merged))
            return {
                "ok": True,
                "action": action,
                "account": account_name,
                "created": account_name not in get_profile_names(current),
                "config": mask_config(saved),
                "accounts": list_accounts(saved),
            }

        if action == "account_delete":
            account_name = str(name or "").strip().lower()
            current = load_config()
            profiles = current.get('profiles', {})
            if account_name not in profiles:
                return {
                    "ok": False,
                    "action": action,
                    "message": f"Unknown LinkedIn account '{account_name}'.",
                }
            if len(profiles) <= 1:
                return {
                    "ok": False,
                    "action": action,
                    "message": "At least one LinkedIn account must remain configured.",
                }
            merged = copy.deepcopy(current)
            merged['profiles'].pop(account_name, None)
            if merged.get('active_profile') == account_name:
                merged['active_profile'] = next(iter(merged['profiles'].keys()))
            saved = persist_config(_sync_shared_defaults(merged))
            return {
                "ok": True,
                "action": action,
                "deleted": account_name,
                "config": mask_config(saved),
                "accounts": list_accounts(saved),
            }

        if action == "account_set_active":
            account_name = str(name or "").strip().lower()
            current = load_config()
            if account_name not in get_profile_names(current):
                return {
                    "ok": False,
                    "action": action,
                    "message": f"Unknown LinkedIn account '{account_name}'.",
                }
            merged = copy.deepcopy(current)
            merged['active_profile'] = account_name
            saved = persist_config(_sync_shared_defaults(merged))
            return {
                "ok": True,
                "action": action,
                "active_profile": account_name,
                "config": mask_config(saved),
                "accounts": list_accounts(saved),
            }

        if action == "discover":
            return self._discover(config=config, name=name, target=target, access_token=access_token)

        if action == "labels":
            return self._labels(config=config, name=name, urns=urns, access_token=access_token)

        if action == "oauth_start":
            return self._oauth_start(config=config, name=name, redirect_uri=redirect_uri, request_root=request_root)

        return {"ok": False, "action": action, "message": f"Unsupported action: {action}"}

    def _oauth_start(
        self,
        config: dict | None = None,
        name: str | None = None,
        redirect_uri: str | None = None,
        request_root: str = "",
    ) -> dict:
        """Issue a single-use state nonce and return the LinkedIn authorize URL."""
        from usr.plugins.linkedin.helpers.linkedin_oauth import authorize_url, create_state, resolve_redirect_uri

        current = load_config()
        account_name = str(name or current.get('active_profile') or '').strip()
        names = get_profile_names(current)
        if account_name not in names:
            return {
                "ok": False,
                "action": "oauth_start",
                "message": f"Unknown LinkedIn account '{account_name}'.",
            }

        linkedin = get_profile_config(current, account_name)
        form_linkedin = _account_linkedin(config)
        client_id = str(form_linkedin.get("client_id") or linkedin.get("client_id") or "").strip()
        client_secret = str(form_linkedin.get("client_secret") or "").strip()
        form_secret = str(form_linkedin.get("client_secret") or "").strip()
        if _looks_masked(client_id) or _looks_masked(client_secret):
            # A masked preview means the value is already saved; fall back to stored.
            if _looks_masked(client_id):
                client_id = str(linkedin.get("client_id") or "").strip()

        if not client_id:
            return {
                "ok": False,
                "action": "oauth_start",
                "message": "Add the LinkedIn app client id for this account first, then start the connection.",
            }

        # The callback runs in a separate request and needs these saved, so a
        # Connect click persists the typed app credentials before redirecting.
        form_secret = str(form_linkedin.get("client_secret") or "").strip()
        needs_save = False
        if client_id and client_id != str(linkedin.get("client_id") or ""):
            linkedin["client_id"] = client_id
            needs_save = True
        if form_secret and not _looks_masked(form_secret) and form_secret != str(linkedin.get("client_secret") or ""):
            linkedin["client_secret"] = form_secret
            needs_save = True
        if needs_save:
            merged = copy.deepcopy(current)
            entry = merged.setdefault("profiles", {}).setdefault(account_name, {"label": account_name, "linkedin": {}})
            store = entry.setdefault("linkedin", {})
            store["client_id"] = linkedin.get("client_id", "")
            store["client_secret"] = linkedin.get("client_secret", "")
            persist_config(sync_shared_defaults(merged))
        if not str(linkedin.get("client_secret") or "").strip():
            return {
                "ok": False,
                "action": "oauth_start",
                "message": "Add the LinkedIn app client secret for this account first, then start the connection.",
            }

        # Never add scopes the user did not configure: LinkedIn rejects the whole
        # request with unauthorized_scope_error when the app lacks that product
        # (e.g. OpenID Connect). Organization posting needs no openid at all.
        resolved_target = str(form_linkedin.get("default_target") or profile_target(linkedin) or "personal").strip()
        default_scopes = (
            ["r_organization_social", "w_organization_social", "rw_organization_admin"]
            if resolved_target == "organization"
            # r_member_social is deliberately excluded: LinkedIn gates it behind
            # extra approval, and requesting a scope the app does not hold fails
            # the WHOLE authorization with unauthorized_scope_error, which would
            # block posting over a scope that only reading needs.
            else ["openid", "profile", "w_member_social"]
        )
        scopes = form_linkedin.get("scopes") or linkedin.get("scopes") or default_scopes
        if isinstance(scopes, str):
            scopes = [part.strip() for part in scopes.replace(',', ' ').split() if part.strip()]
        scopes = [str(scope).strip() for scope in scopes if str(scope).strip()]
        if not scopes:
            scopes = default_scopes

        # LinkedIn retires legacy scopes and then rejects the whole authorization
        # request with unauthorized_scope_error. Catch those here so the operator
        # gets a fixable message instead of a LinkedIn error page.
        retired = [s for s in scopes if s in RETIRED_SCOPES]
        if retired:
            return {
                "ok": False,
                "action": "oauth_start",
                "account": account_name,
                "scopes": scopes,
                "message": (
                    f"These scopes on '{account_name}' are retired by LinkedIn and will be rejected: "
                    + ", ".join(retired)
                    + ". Remove them from the Scopes box and connect again. "
                    "Organization posting only needs w_organization_social (add r_organization_social to read posts)."
                ),
            }

        resolved_redirect = resolve_redirect_uri(request_root, str(redirect_uri or ""))
        plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        state = create_state(plugin_dir, account_name, resolved_redirect, scopes)
        return {
            "ok": True,
            "action": "oauth_start",
            "account": account_name,
            "authorize_url": authorize_url(client_id, resolved_redirect, scopes, state),
            "redirect_uri": resolved_redirect,
            "scopes": scopes,
            "message": f"Open the authorize URL to connect '{account_name}'.",
        }

    def _discover(
        self,
        config: dict | None = None,
        name: str | None = None,
        target: str | None = None,
        access_token: str | None = None,
    ) -> dict:
        """Resolve the member URN or the organization URNs for an account.

        Works with an unsaved token from the settings form: the UI can discover
        identifiers before the account is persisted. The token is never echoed.
        """
        from usr.plugins.linkedin.helpers.linkedin_client import LinkedInClient

        current = load_config()
        account_name = str(name or current.get('active_profile') or '').strip()
        names = get_profile_names(current)
        if not account_name or account_name not in names:
            account_name = names[0] if names else ''
        if not account_name:
            return {
                "ok": False,
                "action": "discover",
                "message": "No LinkedIn account is configured yet. Add an account first.",
            }

        # Stored credentials first; an explicit form token overrides them, and a
        # masked preview from an earlier save must never be sent to LinkedIn.
        linkedin = get_profile_config(current, account_name)
        form_linkedin = _account_linkedin(config)
        if _looks_masked(form_linkedin.get("access_token")):
            form_linkedin.pop("access_token", None)
        candidate_token = str(access_token or form_linkedin.get("access_token") or "").strip()
        if candidate_token and not _looks_masked(candidate_token):
            linkedin["access_token"] = candidate_token

        if not str(linkedin.get("access_token") or "").strip():
            return {
                "ok": False,
                "action": "discover",
                "account": account_name,
                "message": "Enter an access token first, then run discovery.",
            }

        resolved_target = str(target or profile_target(linkedin) or "personal").strip()
        client = LinkedInClient({
            "linkedin": linkedin,
            "active_profile": account_name,
            "profiles": current.get('profiles', {}),
        })

        if resolved_target == "personal":
            found = client.get_member_urn()
            if not found.get("ok"):
                return {
                    "ok": False,
                    "action": "discover",
                    "account": account_name,
                    "target": resolved_target,
                    "status": found.get("status"),
                    "message": _describe_discovery_error(found, "member URN"),
                }
            return {
                "ok": True,
                "action": "discover",
                "account": account_name,
                "target": resolved_target,
                "person_urn": found.get("member_urn", ""),
                "name": found.get("name", ""),
            }

        found = client.discover_organizations(force_live=True)
        if not found.get("ok"):
            message = _describe_discovery_error(found, "organization pages")
            # A configured scope can exist on the app while the saved token was
            # minted before that product was granted: tokens are immutable
            # snapshots, so only a fresh authorization adds the new scope.
            saved_scopes = [str(s) for s in (linkedin.get("scopes") or [])]
            if found.get("status") == 401:
                message += (
                    " LinkedIn rejected the saved token itself (HTTP 401), so this is not a "
                    "scope problem: the token has expired, been revoked, or was issued by an "
                    "app whose client secret was regenerated. Click Connect account to mint a "
                    "fresh token, then look up the pages again."
                )
            if found.get("status") == 403 and "rw_organization_admin" in saved_scopes:
                message += (
                    " The account already lists rw_organization_admin, but the saved token "
                    "was issued before that scope existed. Scopes are fixed when a token is "
                    "minted, so click Connect account (or the manual authorize link) again "
                    "to get a token that actually carries it."
                )
            return {
                "ok": False,
                "action": "discover",
                "account": account_name,
                "target": resolved_target,
                "status": found.get("status"),
                "message": message,
            }
        organizations = [
            item for item in found.get("organizations", [])
            if str(item.get("organization") or "").startswith("urn:li:organization:")
        ]

        # organizationAcls carries no name fields, and /rest rejects the legacy
        # `projection` parameter that used to request them, so resolve each page
        # name separately. Failures are tolerated: a missing label must never
        # break discovery, the URN is still correct without it.
        for item in organizations:
            if str(item.get("localizedName") or "").strip():
                continue
            try:
                named = client.get_organization_name(item.get("organization") or "")
            except Exception:
                named = {"ok": False}
            if named.get("ok"):
                item["localizedName"] = named.get("localizedName") or ""
                item["vanityName"] = named.get("vanityName") or ""

        return {
            "ok": True,
            "action": "discover",
            "account": account_name,
            "target": resolved_target,
            "organization_urns": [item["organization"] for item in organizations],
            "organizations": organizations,
        }

    def _labels(
        self,
        config: dict | None = None,
        name: str | None = None,
        urns: list | None = None,
        access_token: str | None = None,
    ) -> dict:
        """Resolve organization URNs to human page names.

        `/rest/organizationAcls` returns no name fields and `/rest` rejects the
        legacy `projection` parameter, so each page is resolved through
        `/rest/organizations/{id}`, which does return localizedName with plain
        organization read access.
        """
        current = load_config()
        account_name = str(name or current.get("active_profile") or "").strip()
        linkedin = get_profile_config(current, account_name)
        form_linkedin = _account_linkedin(config)
        if _looks_masked(form_linkedin.get("access_token")):
            form_linkedin.pop("access_token", None)
        candidate_token = str(access_token or form_linkedin.get("access_token") or "").strip()
        if candidate_token and not _looks_masked(candidate_token):
            linkedin["access_token"] = candidate_token

        if not str(linkedin.get("access_token") or "").strip():
            return {
                "ok": False,
                "action": "labels",
                "account": account_name,
                "message": "No access token configured for this account.",
            }

        # Mirrors _discover: the client is imported locally, not at module level.
        from usr.plugins.linkedin.helpers.linkedin_client import LinkedInClient

        requested = urns if isinstance(urns, list) and urns else list(linkedin.get("organization_urns") or [])
        requested = [str(urn).strip() for urn in requested if str(urn).strip()]
        if not requested:
            return {
                "ok": True,
                "action": "labels",
                "account": account_name,
                "count": 0,
                "labels": {},
                "errors": {},
                "message": "No organization URNs to label yet.",
            }

        client = LinkedInClient({
            "linkedin": linkedin,
            "active_profile": account_name,
            "profiles": current.get("profiles", {}),
        })
        labels: dict[str, str] = {}
        errors: dict[str, str] = {}
        for urn in requested:
            try:
                found = client.get_organization_name(urn)
            except Exception as exc:
                errors[urn] = str(exc)
                continue
            if found.get("ok"):
                label = str(found.get("localizedName") or "").strip() or str(found.get("vanityName") or "").strip()
                if label:
                    labels[urn] = label
            else:
                error = found.get("error")
                if isinstance(error, dict):
                    errors[urn] = str(error.get("message") or error.get("raw") or "lookup failed")[:160]
                else:
                    errors[urn] = str(error or "lookup failed")[:160]

        return {
            "ok": True,
            "action": "labels",
            "account": account_name,
            "count": len(labels),
            "labels": labels,
            "errors": errors,
        }


def _describe_discovery_error(found: dict, what: str) -> str:
    error = found.get("error")
    detail = ""
    if isinstance(error, dict):
        detail = str(error.get("message") or error.get("raw") or "").strip()
    elif error:
        detail = str(error)
    status = found.get("status")
    parts = [f"Could not resolve the {what}"]
    if status:
        parts.append(f"(HTTP {status})")
    message = " ".join(parts)
    if detail:
        message += f": {detail[:300]}"
    hint = str(found.get("hint") or "").strip()
    if hint:
        message += f" {hint}"
    return message


def handle(action: str = "get", **kwargs: object) -> dict:
    import asyncio
    return asyncio.run(LinkedInConfigApi().handle(action=action, **kwargs))
