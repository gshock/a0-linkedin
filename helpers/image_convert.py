"""Image conversion helpers for the LinkedIn plugin."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


HEIC_EXTENSIONS = {".heic", ".heif"}
CONVERTED_SUFFIX = "_converted.jpg"


def is_heic_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in HEIC_EXTENSIONS


def find_heic_converter() -> tuple[str, list[str]] | None:
    """Return the first available HEIC conversion command.

    Returns a tuple of (tool_name, argv_prefix).
    """
    if shutil.which("heif-convert"):
        return ("heif-convert", ["heif-convert"])
    if shutil.which("magick"):
        return ("magick", ["magick"])
    if shutil.which("convert"):
        return ("convert", ["convert"])
    return None


def convert_heic_to_jpg(image_path: str | Path) -> dict:
    source = Path(image_path).expanduser().resolve()
    if not source.exists():
        raise ValueError(f"HEIC image file not found: {source}")
    if not source.is_file():
        raise ValueError(f"HEIC image path is not a file: {source}")
    if source.suffix.lower() not in HEIC_EXTENSIONS:
        raise ValueError(f"Expected HEIC/HEIF image, got: {source.suffix or 'unknown'}")

    converter = find_heic_converter()
    if not converter:
        raise ValueError(
            "HEIC/HEIF conversion is not available on this system. Install 'libheif-examples' for heif-convert or ImageMagick."
        )

    tool_name, argv_prefix = converter
    temp_dir = Path(tempfile.mkdtemp(prefix="linkedin_heic_"))
    output_path = temp_dir / f"{source.stem}{CONVERTED_SUFFIX}"

    if tool_name == "heif-convert":
        cmd = argv_prefix + [str(source), str(output_path)]
    else:
        cmd = argv_prefix + [str(source), str(output_path)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception as exc:
        raise ValueError(f"HEIC conversion failed to start: {exc}") from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or "unknown conversion error"
        raise ValueError(f"HEIC conversion failed using {tool_name}: {detail}")

    if not output_path.exists() or not output_path.is_file():
        raise ValueError(f"HEIC conversion did not produce an output file: {output_path}")

    size_bytes = output_path.stat().st_size
    if size_bytes <= 0:
        raise ValueError("Converted JPG file is empty.")

    return {
        "converted": True,
        "source_path": str(source),
        "source_name": source.name,
        "source_extension": source.suffix.lower(),
        "tool": tool_name,
        "path": str(output_path),
        "name": output_path.name,
        "extension": output_path.suffix.lower(),
        "size_bytes": size_bytes,
        "temp_dir": str(temp_dir),
    }
