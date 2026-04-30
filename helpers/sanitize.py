"""Sanitization and validation helpers for the LinkedIn plugin."""
from __future__ import annotations

from pathlib import Path


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
HEIC_IMAGE_EXTENSIONS = {".heic", ".heif"}
DEFAULT_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024


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


def validate_image_path(
    image_path: str | None,
    *,
    required: bool = False,
    max_size_bytes: int = DEFAULT_MAX_IMAGE_SIZE_BYTES,
    allowed_extensions: set[str] | None = None,
) -> dict:
    raw = (image_path or "").strip()
    if not raw:
        if required:
            raise ValueError("Image file path is required.")
        return {
            "present": False,
            "path": "",
            "name": "",
            "extension": "",
            "size_bytes": 0,
            "needs_conversion": False,
            "source_extension": "",
        }

    path = Path(raw).expanduser()
    if not path.exists():
        raise ValueError(f"Image file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Image path is not a file: {path}")

    extension = path.suffix.lower()
    allowed = allowed_extensions or ALLOWED_IMAGE_EXTENSIONS
    if extension not in allowed:
        supported = ", ".join(sorted(allowed))
        raise ValueError(f"Unsupported image format '{extension or 'unknown'}'. Supported formats: {supported}")

    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise ValueError("Image file is empty.")
    if size_bytes > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise ValueError(f"Image file is too large. Maximum size is {max_mb:.0f} MB.")

    needs_conversion = extension in HEIC_IMAGE_EXTENSIONS
    return {
        "present": True,
        "path": str(path),
        "name": path.name,
        "extension": extension,
        "source_extension": extension,
        "size_bytes": size_bytes,
        "needs_conversion": needs_conversion,
    }
