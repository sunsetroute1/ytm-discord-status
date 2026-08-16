from __future__ import annotations

from ytm_discord.media import (
    _looks_like_jellyfin_web_playback,
    _looks_like_tv_or_movie,
    _passes_privacy,
)
from ytm_discord.services import WhitelistEntry


def test_tv_movie_heuristics() -> None:
    assert _looks_like_tv_or_movie("Pilot", "Show", "S01E02")
    assert _looks_like_tv_or_movie("Pilot", "Show S02E01", "")
    assert _looks_like_tv_or_movie("Name", "Show", "1x05")
    assert _looks_like_tv_or_movie("Title", "Show", "Season 1 Episode 3")
    assert not _looks_like_tv_or_movie("Clear Day", "The Last Emperor", "Album")


def test_jellyfin_web_heuristic() -> None:
    assert _looks_like_jellyfin_web_playback("", 54 * 60) is True
    assert _looks_like_jellyfin_web_playback("   ", 20 * 60) is True
    assert _looks_like_jellyfin_web_playback("", 5 * 60) is False
    assert _looks_like_jellyfin_web_playback("Cinemassacre", 54 * 60) is False
    assert _looks_like_jellyfin_web_playback("", None) is False


def test_jellyfin_desktop_allows_films_and_tv() -> None:
    entry = WhitelistEntry("jellyfin", "Jellyfin", ("jellyfin",))
    assert (
        _passes_privacy(
            entry,
            "Pilot",
            "Some Show",
            "S01E01",
            "JellyfinMediaPlayer.exe",
            browser_require_catalog_match=True,
        )
        is True
    )


def test_jellyfin_web_in_browser_allows_title_only_longform() -> None:
    entry = WhitelistEntry("brave", "Brave", ("brave",), is_browser=True)
    assert (
        _passes_privacy(
            entry,
            "Silo",
            "",
            "",
            "BraveBeta",
            browser_require_catalog_match=True,
            jellyfin_enabled=True,
            duration_seconds=54 * 60,
        )
        is True
    )


def test_browser_still_blocks_youtube_without_catalog(monkeypatch) -> None:
    entry = WhitelistEntry("brave", "Brave", ("brave",), is_browser=True)
    monkeypatch.setattr(
        "ytm_discord.media.catalog_confirms_music",
        lambda *a, **k: False,
    )
    assert (
        _passes_privacy(
            entry,
            "Commodore 64 - Angry Video Game Nerd (AVGN)",
            "Cinemassacre",
            "",
            "BraveBeta",
            browser_require_catalog_match=True,
            jellyfin_enabled=True,
            duration_seconds=20 * 60,
        )
        is False
    )
