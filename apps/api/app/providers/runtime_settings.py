"""Pengaturan runtime provider lokal yang dapat diubah dari AI Control Center."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from app.config import Settings

FILE_NAME = "ai-provider-settings.json"


def valid_base_url(value: str) -> bool:
    try:
        parsed = urlsplit(value.strip())
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and ".." not in parsed.path.split("/")
        )
    except (TypeError, ValueError):
        return False


def settings_path(data_dir: Path) -> Path:
    return data_dir / FILE_NAME


def load_provider_settings(settings: Settings) -> None:
    """Muat opsi provider sebelum registry dibuat; file berada di direktori data lokal."""
    try:
        values = json.loads(settings_path(settings.data_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    ollama = values.get("ollama") if isinstance(values, dict) else None
    if isinstance(ollama, dict):
        if isinstance(ollama.get("enabled"), bool):
            settings.ollama_enabled = ollama["enabled"]
        base_url = ollama.get("base_url")
        if isinstance(base_url, str) and valid_base_url(base_url):
            settings.ollama_base_url = base_url.strip().rstrip("/")
    for name in ("openai", "gemini", "anthropic"):
        value = values.get(name) if isinstance(values, dict) else None
        if not isinstance(value, dict):
            continue
        if isinstance(value.get("enabled"), bool):
            setattr(settings, f"{name}_enabled", value["enabled"])
        if isinstance(value.get("api_key"), str):
            setattr(settings, f"{name}_api_key", value["api_key"])


def save_provider_settings(data_dir: Path, *, enabled: bool, base_url: str) -> None:
    path = settings_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    values = _read_settings(path)
    values["ollama"] = {"enabled": enabled, "base_url": base_url}
    _write_settings(path, values)


def save_cloud_provider_settings(data_dir: Path, *, name: str, enabled: bool, api_key: str) -> None:
    if name not in {"openai", "gemini", "anthropic"}:
        raise ValueError("Provider cloud tidak dikenal")
    path = settings_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    values = _read_settings(path)
    values[name] = {"enabled": enabled, "api_key": api_key}
    _write_settings(path, values)


def _read_settings(path: Path) -> dict:
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        return values if isinstance(values, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_settings(path: Path, values: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
