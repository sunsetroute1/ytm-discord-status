from __future__ import annotations

import logging
import time
from typing import Any

from pypresence import ActivityType, Presence
from pypresence.exceptions import DiscordNotFound, InvalidID, InvalidPipe

from .artwork import ArtworkResolver
from .config import AppConfig, PresenceConfig
from .media import NowPlaying

log = logging.getLogger(__name__)


class DiscordStatus:
    def __init__(
        self,
        client_id: str,
        presence: PresenceConfig,
        show_artwork: bool = True,
        artwork_webhook: str | None = None,
    ) -> None:
        self._client_id = client_id
        self._presence = presence
        self._artwork = ArtworkResolver(enabled=show_artwork, webhook_url=artwork_webhook)
        self._rpc: Presence | None = None
        self._connected = False
        self._last_track_key: tuple[str, str, str, str] | None = None
        self._last_art_url: str | None = None
        self._last_connect_attempt = 0.0
        self._had_presence = False

    @staticmethod
    def _activity_type(display_mode: str) -> ActivityType:
        if display_mode == "override":
            return ActivityType.PLAYING
        if display_mode == "watching":
            return ActivityType.WATCHING
        return ActivityType.LISTENING

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, force: bool = False, min_interval: float = 15.0) -> bool:
        now = time.monotonic()
        if (
            not force
            and self._last_connect_attempt
            and (now - self._last_connect_attempt) < min_interval
            and not self._connected
        ):
            return False

        self._last_connect_attempt = now
        self._close_socket_quiet()

        try:
            rpc = Presence(self._client_id)
            rpc.connect()
            self._rpc = rpc
            self._connected = True
            # Force a fresh presence push after reconnect.
            self._last_track_key = None
            log.info("Connected to Discord IPC")
            return True
        except InvalidID:
            self._rpc = None
            self._connected = False
            log.error(
                "Discord rejected client_id %s. Check the Application ID in config.json.",
                self._client_id,
            )
            return False
        except (DiscordNotFound, InvalidPipe, FileNotFoundError, ConnectionError, OSError) as exc:
            self._rpc = None
            self._connected = False
            log.warning("Discord not available yet: %s", exc)
            return False
        except Exception as exc:  # noqa: BLE001
            self._rpc = None
            self._connected = False
            log.warning("Failed to connect to Discord: %s", exc)
            return False

    def ensure_connected(self, min_interval: float = 15.0) -> bool:
        if self._connected and self._rpc is not None:
            return True
        return self.connect(min_interval=min_interval)

    def clear(self) -> None:
        if not self._had_presence and self._last_track_key is None:
            return
        if not self.ensure_connected() or self._rpc is None:
            # Drop local state so we retry a full update later.
            self._last_track_key = None
            self._had_presence = False
            return
        try:
            self._rpc.clear()
            self._last_track_key = None
            self._last_art_url = None
            self._had_presence = False
            log.info("Cleared Discord presence")
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to clear presence: %s", exc)
            self._mark_disconnected()

    def update(self, track: NowPlaying, cfg: AppConfig) -> None:
        if not track.playing and cfg.clear_on_pause:
            self.clear()
            return

        activity_type = self._activity_type(cfg.display_mode)
        track_key = (*track.track_key, cfg.display_mode)
        art_url = self._artwork.resolve(track)

        # Skip only when track AND artwork are unchanged (art can arrive after first poll).
        if (
            track_key == self._last_track_key
            and art_url == self._last_art_url
            and self._connected
        ):
            return

        if not self.ensure_connected(cfg.reconnect_interval_seconds) or self._rpc is None:
            return

        # details = song, state = artist
        payload: dict[str, Any] = {
            "details": track.title,
            "state": track.artist,
            "large_text": track.album or self._presence.large_text,
            "activity_type": activity_type,
        }

        if art_url:
            payload["large_image"] = art_url

        if (
            track.playing
            and track.position_seconds is not None
            and track.duration_seconds
            and track.duration_seconds > 1
        ):
            now = int(time.time())
            start = now - int(track.position_seconds)
            end = start + int(track.duration_seconds)
            if end > start:
                payload["start"] = start
                payload["end"] = end

        try:
            self._rpc.update(**payload)
            self._last_track_key = track_key
            self._last_art_url = art_url
            self._had_presence = True
            status = "playing" if track.playing else "paused"
            log.info(
                "Presence updated (%s/%s): %s - %s%s",
                status,
                cfg.display_mode,
                track.artist,
                track.title,
                f" [art={art_url}]" if art_url else " [no art]",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to update presence: %s", exc)
            self._mark_disconnected()

    def close(self) -> None:
        if self._rpc is not None:
            try:
                if self._had_presence:
                    self._rpc.clear()
            except Exception:  # noqa: BLE001
                pass
            self._close_socket_quiet()
        self._mark_disconnected()
        self._had_presence = False

    def _mark_disconnected(self) -> None:
        self._connected = False
        self._rpc = None
        self._last_track_key = None
        self._last_art_url = None

    def _close_socket_quiet(self) -> None:
        if self._rpc is None:
            return
        try:
            self._rpc.close()
        except Exception:  # noqa: BLE001
            pass
        self._rpc = None
