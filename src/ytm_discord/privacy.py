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
# Values: (monotonic_ts, confirmed: bool, from_api_error: bool)
_CATALOG_CACHE: dict[str, tuple[float, bool, bool]] = {}
_CATALOG_TTL_SECONDS = 30 * 60
_CATALOG_ERROR_TTL_SECONDS = 45


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


_VIDEO_TAG = (
    r"official\s+(?:music\s+)?video|official\s+audio|lyric\s+video|lyrics?\s+video|"
    r"music\s+video|visualizer|audio\s+only|\baudio\b|color\s*coded\s+lyrics?|"
    r"\bhd\b|\b4k\b|\b8k\b|\bmv\b|\bpv\b|explicit|clean|"
    r"(?:\d{2,4}\s+)?remaster(?:ed)?"
)


def clean_title_for_match(title: str) -> str:
    """Strip YTM/YouTube clutter that breaks Deezer/iTunes matching."""
    cleaned = title or ""
    # Fullwidth / fancy brackets used on some uploads.
    cleaned = cleaned.replace("【", "[").replace("】", "]").replace("（", "(").replace("）", ")")

    # Bracketed / parenthetical tags anywhere, not only at end.
    cleaned = re.sub(
        rf"\s*[\(\[]\s*(?:{_VIDEO_TAG})\s*[\)\]]",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Dash / pipe / em-dash suffixes: "Song - Official Video", "Song | Official Audio"
    cleaned = re.sub(
        rf"\s*[-|–—]\s*(?:{_VIDEO_TAG})\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Trailing bare tags without brackets (rarer, but seen).
    cleaned = re.sub(
        rf"\s+(?:{_VIDEO_TAG})\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = _strip_features(cleaned)
    return cleaned.strip(" -–—|")


def clean_artist_for_match(artist: str) -> str:
    """Strip YouTube Topic / VEVO channel suffixes from SMTC artist fields."""
    cleaned = (artist or "").strip()
    cleaned = re.sub(r"\s*-\s*topic\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\s-]*vevo\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" -–—")


# Back-compat alias used by earlier builds / tests.
def _strip_video_suffixes(title: str) -> str:
    return clean_title_for_match(title)


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
    left_c = clean_title_for_match(left)
    right_c = clean_title_for_match(right)
    if _similarity(left_c, right_c) >= 0.52:
        return True
    a = _norm(_strip_features(left_c))
    b = _norm(_strip_features(right_c))
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
    left_c = clean_artist_for_match(left)
    right_c = clean_artist_for_match(right)
    if _similarity(left_c, right_c) >= 0.45:
        return True
    a, b = _norm(left_c), _norm(right_c)
    if not a or not b:
        return False
    return a in b or b in a


def _http_get_json(url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def catalog_confirms_music(artist: str, title: str, album: str = "") -> bool:
    """True only if Deezer/iTunes finds a matching song — used for browser whitelist entries."""
    raw_artist = (artist or "").strip()
    raw_title = (title or "").strip()
    artist = clean_artist_for_match(raw_artist)
    title = clean_title_for_match(raw_title)
    if not artist or not title:
        return False

    cache_key = f"{raw_artist.lower()}|{raw_title.lower()}|{album.lower()}"
    now = time.monotonic()
    cached = _CATALOG_CACHE.get(cache_key)
    if cached:
        ts, value, from_error = cached
        ttl = _CATALOG_ERROR_TTL_SECONDS if from_error else _CATALOG_TTL_SECONDS
        if (now - ts) < ttl:
            return value

    ok = False
    api_reachable = False
    queries = [
        f"{artist} {title}",
        f"{artist} {album}" if album else "",
        title,  # label/channel often stuffed into artist; title alone still matches catalogs
    ]
    for query in queries:
        query = " ".join(query.split())
        if not query:
            continue
        deezer = _deezer_confirms(query, artist, title)
        if deezer is not None:
            api_reachable = True
            if deezer:
                ok = True
                break
        itunes = _itunes_confirms(query, artist, title)
        if itunes is not None:
            api_reachable = True
            if itunes:
                ok = True
                break

    if not api_reachable:
        # Network/API blip — do not poison the cache for 30 minutes.
        _CATALOG_CACHE[cache_key] = (now, False, True)
        log.debug("Catalog APIs unreachable for %s - %s; short-caching miss", artist, title)
        return False

    _CATALOG_CACHE[cache_key] = (now, ok, False)
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
        _norm(clean_artist_for_match(artist)) in _norm(clean_artist_for_match(result_artist))
        or _norm(clean_artist_for_match(result_artist)) in _norm(clean_artist_for_match(artist))
    ):
        return True
    return False


def _deezer_confirms(query: str, artist: str, title: str) -> bool | None:
    """True/False on success; None if the API request failed."""
    url = "https://api.deezer.com/search?" + urllib.parse.urlencode({"q": query, "limit": 8})
    try:
        payload = _http_get_json(url)
    except Exception as exc:  # noqa: BLE001
        log.debug("Deezer catalog check failed: %s", exc)
        return None
    for item in payload.get("data") or []:
        rt = str(item.get("title") or "")
        ra = str((item.get("artist") or {}).get("name") or "")
        if _result_matches(artist, title, ra, rt):
            return True
        # YTM often puts the label in artist (e.g. "ANTI- Records") while catalogs
        # have the real performer. Allow unique-ish exact title matches.
        if _exact_title_ok(title, rt):
            return True
    return False


def _itunes_confirms(query: str, artist: str, title: str) -> bool | None:
    """True/False on success; None if the API request failed."""
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": query, "entity": "song", "limit": 8}
    )
    try:
        payload = _http_get_json(url)
    except Exception as exc:  # noqa: BLE001
        log.debug("iTunes catalog check failed: %s", exc)
        return None
    for item in payload.get("results") or []:
        rt = str(item.get("trackName") or "")
        ra = str(item.get("artistName") or "")
        if _result_matches(artist, title, ra, rt):
            return True
        if _exact_title_ok(title, rt):
            return True
    return False


def _exact_title_ok(left: str, right: str) -> bool:
    """Exact title match for longer titles (label/channel artist mismatch)."""
    a = _norm(clean_title_for_match(left))
    b = _norm(clean_title_for_match(right))
    if not a or a != b:
        return False
    # Avoid short ambiguous titles ("Party", "Stay", "Hello").
    return len(a) >= 10 or len(a.split()) >= 3
