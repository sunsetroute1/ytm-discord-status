from __future__ import annotations

import json
import logging
import re
import time
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

# Cache catalog decisions so we don't hammer APIs / spam logs every poll.
_CATALOG_CACHE: dict[str, tuple[float, bool]] = {}
_CATALOG_TTL_SECONDS = 30 * 60


def _norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _strip_features(title: str) -> str:
    """Remove (feat. X) / [ft. X] clutter that tanks similarity for short titles."""
    cleaned = re.sub(
        r"\s*[\(\[][^)\]]*\b(feat\.?|ft\.?|featuring|with|prod\.?)\b[^)\]]*[\)\]]",
        "",
        title or "",
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*-\s*(feat\.?|ft\.?|featuring)\b.*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" -–—")


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


def _titles_match(left: str, right: str) -> bool:
    if _similarity(left, right) >= 0.52:
        return True
    a = _norm(_strip_features(left))
    b = _norm(_strip_features(right))
    if not a or not b:
        return False
    if a == b:
        return True
    if _similarity(a, b) >= 0.52:
        return True
    # "party" vs "party feat rmr" after strip, or still-prefixed catalog titles
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 3 and (longer == shorter or longer.startswith(shorter + " ")):
        return True
    return False


def _artists_match(left: str, right: str) -> bool:
    if _similarity(left, right) >= 0.45:
        return True
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return False
    return a in b or b in a


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

    cache_key = f"{artist.lower()}|{title.lower()}|{album.lower()}"
    now = time.monotonic()
    cached = _CATALOG_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _CATALOG_TTL_SECONDS:
        return cached[1]

    ok = False
    for query in (f"{artist} {title}", f"{artist} {album}" if album else ""):
        query = " ".join(query.split())
        if not query:
            continue
        if _deezer_confirms(query, artist, title) or _itunes_confirms(query, artist, title):
            ok = True
            break

    _CATALOG_CACHE[cache_key] = (now, ok)
    # Bound cache size
    if len(_CATALOG_CACHE) > 500:
        oldest = sorted(_CATALOG_CACHE.items(), key=lambda kv: kv[1][0])[:100]
        for key, _ in oldest:
            _CATALOG_CACHE.pop(key, None)
    return ok


def _result_matches(artist: str, title: str, result_artist: str, result_title: str) -> bool:
    if _artists_match(artist, result_artist) and _titles_match(title, result_title):
        return True
    # Strong title alone with soft artist containment
    if _titles_match(title, result_title) and (
        _norm(artist) in _norm(result_artist) or _norm(result_artist) in _norm(artist)
    ):
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
        if _result_matches(artist, title, ra, rt):
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
        if _result_matches(artist, title, ra, rt):
            return True
    return False
