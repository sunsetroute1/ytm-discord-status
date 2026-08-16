from __future__ import annotations

import asyncio
import logging
import re
import threading
from dataclasses import dataclass
from typing import Iterable

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

from .privacy import (
    catalog_confirms_music,
    contains_sensitive_media,
    looks_like_video_site_metadata,
)
from .services import WhitelistEntry, match_whitelist

log = logging.getLogger(__name__)

_MAX_FIELD = 128


@dataclass(frozen=True)
class NowPlaying:
    title: str
    artist: str
    album: str
    app_id: str
    playing: bool
    service_id: str = ""
    service_label: str = "Music"
    position_seconds: float | None = None
    duration_seconds: float | None = None
    artwork_png: bytes | None = None

    @property
    def track_key(self) -> tuple[str, str, str, str]:
        return (self.title, self.artist, self.album, self.service_id)


def _clip(value: str) -> str:
    value = " ".join((value or "").split())
    if len(value) <= _MAX_FIELD:
        return value
    return value[: _MAX_FIELD - 1].rstrip() + "…"


def _session_id(session) -> str:
    app = getattr(session, "source_app_user_model_id", None) or ""
    return f"{app}:{id(session)}"


async def _read_artwork_png(props) -> bytes | None:
    try:
        thumb = props.thumbnail
    except Exception:  # noqa: BLE001
        return None
    if thumb is None:
        return None
    try:
        from winrt.windows.storage.streams import Buffer, InputStreamOptions

        stream = await thumb.open_read_async()
        size = int(stream.size)
        if size <= 0 or size > 5_000_000:
            return None
        buf = Buffer(size)
        await stream.read_async(buf, size, InputStreamOptions.NONE)
        data = bytes(buf)
        if len(data) < 32:
            return None
        return data
    except Exception as exc:  # noqa: BLE001
        log.debug("Artwork thumbnail read failed: %s", exc)
        return None


def _looks_like_tv_or_movie(title: str, artist: str, album: str) -> bool:
    """Heuristic for Jellyfin/etc. episode/movie metadata that should never be presence."""
    blob = f"{title} {artist} {album}"
    if re.search(r"\bS\d{1,2}\s*E\d{1,3}\b", blob, flags=re.IGNORECASE):
        return True
    if re.search(r"\bSeason\s+\d+\b", blob, flags=re.IGNORECASE) and re.search(
        r"\bEpisode\s+\d+\b", blob, flags=re.IGNORECASE
    ):
        return True
    if re.search(r"\b\d{1,2}x\d{1,3}\b", blob):
        return True
    return False


def _passes_privacy(
    entry: WhitelistEntry,
    title: str,
    artist: str,
    album: str,
    app_id: str,
    *,
    browser_require_catalog_match: bool,
) -> bool:
    if contains_sensitive_media(title, artist, album, app_id, entry.label):
        log.info("Blocked sensitive media metadata from %s", entry.id)
        return False

    if entry.is_browser and looks_like_video_site_metadata(title, artist, album):
        log.info("Blocked video-site metadata from browser session (%s)", entry.id)
        return False

    needs_catalog = entry.require_catalog_match or (
        entry.is_browser and browser_require_catalog_match
    )
    if needs_catalog:
        if _looks_like_tv_or_movie(title, artist, album):
            log.info(
                "Ignored non-music session (TV/movie metadata): %s - %s via %s",
                artist,
                title,
                entry.id,
            )
            return False
        if not catalog_confirms_music(artist, title, album):
            log.info(
                "Ignored session (no music catalog match): %s - %s via %s",
                artist,
                title,
                entry.id,
            )
            return False
    return True


