from __future__ import annotations

from ytm_discord.media import _looks_like_tv_or_movie, _passes_privacy
from ytm_discord.services import WhitelistEntry


def test_tv_movie_heuristics() -> None:
    assert _looks_like_tv_or_movie("Pilot", "Show", "S01E02")
    assert _looks_like_tv_or_movie("Pilot", "Show S02E01", "")
    assert _looks_like_tv_or_movie("Name", "Show", "1x05")
    assert _looks_like_tv_or_movie("Title", "Show", "Season 1 Episode 3")
    assert not _looks_like_tv_or_movie("Clear Day", "The Last Emperor", "Album")


def test_jellyfin_blocks_episode_without_catalog(monkeypatch) -> None:
    entry = WhitelistEntry(
        "jellyfin",
        "Jellyfin",
        ("jellyfin",),
        require_catalog_match=True,
    )
    assert (
        _passes_privacy(
            entry,
            "Pilot",
            "Some Show",
            "S01E01",
            "JellyfinMediaPlayer.exe",
            browser_require_catalog_match=True,
        )
        is False
    )


def test_jellyfin_allows_catalog_music(monkeypatch) -> None:
    entry = WhitelistEntry(
        "jellyfin",
        "Jellyfin",
        ("jellyfin",),
        require_catalog_match=True,
    )
    monkeypatch.setattr(
        "ytm_discord.media.catalog_confirms_music",
        lambda *a, **k: True,
    )
    assert (
        _passes_privacy(
            entry,
            "Get Lucky",
            "Daft Punk",
            "Random Access Memories",
            "JellyfinMediaPlayer.exe",
            browser_require_catalog_match=True,
        )
        is True
    )
