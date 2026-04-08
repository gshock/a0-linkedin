"""Formatting utilities for LinkedIn plugin MVP."""
from __future__ import annotations

from .sanitize import sanitize_text

_ALLOWED_VISIBILITY = {"PUBLIC", "CONNECTIONS", "LOGGED_IN"}


def normalize_visibility(value: str | None, default: str = "PUBLIC") -> str:
    candidate = (value or default or "PUBLIC").upper().strip()
    return candidate if candidate in _ALLOWED_VISIBILITY else default


def compact_post_preview(text: str, visibility: str = "PUBLIC") -> dict:
    cleaned = sanitize_text(text)
    return {
        "text": cleaned,
        "character_count": len(cleaned),
        "visibility": normalize_visibility(visibility),
    }
