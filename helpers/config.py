"""Configuration helpers for the LinkedIn plugin.

Uses JSON for runtime persistence to avoid optional YAML dependency at runtime.
Supports a single active config plus optional named profiles for switching
between personal and organization app settings.
"""
from __future__ import annotations

from pathlib import Path
import copy
import json

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG_PATH = PLUGIN_ROOT / ".runtime_config.json"
CONFIG_SCHEMA_PATH = PLUGIN_ROOT / "config.json"
DEFAULT_LINKEDIN = {
    "mode": "api",
    "api_base_url": "https://api.linkedin.com",
    "access_token": "",
    "person_urn": "",
    "organization_urn": "",
    "organization_urns": [],
    "scopes": [],
    "default_target": "personal",
    "linkedin_version": "202601",
    "default_visibility": "PUBLIC",
    "dry_run": True,
    "timeout_seconds": 30,
    "user_agent": "AgentZero-LinkedIn-Plugin/0.2.0",
}
DEFAULT_CONFIG = {
    "enabled": True,
    "active_profile": "default",
    "linkedin": copy.deepcopy(DEFAULT_LINKEDIN),
    "profiles": {
        "default": {
            "label": "Default",
            "linkedin": copy.deepcopy(DEFAULT_LINKEDIN),
        }
    },
}


def _deep_merge(base: dict, extra: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _normalize_profiles(config: dict) -> dict:
    cfg = copy.deepcopy(config or {})
    raw_root_linkedin = cfg.get("linkedin") if isinstance(cfg.get("linkedin"), dict) else {}
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        seed_linkedin = raw_root_linkedin or DEFAULT_LINKEDIN
        profiles = {
            "default": {
                "label": "Default",
                "linkedin": copy.deepcopy(seed_linkedin),
            }
        }
    normalized_profiles = {}
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        normalized_profiles[str(name)] = {
            "label": str(profile.get("label") or name).strip() or str(name),
            "linkedin": _deep_merge(DEFAULT_LINKEDIN, profile.get("linkedin") or {}),
        }
    if not normalized_profiles:
        normalized_profiles = {
            "default": {
                "label": "Default",
                "linkedin": copy.deepcopy(DEFAULT_LINKEDIN),
            }
        }
    cfg["profiles"] = normalized_profiles
    active_profile = str(cfg.get("active_profile") or "default").strip() or "default"
    if active_profile not in normalized_profiles:
        active_profile = next(iter(normalized_profiles.keys()))
    cfg["active_profile"] = active_profile

    active_linkedin = copy.deepcopy(normalized_profiles.get(active_profile, {}).get("linkedin") or DEFAULT_LINKEDIN)
    root_overrides = {
        key: value
        for key, value in raw_root_linkedin.items()
        if key in DEFAULT_LINKEDIN and value != DEFAULT_LINKEDIN.get(key)
    }
    cfg["linkedin"] = _deep_merge(active_linkedin, root_overrides)
    return cfg


def get_profile_names(config: dict) -> list[str]:
    cfg = _normalize_profiles(config or {})
    profiles = cfg.get("profiles", {}) if isinstance(cfg, dict) else {}
    if not isinstance(profiles, dict):
        return []
    return sorted(str(name) for name, profile in profiles.items() if isinstance(profile, dict))


def get_profile_name_for_target(target: str | None) -> str | None:
    candidate = str(target or "").strip().lower()
    if candidate in {"personal", "person", "member", "profile"}:
        return "personal_app"
    if candidate in {"organization", "org", "company", "page"}:
        return "org_app"
    return None


def get_profile_config(config: dict, profile_name: str) -> dict:
    cfg = _normalize_profiles(config or {})
    profiles = cfg.get("profiles", {}) if isinstance(cfg, dict) else {}
    if not isinstance(profiles, dict) or profile_name not in profiles:
        raise ValueError(f"Unknown LinkedIn profile '{profile_name}'.")
    profile = profiles.get(profile_name, {})
    linkedin = profile.get("linkedin", {}) if isinstance(profile, dict) else {}
    if not isinstance(linkedin, dict):
        linkedin = {}
    return _deep_merge(DEFAULT_LINKEDIN, linkedin)


def resolve_profile_name(config: dict, target: str | None = None, profile: str | None = None) -> tuple[str | None, str | None]:
    cfg = _normalize_profiles(config or {})
    available = set(get_profile_names(cfg))

    explicit_profile = str(profile or "").strip()
    if explicit_profile:
        if explicit_profile not in available:
            return None, f"Unknown LinkedIn profile '{explicit_profile}'. Available profiles: {', '.join(sorted(available))}."
        return explicit_profile, None

    mapped = get_profile_name_for_target(target)
    if mapped:
        if mapped not in available:
            return None, f"LinkedIn target '{target}' maps to profile '{mapped}', but that profile is not configured."
        return mapped, None

    return None, "LinkedIn target is ambiguous. Please specify whether to use your personal profile or organization profile."


def resolve_linkedin_config(config: dict, target: str | None = None, profile: str | None = None) -> tuple[dict | None, str | None, str | None]:
    resolved_profile, error = resolve_profile_name(config, target=target, profile=profile)
    if error or not resolved_profile:
        return None, None, error
    return get_profile_config(config, resolved_profile), resolved_profile, None


def get_dual_profile_snapshot(config: dict) -> dict:
    cfg = _normalize_profiles(config or {})
    snapshot = {}
    for profile_name in ("personal_app", "org_app"):
        if profile_name not in get_profile_names(cfg):
            continue
        linkedin = get_profile_config(cfg, profile_name)
        snapshot[profile_name] = {
            "token_present": bool(str(linkedin.get("access_token") or "").strip()),
            "person_urn_present": bool(str(linkedin.get("person_urn") or "").strip()),
            "organization_urn_present": bool(str(linkedin.get("organization_urn") or "").strip() or linkedin.get("organization_urns") or []),
            "scopes": linkedin.get("scopes") or [],
            "default_target": linkedin.get("default_target", "personal"),
            "dry_run": bool(linkedin.get("dry_run", True)),
        }
    return snapshot


def load_default_config() -> dict:
    return copy.deepcopy(DEFAULT_CONFIG)


def load_config() -> dict:
    config = load_default_config()
    if LOCAL_CONFIG_PATH.exists():
        with LOCAL_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            runtime_cfg = json.load(fh)
        config = _deep_merge(config, runtime_cfg)
    return _normalize_profiles(config)


def persist_config(config: dict) -> dict:
    merged = _deep_merge(load_default_config(), config or {})
    normalized = _normalize_profiles(merged)
    with LOCAL_CONFIG_PATH.open("w", encoding="utf-8") as fh:
        json.dump(normalized, fh, indent=2)
    return normalized


def mask_config(config: dict) -> dict:
    masked = copy.deepcopy(config or {})

    def _mask_linkedin(linkedin: dict) -> None:
        for key in ("access_token", "client_secret", "refresh_token"):
            if linkedin.get(key):
                value = str(linkedin[key])
                linkedin[key] = ("*" * max(0, len(value) - 4)) + value[-4:]

    linkedin = masked.get("linkedin", {}) if isinstance(masked, dict) else {}
    if isinstance(linkedin, dict):
        _mask_linkedin(linkedin)

    profiles = masked.get("profiles", {}) if isinstance(masked, dict) else {}
    if isinstance(profiles, dict):
        for profile in profiles.values():
            if isinstance(profile, dict) and isinstance(profile.get("linkedin"), dict):
                _mask_linkedin(profile["linkedin"])
    return masked


def load_schema() -> dict:
    with CONFIG_SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)