async def _read_session(
    session,
    entries: list[WhitelistEntry],
    *,
    browser_require_catalog_match: bool,
) -> NowPlaying | None:
    try:
        app_id = session.source_app_user_model_id or ""
    except Exception as exc:  # noqa: BLE001
        log.debug("Failed reading session app id: %s", exc)
        return None

    entry = match_whitelist(app_id, entries)
    if entry is None:
        return None

    try:
        props = await session.try_get_media_properties_async()
    except Exception as exc:  # noqa: BLE001
        log.debug("Media properties failed for %s: %s", app_id, exc)
        return None

    if props is None:
        return None

    title = _clip((props.title or "").strip())
    artist = _clip((props.artist or "").strip())
    album = _clip((props.album_title or "").strip())
    if not title or not artist:
        return None

    if not _passes_privacy(
        entry,
        title,
        artist,
        album,
        app_id,
        browser_require_catalog_match=browser_require_catalog_match,
    ):
        return None

    playing = False
    try:
        info = session.get_playback_info()
        playing = bool(info and info.playback_status == PlaybackStatus.PLAYING)
    except Exception as exc:  # noqa: BLE001
        log.debug("Playback info failed for %s: %s", app_id, exc)

    position_seconds: float | None = None
    duration_seconds: float | None = None
    try:
        timeline = session.get_timeline_properties()
        if timeline is not None:
            position_seconds = max(0.0, float(timeline.position.total_seconds()))
            end = float(timeline.end_time.total_seconds())
            start = float(timeline.start_time.total_seconds())
            if end > start:
                duration_seconds = max(0.0, end - start)
            if duration_seconds is not None and duration_seconds > 24 * 3600:
                duration_seconds = None
                position_seconds = None
            elif (
                position_seconds is not None
                and duration_seconds is not None
                and position_seconds > duration_seconds + 2
            ):
                position_seconds = duration_seconds
    except Exception as exc:  # noqa: BLE001
        log.debug("Timeline read failed for %s: %s", app_id, exc)
        position_seconds = None
        duration_seconds = None

    artwork_png = await _read_artwork_png(props)

    return NowPlaying(
        title=title,
        artist=artist,
        album=album,
        app_id=app_id,
        playing=playing,
        service_id=entry.id,
        service_label=entry.label if not entry.is_browser else "Music",
        position_seconds=position_seconds,
        duration_seconds=duration_seconds,
        artwork_png=artwork_png,
    )


async def get_now_playing(
    entries: list[WhitelistEntry],
    *,
    browser_require_catalog_match: bool = True,
) -> NowPlaying | None:
    """Return the best whitelist-matched music session, if any."""
    manager = await MediaManager.request_async()
    try:
        sessions = list(manager.get_sessions())
    except Exception as exc:  # noqa: BLE001
        log.warning("Unable to enumerate media sessions: %s", exc)
        return None

    current = None
    try:
        current = manager.get_current_session()
    except Exception:  # noqa: BLE001
        current = None

    ordered = []
    seen: set[str] = set()
    if current is not None:
        ordered.append(current)
        seen.add(_session_id(current))
    for session in sessions:
        sid = _session_id(session)
        if sid in seen:
            continue
        seen.add(sid)
        ordered.append(session)

    playing_match: NowPlaying | None = None
    paused_match: NowPlaying | None = None

    for session in ordered:
        track = await _read_session(
            session,
            entries,
            browser_require_catalog_match=browser_require_catalog_match,
        )
        if track is None:
            continue
        if track.playing and playing_match is None:
            playing_match = track
        elif not track.playing and paused_match is None:
            paused_match = track

    return playing_match or paused_match


class MediaPoller:
    """Reuse one asyncio loop so we don't create/destroy loops every poll."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop = asyncio.new_event_loop()

    def get_now_playing(
        self,
        entries: list[WhitelistEntry],
        *,
        browser_require_catalog_match: bool = True,
    ) -> NowPlaying | None:
        with self._lock:
            return self._loop.run_until_complete(
                get_now_playing(
                    entries,
                    browser_require_catalog_match=browser_require_catalog_match,
                )
            )

    def close(self) -> None:
        with self._lock:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                try:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                except Exception:  # noqa: BLE001
                    pass
            self._loop.close()


def get_now_playing_sync(
    entries: Iterable[WhitelistEntry],
    *,
    browser_require_catalog_match: bool = True,
) -> NowPlaying | None:
    return asyncio.run(
        get_now_playing(
            list(entries),
            browser_require_catalog_match=browser_require_catalog_match,
        )
    )
