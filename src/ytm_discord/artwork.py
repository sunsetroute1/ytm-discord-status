from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from .config import user_data_dir
from .media import NowPlaying
from .privacy import clean_artist_for_match, clean_title_for_match

log = logging.getLogger(__name__)

_USER_AGENT = "ytm-discord-status/0.1 (+https://github.com/sunsetroute1/ytm-discord-status)"
_CATBOX = "https://catbox.moe/user/api.php"


def _http_get_json(url: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _url_is_reachable_image(url: str, timeout: float = 15.0) -> bool:
    """Discord's proxy must be able to fetch the image; reject dead hosts early."""
    if not url.startswith("https://"):
        return False
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            chunk = resp.read(64)
            if chunk.startswith(b"\xff\xd8\xff") or chunk.startswith(b"\x89PNG"):
                return True
            if "image/" in ctype and chunk:
                return True
    except Exception as exc:  # noqa: BLE001
        log.debug("Image URL not reachable (%s): %s", url, exc)
    return False


def _normalize_https(url: str) -> str:
    url = str(url).strip()
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


class ArtworkResolver:
    """Resolve a public HTTPS image URL that Discord can actually proxy."""

    def __init__(self, enabled: bool = True, webhook_url: str | None = None) -> None:
        self.enabled = enabled
        self.webhook_url = (webhook_url or "").strip() or None
        self._memory: dict[str, str | None] = {}
        self._cache_path = user_data_dir() / "artwork-cache.json"
        self._disk = self._load_disk()
        self._scrub_bad_cached_hosts()

    def resolve(self, track: NowPlaying) -> str | None:
        if not self.enabled:
            return None

        key = self._track_key(track)
        if key in self._memory:
            return self._memory[key]
        if key in self._disk:
            url = self._disk[key]
            # Re-validate non-CDN hosts; Discord shows "?" for dead/blocked URLs.
            if url and self._is_trusted_cdn(url):
                self._memory[key] = url
                return url
            if url and _url_is_reachable_image(url):
                self._memory[key] = url
                return url
            # Stale/bad entry (e.g. dead catbox) — resolve fresh.
            self._disk.pop(key, None)

        url = None
        try:
            # Prefer CDNs Discord reliably proxies.
            url = self._deezer_lookup(track.artist, track.title, track.album)
            if not url:
                url = self._itunes_lookup(track.artist, track.title, track.album)
            # Exact cover from the media session, hosted where Discord can read it.
            if not url and track.artwork_png:
                if self.webhook_url:
                    url = self._upload_via_discord_webhook(track.artwork_png)
                if not url:
                    url = self._upload_png_catbox(track.artwork_png)
                    if url and not _url_is_reachable_image(url):
                        log.warning("Hosted art URL not fetchable; discarding: %s", url)
                        url = None
        except Exception as exc:  # noqa: BLE001
            log.warning("Artwork resolve failed: %s", exc)
            url = None

        self._memory[key] = url
        self._disk[key] = url
        self._save_disk()
        if url:
            log.info("Artwork URL ready: %s", url)
        else:
            log.info("No artwork found for %s - %s", track.artist, track.title)
        return url

    @staticmethod
    def _track_key(track: NowPlaying) -> str:
        return f"{track.artist}|{track.title}|{track.album}".lower()

    @staticmethod
    def _is_trusted_cdn(url: str) -> bool:
        host = urllib.parse.urlparse(url).netloc.lower()
        return any(
            host.endswith(suffix)
            for suffix in (
                "mzstatic.com",
                "dzcdn.net",
                "deezer.com",
                "discordapp.com",
                "discordapp.net",
                "discord.com",
            )
        )

    def _scrub_bad_cached_hosts(self) -> None:
        """Drop known-unreliable hosts from older builds (catbox often becomes "?")."""
        changed = False
        for key, url in list(self._disk.items()):
            if not url:
                continue
            host = urllib.parse.urlparse(url).netloc.lower()
            if "catbox.moe" in host or "litter.catbox.moe" in host:
                self._disk.pop(key, None)
                changed = True
        if changed:
            self._save_disk()
            log.info("Cleared cached catbox artwork URLs (Discord often cannot proxy them)")

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
            items = list(self._disk.items())[-300:]
            self._cache_path.write_text(json.dumps(dict(items), indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            log.debug("Artwork cache save failed: %s", exc)

    def _deezer_lookup(self, artist: str, title: str, album: str) -> str | None:
        artist = clean_artist_for_match(artist)
        title = clean_title_for_match(title)
        queries = [f"{artist} {title}", f"{artist} {album}" if album else "", title]
        for query in queries:
            query = " ".join(query.split())
            if not query:
                continue
            url = "https://api.deezer.com/search?" + urllib.parse.urlencode(
                {"q": query, "limit": 5}
            )
            try:
                payload = _http_get_json(url)
            except Exception as exc:  # noqa: BLE001
                log.debug("Deezer lookup failed for %r: %s", query, exc)
                continue
            for item in payload.get("data") or []:
                album_obj = item.get("album") or {}
                art = (
                    album_obj.get("cover_xl")
                    or album_obj.get("cover_big")
                    or album_obj.get("cover_medium")
                )
                if art:
                    art = _normalize_https(art)
                    if _url_is_reachable_image(art):
                        return art
        return None

    def _itunes_lookup(self, artist: str, title: str, album: str) -> str | None:
        artist = clean_artist_for_match(artist)
        title = clean_title_for_match(title)
        queries = [f"{artist} {title}", f"{artist} {album}" if album else "", title]
        for query in queries:
            query = " ".join(query.split())
            if not query:
                continue
            url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
                {"term": query, "entity": "song", "limit": 5}
            )
            try:
                payload = _http_get_json(url)
            except Exception as exc:  # noqa: BLE001
                log.debug("iTunes lookup failed for %r: %s", query, exc)
                continue
            for item in payload.get("results") or []:
                art = item.get("artworkUrl100") or item.get("artworkUrl60")
                if not art:
                    continue
                art = _normalize_https(re.sub(r"\d+x\d+bb", "600x600bb", str(art)))
                if _url_is_reachable_image(art):
                    return art
        return None

    def _upload_via_discord_webhook(self, png: bytes) -> str | None:
        """Upload to a Discord webhook so the CDN URL is always proxyable."""
        if not self.webhook_url:
            return None
        digest = hashlib.sha1(png).hexdigest()
        cache_key = f"webhook-sha1:{digest}"
        if self._disk.get(cache_key):
            return self._disk[cache_key]

        boundary = "----ytmDiscordWebhook"
        filename = f"cover-{digest[:10]}.png"
        parts = [
            f"--{boundary}".encode(),
            b'Content-Disposition: form-data; name="payload_json"',
            b"Content-Type: application/json",
            b"",
            b'{"content":null}',
            f"--{boundary}".encode(),
            (
                f'Content-Disposition: form-data; name="files[0]"; filename="{filename}"'
            ).encode(),
            b"Content-Type: image/png",
            b"",
            png,
            f"--{boundary}--".encode(),
            b"",
        ]
        body = b"\r\n".join(parts)
        endpoint = self.webhook_url
        if "wait=" not in endpoint:
            endpoint += ("&" if "?" in endpoint else "?") + "wait=true"
        req = urllib.request.Request(endpoint, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("User-Agent", _USER_AGENT)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            log.warning("Discord webhook art upload failed: %s", exc)
            return None

        attachments = payload.get("attachments") or []
        if not attachments:
            log.warning("Webhook upload returned no attachments")
            return None
        url = _normalize_https(attachments[0].get("url") or "")
        if not url.startswith("https://"):
            return None
        self._disk[cache_key] = url
        return url

    def _upload_png_catbox(self, png: bytes) -> str | None:
        digest = hashlib.sha1(png).hexdigest()
        cache_key = f"sha1:{digest}"
        if self._disk.get(cache_key) and _url_is_reachable_image(str(self._disk[cache_key])):
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
