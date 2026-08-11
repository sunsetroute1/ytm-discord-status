from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import user_data_dir
from .media import NowPlaying

log = logging.getLogger(__name__)

_USER_AGENT = "ytm-discord-status/0.1 (+https://github.com/sunsetroute1/ytm-discord-status)"
_CATBOX = "https://catbox.moe/user/api.php"


class ArtworkResolver:
    """Resolve a public HTTPS image URL for Discord Rich Presence."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._memory: dict[str, str | None] = {}
        self._cache_path = user_data_dir() / "artwork-cache.json"
        self._disk = self._load_disk()

    def resolve(self, track: NowPlaying) -> str | None:
        if not self.enabled:
            return None

        key = f"{track.artist}|{track.title}|{track.album}".lower()
        if key in self._memory:
            return self._memory[key]
        if key in self._disk:
            url = self._disk[key]
            self._memory[key] = url
            return url

        url = None
        try:
            if track.artwork_png:
                url = self._upload_png(track.artwork_png)
            if not url:
                url = self._itunes_lookup(track.artist, track.title, track.album)
        except Exception as exc:  # noqa: BLE001
            log.warning("Artwork resolve failed: %s", exc)
            url = None

        self._memory[key] = url
        self._disk[key] = url
        self._save_disk()
        if url:
            log.info("Artwork URL ready for %s - %s", track.artist, track.title)
        else:
            log.info("No artwork found for %s - %s", track.artist, track.title)
        return url

    def _load_disk(self) -> dict[str, str | None]:
        try:
            if self._cache_path.exists():
                data = json.loads(self._cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(k): (str(v) if v else None) for k, v in data.items()}
        except Exception:  # noqa: BLE001
            pass
        return {}

    def _save_disk(self) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            # Keep cache bounded
            items = list(self._disk.items())[-200:]
            self._cache_path.write_text(
                json.dumps(dict(items), indent=2),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("Artwork cache save failed: %s", exc)

    def _upload_png(self, png: bytes) -> str | None:
        digest = hashlib.sha1(png).hexdigest()
        cache_key = f"sha1:{digest}"
        if cache_key in self._disk and self._disk[cache_key]:
            return self._disk[cache_key]

        boundary = "----ytmDiscordBoundary"
        parts = [
            f"--{boundary}".encode(),
            b'Content-Disposition: form-data; name="reqtype"',
            b"",
            b"fileupload",
            f"--{boundary}".encode(),
            b'Content-Disposition: form-data; name="fileToUpload"; filename="cover.png"',
            b"Content-Type: image/png",
            b"",
            png,
            f"--{boundary}--".encode(),
            b"",
        ]
        body = b"\r\n".join(parts)
        req = urllib.request.Request(_CATBOX, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("User-Agent", _USER_AGENT)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                url = resp.read().decode("utf-8", "replace").strip()
        except urllib.error.URLError as exc:
            log.warning("Catbox upload failed: %s", exc)
            return None

        if not url.startswith("https://"):
            log.warning("Unexpected catbox response: %s", url[:120])
            return None

        self._disk[cache_key] = url
        return url

    def _itunes_lookup(self, artist: str, title: str, album: str) -> str | None:
        queries = [
            f"{artist} {title}",
            f"{artist} {album}" if album else "",
            title,
        ]
        for query in queries:
            query = " ".join(query.split())
            if not query:
                continue
            url = (
                "https://itunes.apple.com/search?"
                + urllib.parse.urlencode(
                    {"term": query, "entity": "song", "limit": 5}
                )
            )
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                log.debug("iTunes lookup failed for %r: %s", query, exc)
                continue

            for item in payload.get("results") or []:
                art = item.get("artworkUrl100") or item.get("artworkUrl60")
                if not art:
                    continue
                # Prefer larger art.
                art = re.sub(r"\d+x\d+bb", "600x600bb", str(art))
                if art.startswith("http://"):
                    art = "https://" + art[len("http://") :]
                return art
        return None
