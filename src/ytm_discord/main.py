from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path

from .config import config_path, load_config
from .discord_rpc import DiscordStatus
from .media import MediaPoller


def _setup_logging() -> None:
    # Avoid UnicodeEncodeError on Windows cp1252 consoles.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    _setup_logging()
    log = logging.getLogger("ytm_discord")

    try:
        cfg_file = config_path()
        cfg = load_config(cfg_file)
    except (FileNotFoundError, ValueError, OSError) as exc:
        log.error("%s", exc)
        return 1

    status = DiscordStatus(cfg.client_id, cfg.presence)
    poller = MediaPoller()
    running = True

    def _stop(*_args: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    log.info("YouTube Music -> Discord status updater started")
    log.info("Config: %s", cfg_file)
    log.info("Polling every %ss. Play something on music.youtube.com.", cfg.poll_interval_seconds)
    log.info(
        "Display mode: %s (alongside=Listening with game on profile, "
        "override=Playing to compete with game status, watching=Watching)",
        cfg.display_mode,
    )

    had_track = False

    try:
        while running:
            try:
                track = poller.get_now_playing(cfg.supported_apps)
                if track is None:
                    if had_track:
                        status.clear()
                        had_track = False
                        log.info("No matching media session - presence cleared")
                else:
                    had_track = True
                    status.update(track, cfg)
            except Exception as exc:  # noqa: BLE001
                log.warning("Poll failed: %s", exc)

            end = time.time() + cfg.poll_interval_seconds
            while running and time.time() < end:
                time.sleep(0.2)
    finally:
        status.close()
        poller.close()
        log.info("Stopped")

    return 0


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    raise SystemExit(main())
