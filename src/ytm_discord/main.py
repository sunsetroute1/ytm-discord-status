from __future__ import annotations

import logging
import signal
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import config_path, load_config, user_data_dir
from .discord_rpc import DiscordStatus
from .instance import SingleInstance
from .media import MediaPoller


def _setup_logging() -> Path:
    log_dir = user_data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "ytm-discord.log"

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=2,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if sys.stdout and hasattr(sys.stdout, "write"):
        try:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)
            root.addHandler(stream_handler)
        except Exception:  # noqa: BLE001
            pass

    return log_path


def main() -> int:
    log_path = _setup_logging()
    log = logging.getLogger("ytm_discord")

    singleton = SingleInstance()
    if not singleton.acquire():
        log.error("Another ytm-discord instance is already running")
        return 2

    try:
        cfg_file = config_path()
        cfg = load_config(cfg_file)
    except (FileNotFoundError, ValueError, OSError) as exc:
        log.error("%s", exc)
        singleton.release()
        return 1

    status = DiscordStatus(
        cfg.client_id,
        cfg.presence,
        show_artwork=cfg.show_artwork,
        artwork_webhook=cfg.artwork_webhook,
    )
    poller = MediaPoller()
    running = True

    def _stop(*_args: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    log.info("YouTube Music -> Discord status updater started (hidden-capable)")
    log.info("Log file: %s", log_path)
    log.info("Config: %s", cfg_file)
    log.info("Polling every %ss. Display mode: %s", cfg.poll_interval_seconds, cfg.display_mode)

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
        singleton.release()
        log.info("Stopped")

    return 0


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    src = str(root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    raise SystemExit(main())
