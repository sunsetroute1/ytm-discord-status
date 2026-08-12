from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .services import (
    ALL_ENTRIES,
    BROWSER_WHITELIST,
    DEFAULT_ENABLED_IDS,
    DEFAULT_WHITELIST,
    resolve_whitelist,
)


APP_NAME = "ytm-discord-status"
DISPLAY_MODES = ("alongside", "override", "watching")


@dataclass(frozen=True)
class PresenceConfig:
    large_text: str = "Music"
    small_text: str = ""


@dataclass(frozen=True)
class ListenButtonConfig:
    enabled: bool = True
    label: str = "Listen on YouTube Music"
    # youtube_music | deezer | spotify (search URLs — not synced listen-along)
    target: str = "youtube_music"


@dataclass(frozen=True)
class AppConfig:
    client_id: str
    poll_interval_seconds: float = 5.0
    clear_on_pause: bool = True
    reconnect_interval_seconds: float = 15.0
    display_mode: str = "override"
    show_artwork: bool = True
    artwork_webhook: str | None = None
    whitelist: tuple[str, ...] = DEFAULT_ENABLED_IDS
    allow_browsers: bool = True
    browser_require_catalog_match: bool = True
    listen_button: ListenButtonConfig = field(default_factory=ListenButtonConfig)
    presence: PresenceConfig = field(default_factory=PresenceConfig)

    def resolved_whitelist(self):
        ids = list(self.whitelist)
        if self.allow_browsers:
            for entry in BROWSER_WHITELIST:
                if entry.id not in ids:
                    ids.append(entry.id)
        return resolve_whitelist(tuple(ids))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        if not isinstance(data, dict):
            raise ValueError("config root must be a JSON object")

        presence_raw = data.get("presence") or {}
        if not isinstance(presence_raw, dict):
            raise ValueError("presence must be a JSON object")

        if "client_id" not in data:
            raise ValueError("client_id is required")

        display_mode = str(data.get("display_mode", "override")).strip().lower()
        if display_mode not in DISPLAY_MODES:
            raise ValueError(
                f"display_mode must be one of: {', '.join(DISPLAY_MODES)}"
            )

        webhook = data.get("artwork_webhook")
        webhook_s = str(webhook).strip() if webhook else None
        if webhook_s == "":
            webhook_s = None

        listen_raw = data.get("listen_button") or {}
        if listen_raw is None:
            listen_raw = {}
        if not isinstance(listen_raw, dict):
            raise ValueError("listen_button must be a JSON object")
        listen_target = str(listen_raw.get("target", "youtube_music")).strip().lower()
        if listen_target not in {"youtube_music", "deezer", "spotify"}:
            raise ValueError("listen_button.target must be youtube_music, deezer, or spotify")
        listen_label = str(listen_raw.get("label", "Listen on YouTube Music")).strip()[:32]
        if not listen_label:
            listen_label = "Listen along"

        whitelist = _parse_whitelist(data)

        return cls(
            client_id=str(data["client_id"]).strip(),
            poll_interval_seconds=float(data.get("poll_interval_seconds", 5)),
            clear_on_pause=bool(data.get("clear_on_pause", True)),
            reconnect_interval_seconds=float(data.get("reconnect_interval_seconds", 15)),
            display_mode=display_mode,
            show_artwork=bool(data.get("show_artwork", True)),
            artwork_webhook=webhook_s,
            whitelist=whitelist,
            allow_browsers=bool(data.get("allow_browsers", True)),
            browser_require_catalog_match=bool(
                data.get("browser_require_catalog_match", True)
            ),
            listen_button=ListenButtonConfig(
                enabled=bool(listen_raw.get("enabled", True)),
                label=listen_label,
                target=listen_target,
            ),
            presence=PresenceConfig(
                large_text=str(presence_raw.get("large_text", "Music"))[:128],
                small_text=str(presence_raw.get("small_text", ""))[:128],
            ),
        )


def _parse_whitelist(data: dict[str, Any]) -> tuple[str, ...]:
    """Prefer `whitelist`; migrate legacy `supported_apps` if needed."""
    if "whitelist" in data:
        raw = data.get("whitelist") or []
        if not isinstance(raw, (list, tuple)) or not raw:
            raise ValueError("whitelist must be a non-empty list of service ids")
        ids = tuple(str(x).lower().strip() for x in raw if str(x).strip())
        unknown = [i for i in ids if i not in ALL_ENTRIES]
        if unknown:
            raise ValueError(
                "Unknown whitelist ids: "
                + ", ".join(unknown)
                + ". Known: "
                + ", ".join(sorted(ALL_ENTRIES))
            )
        return ids

    # Legacy: supported_apps was a loose browser/app token list.
    legacy = data.get("supported_apps")
    if isinstance(legacy, (list, tuple)) and legacy:
        mapped: list[str] = []
        for token in legacy:
            t = str(token).lower().strip()
            if not t:
                continue
            if t in ALL_ENTRIES:
                mapped.append(t)
                continue
            # Map old browser tokens → browser ids; music apps kept via defaults.
            for entry in (*DEFAULT_WHITELIST, *BROWSER_WHITELIST):
                if t in entry.tokens or t == entry.id:
                    mapped.append(entry.id)
                    break
        # Always include dedicated music apps when migrating.
        for eid in DEFAULT_ENABLED_IDS:
            if eid not in mapped:
                mapped.append(eid)
        return tuple(dict.fromkeys(mapped))

    return DEFAULT_ENABLED_IDS


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
    if not cfg.whitelist:
        raise ValueError("whitelist must contain at least one service id")
    if not cfg.resolved_whitelist():
        raise ValueError("whitelist resolved to no known services")
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
            "whitelist": list(DEFAULT_ENABLED_IDS),
            "allow_browsers": True,
            "browser_require_catalog_match": True,
            "presence": {"large_text": "Music", "small_text": ""},
        }

    if client_id:
        data["client_id"] = client_id

    dest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return dest
