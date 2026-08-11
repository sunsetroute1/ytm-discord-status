from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Iterable

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

log = logging.getLogger(__name__)

_MAX_FIELD = 128


@dataclass(frozen=True)
class NowPlaying:
    title: str
    artist: str
    album: str
    app_id: str
    playing: bool
    position_seconds: float | None = None
    duration_seconds: float | None = None
    artwork_png: bytes | None = None

    @property
    def track_key(self) -> tuple[str, str, str]:
        return (self.title, self.artist, self.album)


def _clip(value: str) -> str:
    value = " ".join((value or "").split())
    if len(value) <= _MAX_FIELD:
        return value
    return value[: _MAX_FIELD - 1].rstrip() + "…"


def _matches_supported_app(app_id: str, supported_apps: Iterable[str]) -> bool:
    needle = (app_id or "").lower()
    if not needle:
        return False
    return any(token in needle for token in supported_apps)


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


async def _read_session(session, supported_apps: Iterable[str]) -> NowPlaying | None:
    try:
        app_id = session.source_app_user_model_id or ""
    except Exception as exc:  # noqa: BLE001
        log.debug("Failed reading session app id: %s", exc)
        return None

    if not _matches_supported_app(app_id, supported_apps):
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
        position_seconds=position_seconds,
        duration_seconds=duration_seconds,
        artwork_png=artwork_png,
    )


async def get_now_playing(supported_apps: Iterable[str]) -> NowPlaying | None:
    """Return the best matching YouTube Music-like media session, if any."""
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
        track = await _read_session(session, supported_apps)
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

    def get_now_playing(self, supported_apps: Iterable[str]) -> NowPlaying | None:
        with self._lock:
            return self._loop.run_until_complete(get_now_playing(supported_apps))

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


def get_now_playing_sync(supported_apps: Iterable[str]) -> NowPlaying | None:
    """One-shot helper (tests / scripts). Prefer MediaPoller in the service loop."""
    return asyncio.run(get_now_playing(supported_apps))
