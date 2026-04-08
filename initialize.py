"""Minimal plugin initialization for LinkedIn scaffold."""
from pathlib import Path


def initialize(plugin_dir: str | None = None, **_: object) -> dict:
    """Perform lightweight initialization.

    TODO: If the final implementation needs dependency installation or migrations,
    add them here conservatively.
    """
    root = Path(plugin_dir or Path(__file__).resolve().parent)
    required = [
        root / "plugin.yaml",
        root / "default_config.yaml",
        root / "config.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    return {
        "ok": not missing,
        "plugin": "linkedin",
        "missing": missing,
        "message": "LinkedIn plugin scaffold initialized" if not missing else "LinkedIn plugin scaffold missing required files",
    }
