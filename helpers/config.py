"""Configuration helpers for the LinkedIn plugin.

Uses JSON for runtime persistence to avoid optional YAML dependency at runtime.
Supports a single active config plus optional named profiles for switching
between personal and organization app settings.
"""
from __future__ import annotations

from pathlib import Path
import copy
import json
import os

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG_PATH = PLUGIN_ROOT / ".runtime_config.json"
CONFIG_SCHEMA_PATH = PLUGIN_ROOT / "config.json"
# Non-secret settings that legitimately apply to every account. Secrets and
# identity fields (tokens, person URN, organization URNs) must never propagate
# between accounts.
SHARED_FIELDS = (
    "mode",
    "api_base_url",
    "linkedin_version",
    "timeout_seconds",
    "user_agent",
)

PLUGIN_NAME = "linkedin"
CONFIG_SOURCE_ENV = "LINKEDIN_CONFIG_SOURCE"
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
# Profiles are intentionally empty here: the accounts shipped in
# default_config.yaml are the only seed. A phantom 'default' account would
# otherwise survive every merge and show up in the UI and in `accounts` output.
# When nothing is configured at all, _normalize_profiles creates a 'default'
# placeholder so the settings page still has an account to render.
DEFAULT_CONFIG = {
    "enabled": True,
    "active_profile": "",
    "linkedin": copy.deepcopy(DEFAULT_LINKEDIN),
    "profiles": {},
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


PERSONAL_TARGETS = {"personal", "person", "member", "profile"}
ORGANIZATION_TARGETS = {"organization", "org", "company", "page"}


def normalize_target_alias(target: str | None) -> str | None:
    """Map a loose target word onto 'personal' or 'organization' (None if unknown)."""
    candidate = str(target or "").strip().lower()
    if candidate in PERSONAL_TARGETS:
        return "personal"
    if candidate in ORGANIZATION_TARGETS:
        return "organization"
    return None


def profile_target(linkedin: dict) -> str:
    """Infer whether a credential set acts as a person or an organization."""
    linkedin = linkedin or {}
    default_target = str(linkedin.get("default_target") or "").strip().lower()
    if default_target in {"personal", "organization"}:
        return default_target
    scopes = {str(s).strip() for s in (linkedin.get("scopes") or [])}
    if scopes & {"w_organization_social", "r_organization_social"}:
        return "organization"
    if scopes & {"w_member_social", "r_member_social"}:
        return "personal"
    if str(linkedin.get("organization_urn") or "").strip() or (linkedin.get("organization_urns") or []):
        return "organization"
    if str(linkedin.get("person_urn") or linkedin.get("member_urn") or "").strip():
        return "personal"
    return "personal"


def get_profile_target(config: dict, profile_name: str) -> str:
    return profile_target(get_profile_config(config, profile_name))


def profile_capabilities(config: dict, profile_name: str) -> dict:
    """Describe one configured account: target type, scopes, and readiness."""
    linkedin = get_profile_config(config, profile_name)
    scopes = sorted({str(s).strip() for s in (linkedin.get("scopes") or []) if str(s).strip()})
    target = profile_target(linkedin)
    token_present = bool(str(linkedin.get("access_token") or "").strip())
    person_urn_present = bool(str(linkedin.get("person_urn") or linkedin.get("member_urn") or "").strip())
    organization_urns = [str(u).strip() for u in (linkedin.get("organization_urns") or []) if str(u).strip()]
    organization_urn = str(linkedin.get("organization_urn") or "").strip()
    if organization_urn and organization_urn not in organization_urns:
        organization_urns.insert(0, organization_urn)
    can_post = token_present and (
        (target == "personal" and "w_member_social" in scopes and person_urn_present)
        or (target == "organization" and "w_organization_social" in scopes and bool(organization_urns))
    )
    can_read = token_present and (
        (target == "personal" and "r_member_social" in scopes and person_urn_present)
        or (target == "organization" and "r_organization_social" in scopes and bool(organization_urns))
    )
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    raw_profile = profiles.get(profile_name) if isinstance(profiles.get(profile_name), dict) else {}
    label = str(raw_profile.get("label") or profile_name)
    return {
        "profile": profile_name,
        "label": label,
        "target": target,
        "token_present": token_present,
        "scopes": scopes,
        "person_urn_present": person_urn_present,
        "organization_urns": organization_urns,
        "organization_page_count": len(organization_urns),
        "can_post": can_post,
        "can_read": can_read,
        "dry_run": bool(linkedin.get("dry_run", True)),
    }


def list_accounts(config: dict) -> list[dict]:
    """Return a capability summary for every configured LinkedIn account."""
    cfg = _normalize_profiles(config or {})
    return [profile_capabilities(cfg, name) for name in get_profile_names(cfg)]


def resolve_profile_candidates(config: dict, target: str | None = None) -> list[dict]:
    """Accounts with a token that can act for the requested target type."""
    cfg = _normalize_profiles(config or {})
    normalized = normalize_target_alias(target)
    candidates: list[dict] = []
    for account in list_accounts(cfg):
        if normalized and account.get("target") != normalized:
            continue
        if not account.get("token_present"):
            continue
        candidates.append(account)
    return candidates


def resolve_target_selection(config: dict, target: str | None = None, profile: str | None = None) -> dict:
    """Single routing decision point for every LinkedIn tool.

    Resolution order: explicit profile, then a unique capability match, then a
    clarification request carrying the candidate accounts for the agent to present.
    """
    cfg = _normalize_profiles(config or {})
    available = set(get_profile_names(cfg))

    explicit = str(profile or "").strip()
    if explicit:
        if explicit not in available:
            return {
                "profile": None,
                "linkedin": None,
                "error": f"Unknown LinkedIn profile '{explicit}'. Available profiles: {', '.join(sorted(available))}.",
                "needs_clarification": False,
                "candidates": list_accounts(cfg),
            }
        return {
            "profile": explicit,
            "linkedin": get_profile_config(cfg, explicit),
            "error": None,
            "needs_clarification": False,
            "candidates": [],
        }

    candidates = resolve_profile_candidates(cfg, target)
    if not candidates:
        every = list_accounts(cfg)
        requested = normalize_target_alias(target)
        scope_hint = f" for target '{requested}'" if requested else ""
        if not every:
            message = "No LinkedIn accounts are configured."
        elif any(account.get("token_present") for account in every):
            message = f"No configured LinkedIn account can act{scope_hint}: none has a token plus the required scopes and author URN for that target."
        else:
            message = f"No configured LinkedIn account has an access token{scope_hint}. Add a token in the LinkedIn plugin config."
        return {"profile": None, "linkedin": None, "error": message, "needs_clarification": False, "candidates": every}

    if len(candidates) == 1:
        account = candidates[0]
        return {
            "profile": account["profile"],
            "linkedin": get_profile_config(cfg, account["profile"]),
            "error": None,
            "needs_clarification": False,
            "candidates": [],
        }

    label = normalize_target_alias(target) or "this request"
    return {
        "profile": None,
        "linkedin": None,
        "error": f"Multiple LinkedIn accounts can handle {label}: {', '.join(c['profile'] for c in candidates)}. Which one should be used?",
        "needs_clarification": True,
        "candidates": candidates,
    }


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
    """Backward-compatible wrapper around resolve_target_selection."""
    selection = resolve_target_selection(config, target=target, profile=profile)
    return selection.get("profile"), selection.get("error")


def resolve_linkedin_config(config: dict, target: str | None = None, profile: str | None = None) -> tuple[dict | None, str | None, str | None]:
    """Backward-compatible wrapper: (linkedin_config, profile_name, error)."""
    selection = resolve_target_selection(config, target=target, profile=profile)
    return selection.get("linkedin"), selection.get("profile"), selection.get("error")


def get_dual_profile_snapshot(config: dict) -> dict:
    """Compact readiness snapshot for every configured account."""
    cfg = _normalize_profiles(config or {})
    snapshot = {}
    for account in list_accounts(cfg):
        snapshot[account["profile"]] = {
            "label": account["label"],
            "target": account["target"],
            "token_present": account["token_present"],
            "person_urn_present": account["person_urn_present"],
            "organization_urn_present": bool(account["organization_urns"]),
            "organization_page_count": account["organization_page_count"],
            "scopes": account["scopes"],
            "can_post": account["can_post"],
            "can_read": account["can_read"],
            "dry_run": account["dry_run"],
        }
    return snapshot


def load_default_config() -> dict:
    return copy.deepcopy(DEFAULT_CONFIG)


def _framework_scope(agent=None) -> tuple[str, str]:
    """Resolve (project_name, agent_profile) for scoped plugin config."""
    project_name = ""
    agent_profile = ""
    if agent is not None:
        try:
            from helpers import projects as _projects

            project_name = str(_projects.get_context_project_name(agent.context) or "")
        except Exception:
            project_name = ""
        try:
            agent_profile = str(agent.config.profile or "")
        except Exception:
            agent_profile = ""
    return project_name, agent_profile


def _framework_config_path(agent=None) -> str:
    """Path of the saved plugin config.json, or '' when none exists yet."""
    try:
        from helpers import plugins as _plugins

        project_name, agent_profile = _framework_scope(agent)
        entry = _plugins.find_plugin_asset(
            PLUGIN_NAME,
            _plugins.CONFIG_FILE_NAME,
            project_name=project_name,
            agent_profile=agent_profile,
        )
        return str((entry or {}).get("path") or "")
    except Exception:
        return ""


def _framework_effective_config(agent=None) -> dict:
    """Framework-resolved config: config.json when saved, else default_config.yaml."""
    try:
        from helpers import plugins as _plugins

        data = _plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def config_source(agent=None) -> str:
    """Where load_config() reads from: 'framework' (settings UI) or 'local' (tests/CLI)."""
    forced = str(os.environ.get(CONFIG_SOURCE_ENV, "") or "").strip().lower()
    if forced in {"local", "framework"}:
        return forced
    return "framework" if _framework_config_path(agent) else "local"


def sync_shared_defaults(config: dict) -> dict:
    """Apply the Runtime-tab defaults to every account, then mirror the active one.

    The root `linkedin` block is a shared-defaults surface, never a credential
    source. Without this step a stale mirrored token in the root block would
    overwrite a freshly edited account token on save.
    """
    if not isinstance(config, dict):
        return config
    result = copy.deepcopy(config)
    profiles = result.get("profiles") if isinstance(result.get("profiles"), dict) else {}
    profiles = copy.deepcopy(profiles)
    root = result.get("linkedin") if isinstance(result.get("linkedin"), dict) else {}
    shared = {key: copy.deepcopy(root[key]) for key in SHARED_FIELDS if key in root}

    for name, profile in list(profiles.items()):
        if not isinstance(profile, dict):
            continue
        profile = copy.deepcopy(profile)
        linkedin = profile.get("linkedin") if isinstance(profile.get("linkedin"), dict) else {}
        linkedin = copy.deepcopy(linkedin)
        linkedin.update(shared)
        profile["label"] = str(profile.get("label") or name)
        profile["linkedin"] = linkedin
        profiles[name] = profile

    result["profiles"] = profiles
    names = [str(name) for name in profiles.keys()]
    active = str(result.get("active_profile") or "").strip()
    if active not in names:
        active = names[0] if names else "default"
    result["active_profile"] = active
    active_linkedin = profiles.get(active, {}).get("linkedin") if active else None
    result["linkedin"] = copy.deepcopy(active_linkedin or root)
    return result


def sanitize_for_storage(config: dict) -> dict:
    """Strip UI-only helper fields before persisting."""
    cfg = copy.deepcopy(config or {})
    profiles = cfg.get("profiles") if isinstance(cfg.get("profiles"), dict) else {}
    for profile in profiles.values():
        if not isinstance(profile, dict):
            continue
        linkedin = profile.get("linkedin")
        if isinstance(linkedin, dict):
            linkedin.pop("scopes_text", None)
            linkedin.pop("organization_urns_text", None)
    root = cfg.get("linkedin")
    if isinstance(root, dict):
        root.pop("scopes_text", None)
        root.pop("organization_urns_text", None)
    return cfg


def load_config(agent=None) -> dict:
    """Load the LinkedIn config from the plugin settings store.

    Precedence: framework config.json (what the Settings UI writes) when present,
    else the local runtime file, else default_config.yaml. Set
    LINKEDIN_CONFIG_SOURCE=local|framework to force one source.
    """
    runtime_cfg: dict = {}
    if config_source(agent) == "framework":
        runtime_cfg = _framework_effective_config(agent)
    else:
        if LOCAL_CONFIG_PATH.exists():
            try:
                with LOCAL_CONFIG_PATH.open("r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                runtime_cfg = loaded if isinstance(loaded, dict) else {}
            except (OSError, json.JSONDecodeError):
                runtime_cfg = {}
        if not runtime_cfg:
            runtime_cfg = _framework_effective_config(agent)
    return _normalize_profiles(_deep_merge(load_default_config(), runtime_cfg or {}))


def persist_config(config: dict, agent=None) -> dict:
    """Persist normalized config to the same store load_config() prefers."""
    merged = _deep_merge(load_default_config(), sanitize_for_storage(config))
    normalized = _normalize_profiles(merged)
    if config_source(agent) == "framework":
        try:
            from helpers import plugins as _plugins

            project_name, agent_profile = _framework_scope(agent)
            _plugins.save_plugin_config(PLUGIN_NAME, project_name, agent_profile, normalized)
            return normalized
        except Exception:
            pass
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


# Shipped schema so the config UI still renders when no config.json file exists.
# config.json is a gitignored runtime artifact, so it can never be a hard dependency.
DEFAULT_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "active_profile": {"type": "string"},
        "linkedin": {"type": "object"},
        "profiles": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "linkedin": {
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string", "enum": ["api", "browser", "hybrid"]},
                            "api_base_url": {"type": "string"},
                            "access_token": {"type": "string", "format": "password"},
                            "person_urn": {"type": "string"},
                            "organization_urn": {"type": "string"},
                            "organization_urns": {"type": "array", "items": {"type": "string"}},
                            "scopes": {"type": "array", "items": {"type": "string"}},
                            "default_target": {"type": "string", "enum": ["personal", "organization"]},
                            "linkedin_version": {"type": "string"},
                            "default_visibility": {"type": "string", "enum": ["PUBLIC", "CONNECTIONS", "LOGGED_IN"]},
                            "dry_run": {"type": "boolean"},
                            "timeout_seconds": {"type": "integer"},
                            "user_agent": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                },
                "additionalProperties": True,
            },
        },
    },
    "additionalProperties": True,
}


def load_schema() -> dict:
    if CONFIG_SCHEMA_PATH.exists():
        try:
            with CONFIG_SCHEMA_PATH.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            pass
    return copy.deepcopy(DEFAULT_SCHEMA)
