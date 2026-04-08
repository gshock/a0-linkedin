"""Optional plugin hooks for LinkedIn scaffold.

This file is intentionally minimal. Add lifecycle hooks only when actual plugin
behavior requires them.
"""


def plugin_status(**_: object) -> dict:
    return {
        "plugin": "linkedin",
        "status": "scaffold",
        "message": "No runtime hooks registered yet.",
    }
