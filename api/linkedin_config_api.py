"""LinkedIn plugin config API."""
from __future__ import annotations

try:
    from helpers.api import ApiHandler  # type: ignore
except Exception:  # pragma: no cover
    class ApiHandler:
        async def handle(self, **kwargs):
            raise NotImplementedError

from helpers.config import load_config, load_schema, mask_config, persist_config, _deep_merge
from helpers.linkedin_auth import LinkedInAuthHelper

SECRET_FIELDS = ("access_token", "client_secret", "refresh_token")


def _looks_masked(value: object) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return bool(stripped) and all(ch == '*' for ch in stripped[:-4]) and len(stripped) >= 4


def _preserve_masked_secrets(existing: dict, incoming: dict) -> dict:
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


def _sync_active_profile(config: dict) -> dict:
    if not isinstance(config, dict):
        return config
    cfg = dict(config)
    active = str(cfg.get('active_profile') or 'default').strip() or 'default'
    profiles = cfg.get('profiles') if isinstance(cfg.get('profiles'), dict) else {}
    profile = profiles.get(active) if isinstance(profiles.get(active), dict) else {}
    profile_linkedin = _sanitize_linkedin_payload(profile.get('linkedin') if isinstance(profile.get('linkedin'), dict) else {})
    root_linkedin = _sanitize_linkedin_payload(cfg.get('linkedin') if isinstance(cfg.get('linkedin'), dict) else {})

    merged_profile_linkedin = _deep_merge(profile_linkedin, root_linkedin)
    merged_root_linkedin = _deep_merge(root_linkedin, merged_profile_linkedin)

    profile = dict(profile)
    profile['label'] = str(profile.get('label') or active)
    profile['linkedin'] = merged_profile_linkedin
    profiles = dict(profiles)
    profiles[active] = profile

    cfg['active_profile'] = active
    cfg['profiles'] = profiles
    cfg['linkedin'] = merged_root_linkedin
    return cfg


class LinkedInConfigApi(ApiHandler):
    async def handle(self, action: str = "get", config: dict | None = None, **_: object) -> dict:
        if action == "get":
            current = load_config()
            return {"ok": True, "action": action, "config": mask_config(current), "schema": load_schema()}
        if action == "set":
            current = load_config()
            incoming = _preserve_masked_secrets(current, config or {})
            incoming = _sync_active_profile(incoming)
            saved = persist_config(incoming)
            return {"ok": True, "action": action, "config": mask_config(saved)}
        if action == "test":
            current = load_config()
            auth = LinkedInAuthHelper(current)
            return {"ok": True, "action": action, "auth": auth.get_auth_state(), "config": mask_config(current)}
        return {"ok": False, "action": action, "message": f"Unsupported action: {action}"}


def handle(action: str = "get", **kwargs: object) -> dict:
    import asyncio
    return asyncio.run(LinkedInConfigApi().handle(action=action, **kwargs))
