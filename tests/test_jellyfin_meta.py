from __future__ import annotations

from ytm_discord.jellyfin_meta import JellyfinConfig, enrich_jellyfin_track, format_episode
from ytm_discord.media import NowPlaying


def test_format_episode() -> None:
    assert format_episode(1, 1) == "S1E1"
    assert format_episode(2, 10) == "S2E10"
    assert format_episode(None, 1) == ""


def test_enrich_tvmaze_show_art() -> None:
    track = NowPlaying(
        title="Silo",
        artist="Jellyfin",
        album="",
        app_id="BraveBeta",
        playing=True,
        service_id="jellyfin",
        service_label="Jellyfin",
        duration_seconds=3278,
    )
    enriched = enrich_jellyfin_track(track, JellyfinConfig())
    assert enriched.series_name == "Silo"
    assert enriched.media_kind in {"episode", "video"}
    assert enriched.artwork_url
    assert "tvmaze.com" in enriched.artwork_url
    assert enriched.artist == "Jellyfin"


def test_enrich_applies_api_episode(monkeypatch) -> None:
    track = NowPlaying(
        title="Silo",
        artist="Jellyfin",
        album="",
        app_id="BraveBeta",
        playing=True,
        service_id="jellyfin",
        duration_seconds=3000,
    )

    def fake_session(track, cfg):
        return {
            "media_kind": "episode",
            "series_name": "Silo",
            "episode_name": "Freedom Day",
            "season": 1,
            "episode": 1,
            "episode_code": "S1E1",
            "title": "Silo",
            "artwork_url": "https://example.com/silo.jpg",
        }

    monkeypatch.setattr(
        "ytm_discord.jellyfin_meta._jellyfin_session_meta",
        fake_session,
    )
    enriched = enrich_jellyfin_track(
        track, JellyfinConfig(base_url="http://jf", api_key="x")
    )
    assert enriched.episode_code == "S1E1"
    assert enriched.episode_name == "Freedom Day"
    assert enriched.series_name == "Silo"
    assert enriched.artwork_url == "https://example.com/silo.jpg"
