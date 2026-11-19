"""LinkedIn plugin config API.

Supports whole-config get/set plus explicit per-account CRUD so a single plugin
installation can hold many LinkedIn credentials (apps, members, and pages).
"""
from __future__ import annotations

import copy
import re

try:
    from helpers.api import ApiHandler  # type: ignore
except Exception:  # pragma: no cover
    class ApiHandler:
        async def handle(self, **kwargs):
            raise NotImplementedError

from helpers.config import (
    get_profile_config,
    get_profile_names,
    list_accounts,
    load_config,
    load_schema,
    mask_config,
    persist_config,
    sync_shared_defaults,
)
from helpers.linkedin_auth import LinkedInAuthHelper

SECRET_FIELDS = ("access_token", "client_secret", "refresh_token")

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
    async def handle(
        self,
        action: str = "get",
        config: dict | None = None,
        name: str | None = None,
        profile: dict | None = None,
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

        return {"ok": False, "action": action, "message": f"Unsupported action: {action}"}


def handle(action: str = "get", **kwargs: object) -> dict:
    import asyncio
    return asyncio.run(LinkedInConfigApi().handle(action=action, **kwargs))
