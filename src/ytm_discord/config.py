from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


APP_NAME = "ytm-discord-status"
DEFAULT_SUPPORTED_APPS = (
    "chrome",
    "msedge",
    "edge",
    "brave",
    "opera",
    "firefox",
    "chromium",
    "vivaldi",
    "youtube",
)


@dataclass(frozen=True)
class PresenceConfig:
    large_text: str = "YouTube Music"
    small_text: str = "music.youtube.com"


@dataclass(frozen=True)
class AppConfig:
    client_id: str
    poll_interval_seconds: float = 5.0
    clear_on_pause: bool = True
    reconnect_interval_seconds: float = 15.0
    supported_apps: tuple[str, ...] = DEFAULT_SUPPORTED_APPS
    presence: PresenceConfig = field(default_factory=PresenceConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        if not isinstance(data, dict):
            raise ValueError("config root must be a JSON object")

        presence_raw = data.get("presence") or {}
        if not isinstance(presence_raw, dict):
            raise ValueError("presence must be a JSON object")

        supported = data.get("supported_apps", DEFAULT_SUPPORTED_APPS)
        if not isinstance(supported, (list, tuple)) or not supported:
            raise ValueError("supported_apps must be a non-empty list")

        if "client_id" not in data:
            raise ValueError("client_id is required")

        return cls(
            client_id=str(data["client_id"]).strip(),
            poll_interval_seconds=float(data.get("poll_interval_seconds", 5)),
            clear_on_pause=bool(data.get("clear_on_pause", True)),
            reconnect_interval_seconds=float(data.get("reconnect_interval_seconds", 15)),
            supported_apps=tuple(
                str(a).lower().strip() for a in supported if str(a).strip()
            ),
            presence=PresenceConfig(
                large_text=str(presence_raw.get("large_text", "YouTube Music"))[:128],
                small_text=str(presence_raw.get("small_text", "music.youtube.com"))[:128],
            ),
        )


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


def config_candidates() -> list[Path]:
    paths: list[Path] = []
    env = os.environ.get("YTM_DISCORD_CONFIG")
    if env:
        paths.append(Path(env).expanduser())
    paths.append(install_dir() / "config.json")
    paths.append(user_data_dir() / "config.json")
    paths.append(Path.cwd() / "config.json")

    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def example_config_path() -> Path:
    return install_dir() / "config.example.json"


def config_path() -> Path:
    for path in config_candidates():
        if path.exists():
            return path
    if is_frozen():
        return user_data_dir() / "config.json"
    return install_dir() / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    cfg_path = path or config_path()
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Missing config at {cfg_path}. "
            "Copy config.example.json there and set client_id, or run install.ps1."
        )

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {cfg_path}: {exc}") from exc

    cfg = AppConfig.from_dict(data)

    if not cfg.client_id or cfg.client_id.upper() in {
        "YOUR_DISCORD_APP_CLIENT_ID",
        "CHANGEME",
        "REPLACE_ME",
    }:
        raise ValueError(
            "config.json client_id is not set. Create an app at "
            "https://discord.com/developers/applications and paste the Application ID."
        )
    if not cfg.client_id.isdigit():
        raise ValueError("client_id must be the numeric Discord Application ID")
    if cfg.poll_interval_seconds < 1:
        raise ValueError("poll_interval_seconds must be >= 1")
    if cfg.reconnect_interval_seconds < 1:
        raise ValueError("reconnect_interval_seconds must be >= 1")
    if not cfg.supported_apps:
        raise ValueError("supported_apps must contain at least one entry")
    return cfg


def ensure_user_config_from_example(client_id: str | None = None) -> Path:
    dest = user_data_dir() / "config.json"
    if dest.exists():
        return dest

    user_data_dir().mkdir(parents=True, exist_ok=True)
    example = example_config_path()
    if example.exists():
        data = json.loads(example.read_text(encoding="utf-8-sig"))
    else:
        data = {
            "client_id": "YOUR_DISCORD_APP_CLIENT_ID",
            "poll_interval_seconds": 5,
            "clear_on_pause": True,
            "reconnect_interval_seconds": 15,
            "supported_apps": list(DEFAULT_SUPPORTED_APPS),
            "presence": {
                "large_text": "YouTube Music",
                "small_text": "music.youtube.com",
            },
        }

    if client_id:
        data["client_id"] = client_id

    dest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return dest
