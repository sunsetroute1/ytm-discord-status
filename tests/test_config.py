from __future__ import annotations

import json
from pathlib import Path

from ytm_discord.config import AppConfig, ensure_user_config_from_example, load_config
from ytm_discord.privacy import (
    catalog_confirms_music,
    contains_sensitive_media,
    looks_like_video_site_metadata,
)
from ytm_discord.services import match_whitelist, resolve_whitelist


def test_config_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "client_id": "1536877982222913626",
                "poll_interval_seconds": 3,
                "clear_on_pause": True,
                "whitelist": ["spotify", "deezer", "winamp"],
                "allow_browsers": False,
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.client_id == "1536877982222913626"
    assert cfg.poll_interval_seconds == 3
    assert cfg.whitelist == ("spotify", "deezer", "winamp")
    assert [e.id for e in cfg.resolved_whitelist()] == ["spotify", "deezer", "winamp"]


def test_rejects_placeholder(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"client_id": "YOUR_DISCORD_APP_CLIENT_ID"}),
        encoding="utf-8",
    )
    try:
        load_config(path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "client_id" in str(exc)


def test_rejects_non_numeric(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"client_id": "abc"}), encoding="utf-8")
    try:
        load_config(path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "numeric" in str(exc)


def test_from_dict_defaults() -> None:
    cfg = AppConfig.from_dict({"client_id": "1"})
    assert cfg.clear_on_pause is True
    assert cfg.display_mode == "override"
    assert "spotify" in cfg.whitelist
    assert "deezer" in cfg.whitelist
    assert "winamp" in cfg.whitelist


def test_ensure_user_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    dest = ensure_user_config_from_example(client_id="123456789012345678")
    assert dest.exists()
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["client_id"] == "123456789012345678"


def test_display_mode_override(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"client_id": "1536877982222913626", "display_mode": "alongside"}),
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.display_mode == "alongside"


def test_rejects_bad_display_mode(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"client_id": "1536877982222913626", "display_mode": "nope"}),
        encoding="utf-8",
    )
    try:
        load_config(path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "display_mode" in str(exc)


def test_legacy_supported_apps_migrates() -> None:
    cfg = AppConfig.from_dict(
        {
            "client_id": "1",
            "supported_apps": ["brave", "chrome", "spotify"],
        }
    )
    assert "spotify" in cfg.whitelist
    assert "deezer" in cfg.whitelist  # defaults merged in
    assert "brave" in cfg.whitelist or cfg.allow_browsers


def test_whitelist_match_spotify_and_winamp() -> None:
    entries = resolve_whitelist(("spotify", "deezer", "winamp"))
    assert match_whitelist("Spotify.exe", entries).id == "spotify"
    assert match_whitelist("Winamp", entries).id == "winamp"
    assert match_whitelist("Deezer", entries).id == "deezer"
    assert match_whitelist("BraveBeta", entries) is None
    assert match_whitelist("vlc", entries) is None
    assert match_whitelist("chrome", entries) is None


def test_browser_only_when_enabled() -> None:
    entries = resolve_whitelist(("spotify", "brave"))
    assert match_whitelist("BraveBeta", entries).id == "brave"
    assert match_whitelist("BraveBeta", resolve_whitelist(("spotify",))) is None


def test_sensitive_and_video_filters() -> None:
    assert contains_sensitive_media("pornhub video", "someone")
    assert looks_like_video_site_metadata("Cool Song - YouTube", "Channel", "")
    assert not contains_sensitive_media("Gas", "Simpson Ahuevo")
