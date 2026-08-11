from __future__ import annotations

import json
from pathlib import Path

from ytm_discord.config import AppConfig, ensure_user_config_from_example, load_config


def test_config_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "client_id": "1536877982222913626",
                "poll_interval_seconds": 3,
                "clear_on_pause": True,
                "supported_apps": ["brave", "chrome"],
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.client_id == "1536877982222913626"
    assert cfg.poll_interval_seconds == 3
    assert cfg.supported_apps == ("brave", "chrome")


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
    assert "brave" in cfg.supported_apps


def test_ensure_user_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    dest = ensure_user_config_from_example(client_id="123456789012345678")
    assert dest.exists()
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["client_id"] == "123456789012345678"
