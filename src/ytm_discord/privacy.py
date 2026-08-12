from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

log = logging.getLogger(__name__)

_USER_AGENT = "ytm-discord-status/0.1 (+https://github.com/sunsetroute1/ytm-discord-status)"

# Extra hard reject even if somehow whitelisted (e.g. user added a browser).
SENSITIVE_KEYWORDS = (
    "pornhub",
    "porn hub",
    "xvideos",
    "xhamster",
    "xnxx",
    "onlyfans",
    "only fans",
    "chaturbate",
    "stripchat",
    "manyvids",
    "fansly",
    "redtube",
    "youporn",
    "spankbang",
    "hentai",
    "nhentai",
    "rule34",
    "eporner",
)

VIDEO_SITE_MARKERS = (
    " - youtube",
    " | youtube",
    " - twitch",
    " | twitch",
    "netflix",
    "disney+",
    "disney plus",
    "hulu",
    "prime video",
    "hbo max",
    "crunchyroll",
    "tiktok",
    "dailymotion",
)


def _norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def contains_sensitive_media(*parts: str) -> bool:
    blob = " ".join(_norm(p) for p in parts if p)
    return bool(blob) and any(k in blob for k in SENSITIVE_KEYWORDS)


def looks_like_video_site_metadata(title: str, artist: str, album: str) -> bool:
    raw = f"{title} {artist} {album}".lower()
    # Check before punctuation-stripping so "Song - YouTube" still matches.
    if any(
        marker in raw
        for marker in (
            " - youtube",
            " | youtube",
            "— youtube",
            " – youtube",
            "youtube.com",
        )
    ):
        return True
    blob = " ".join(_norm(p) for p in (title, artist, album) if p)
    return any(marker in blob for marker in VIDEO_SITE_MARKERS)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _http_get_json(url: str, timeout: float = 12.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def catalog_confirms_music(artist: str, title: str, album: str = "") -> bool:
    """True only if Deezer/iTunes finds a matching song — used for browser whitelist entries."""
    artist = (artist or "").strip()
    title = (title or "").strip()
    if not artist or not title:
        return False

    for query in (f"{artist} {title}", f"{artist} {album}" if album else ""):
        query = " ".join(query.split())
        if not query:
            continue
        if _deezer_confirms(query, artist, title) or _itunes_confirms(query, artist, title):
            return True
    return False


def _deezer_confirms(query: str, artist: str, title: str) -> bool:
    url = "https://api.deezer.com/search?" + urllib.parse.urlencode({"q": query, "limit": 8})
    try:
        payload = _http_get_json(url)
    except Exception as exc:  # noqa: BLE001
        log.debug("Deezer catalog check failed: %s", exc)
        return False
    for item in payload.get("data") or []:
        rt = str(item.get("title") or "")
        ra = str((item.get("artist") or {}).get("name") or "")
        if _similarity(title, rt) >= 0.55 and _similarity(artist, ra) >= 0.45:
            return True
        if _similarity(title, rt) >= 0.72 and (
            _norm(artist) in _norm(ra) or _norm(ra) in _norm(artist)
        ):
            return True
    return False


def _itunes_confirms(query: str, artist: str, title: str) -> bool:
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": query, "entity": "song", "limit": 8}
    )
    try:
        payload = _http_get_json(url)
    except Exception as exc:  # noqa: BLE001
        log.debug("iTunes catalog check failed: %s", exc)
        return False
    for item in payload.get("results") or []:
        rt = str(item.get("trackName") or "")
        ra = str(item.get("artistName") or "")
        if _similarity(title, rt) >= 0.55 and _similarity(artist, ra) >= 0.45:
            return True
        if _similarity(title, rt) >= 0.72 and (
            _norm(artist) in _norm(ra) or _norm(ra) in _norm(artist)
        ):
            return True
    return False
