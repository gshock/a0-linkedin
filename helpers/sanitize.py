"""Sanitization and validation helpers for the LinkedIn plugin."""
from __future__ import annotations


def sanitize_text(text: str, max_length: int = 3000) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text


def mask_secret(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * max(0, len(value) - keep) + value[-keep:]


def normalize_target(target: str | None, default: str = "organization") -> str:
    candidate = (target or default or "organization").strip().lower()
    if candidate in {"org", "company", "organization"}:
        return "organization"
    if candidate in {"personal", "person", "member", "profile"}:
        return "personal"
    raise ValueError("target must be 'organization' or 'personal'.")


def normalize_organization_urn(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("urn:li:organization:"):
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    return f"urn:li:organization:{digits}" if digits else raw


def validate_message(text: str, max_length: int = 3000) -> str:
    cleaned = sanitize_text(text, max_length=max_length)
    if not cleaned:
        raise ValueError("Post message must not be empty.")
    return cleaned
