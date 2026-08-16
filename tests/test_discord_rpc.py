from __future__ import annotations

from ytm_discord.discord_rpc import DiscordStatus
from ytm_discord.config import PresenceConfig
from ytm_discord.jellyfin_meta import DEFAULT_JELLYFIN_CLIENT_ID
from ytm_discord.media import NowPlaying
from pypresence import ActivityType


def _track(**kwargs) -> NowPlaying:
    base = dict(
        title="Silo",
        artist="Jellyfin",
        album="",
        app_id="BraveBeta",
        playing=True,
        service_id="jellyfin",
        service_label="Jellyfin",
        media_kind="video",
    )
    base.update(kwargs)
    return NowPlaying(**base)


def test_jellyfin_uses_jellyfin_client_id() -> None:
    status = DiscordStatus(
        "1536877982222913626",
        PresenceConfig(),
        jellyfin=None,
    )
    track = _track()
    assert status._client_id_for(track) == DEFAULT_JELLYFIN_CLIENT_ID
    music = _track(service_id="spotify", media_kind="music", title="Song", artist="A")
    assert status._client_id_for(music) == "1536877982222913626"


def test_override_uses_playing_for_jellyfin() -> None:
    track = _track()
    assert (
        DiscordStatus._activity_type("override", track) == ActivityType.PLAYING
    )
    assert (
        DiscordStatus._activity_type("watching", track) == ActivityType.WATCHING
    )
    assert (
        DiscordStatus._activity_type("alongside", track) == ActivityType.WATCHING
    )
