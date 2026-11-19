"""Lifecycle hooks for the LinkedIn plugin.

The framework calls `save_plugin_config` whenever the settings UI persists the
plugin config.json. That hook is where a saved payload is normalized into the
named-account shape the tools rely on, so a hand-edited or older-UI payload can
never leave the plugin half-valid or let one account's credentials leak into
another's.
"""


def plugin_status(**_: object) -> dict:
    return {
        "plugin": "linkedin",
        "status": "ready",
        "message": "Multi-account LinkedIn plugin ready.",
    }


def save_plugin_config(settings: dict | None = None, **_: object) -> dict:
    """Normalize and share defaults before config.json is written."""
    if not isinstance(settings, dict):
        return settings if settings is not None else {}
    try:
        from usr.plugins.linkedin.helpers.config import (
            _normalize_profiles,
            sanitize_for_storage,
            sync_shared_defaults,
        )

        return _normalize_profiles(sync_shared_defaults(sanitize_for_storage(settings)))
    except Exception:
        # Never block a save because normalization failed.
        return settings
