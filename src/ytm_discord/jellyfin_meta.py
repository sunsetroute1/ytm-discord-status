from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .media import NowPlaying

log = logging.getLogger(__name__)

_USER_AGENT = "ytm-discord-status/0.1 (+https://github.com/sunsetroute1/ytm-discord-status)"
_TVMAZE_CACHE: dict[str, tuple[float, dict | None]] = {}
_TVMAZE_TTL = 6 * 3600
_SESSION_CACHE: dict[str, tuple[float, dict | None]] = {}
_SESSION_TTL = 8


@dataclass(frozen=True)
class JellyfinConfig:
    base_url: str = ""
    api_key: str = ""
    # Optional Discord Application ID named "Jellyfin" so presence isn't under YouTube Music.
    client_id: str = ""


def _http_get_json(url: str, headers: dict[str, str] | None = None, timeout: float = 10.0) -> dict | list:
    hdrs = {"User-Agent": _USER_AGENT, **(headers or {})}
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _norm_url(base: str) -> str:
    return (base or "").strip().rstrip("/")


def format_episode(season: int | None, episode: int | None) -> str:
    if season is None or episode is None:
        return ""
    return f"S{int(season)}E{int(episode)}"


def enrich_jellyfin_track(track: NowPlaying, cfg: JellyfinConfig) -> NowPlaying:
    """Fill series/episode/art for Jellyfin playback (API first, TVMaze fallback)."""
    if track.service_id != "jellyfin":
        return track

    api_meta = _jellyfin_session_meta(track, cfg) if cfg.base_url and cfg.api_key else None
    if api_meta:
        return _apply_meta(track, api_meta)

    show = (track.title or "").strip()
    if track.artist and track.artist.lower() not in {"jellyfin", "music", "unknown"}:
        if re.search(r"S\d+E\d+", track.title or "", re.I):
            show = track.artist
        elif not re.search(r"S\d+E\d+", track.artist or "", re.I):
            show = track.artist if len(track.artist) >= len(track.title) else track.title

    tv = _tvmaze_show(show) if show else None
    if not tv:
        return track.replace(
            media_kind="video",
            series_name=show or track.title,
            episode_code="",
            artwork_url=track.artwork_url,
        )

    return track.replace(
        media_kind="episode",
        series_name=str(tv.get("name") or show),
        episode_code="",
        episode_name="",
        artwork_url=_tvmaze_image(tv) or track.artwork_url,
        title=str(tv.get("name") or show),
        artist="Jellyfin",
    )


def _apply_meta(track: NowPlaying, meta: dict) -> NowPlaying:
    series = str(meta.get("series_name") or "").strip()
    ep_name = str(meta.get("episode_name") or "").strip()
    season = meta.get("season")
    episode = meta.get("episode")
    code = format_episode(
        int(season) if season is not None else None,
        int(episode) if episode is not None else None,
    )
    kind = str(meta.get("media_kind") or "video")
    art = str(meta.get("artwork_url") or "") or None
    title = series or str(meta.get("title") or track.title)
    if kind == "movie":
        title = str(meta.get("title") or track.title)
        series = title
        code = ""
        ep_name = ""
    return track.replace(
        media_kind=kind,
        series_name=series or title,
        season=int(season) if season is not None else None,
        episode=int(episode) if episode is not None else None,
        episode_code=code,
        episode_name=ep_name,
        artwork_url=art or track.artwork_url,
        title=title,
        artist="Jellyfin",
        album=code or track.album,
    )


def _jellyfin_session_meta(track: NowPlaying, cfg: JellyfinConfig) -> dict | None:
    base = _norm_url(cfg.base_url)
    key = f"{base}|{track.title}|{track.duration_seconds}"
    now = time.monotonic()
    cached = _SESSION_CACHE.get(key)
    if cached and (now - cached[0]) < _SESSION_TTL:
        return cached[1]

    url = f"{base}/Sessions?" + urllib.parse.urlencode({"ActiveWithinSeconds": 120})
    headers = {
        "X-Emby-Token": cfg.api_key,
        "Authorization": f'MediaBrowser Token="{cfg.api_key}"',
    }
    try:
        payload = _http_get_json(url, headers=headers)
    except Exception as exc:  # noqa: BLE001
        log.debug("Jellyfin Sessions lookup failed: %s", exc)
        _SESSION_CACHE[key] = (now, None)
        return None

    if not isinstance(payload, list):
        _SESSION_CACHE[key] = (now, None)
        return None

    needle = (track.title or "").strip().lower()
    best: dict | None = None
    for session in payload:
        item = session.get("NowPlayingItem") or {}
        if not item:
            continue
        names = [
            str(item.get("Name") or ""),
            str(item.get("SeriesName") or ""),
            str(item.get("Album") or ""),
        ]
        series = str(item.get("SeriesName") or "").lower()
        if needle and needle not in " ".join(names).lower():
            if not (series and (needle == series or needle in series)):
                continue
        best = _meta_from_item(item, base, cfg.api_key)
        if best:
            break

    _SESSION_CACHE[key] = (now, best)
    if best:
        log.info(
            "Jellyfin API enriched: %s %s",
            best.get("series_name") or best.get("title"),
            best.get("episode_code") or best.get("media_kind"),
        )
    return best


def _meta_from_item(item: dict, base: str, api_key: str) -> dict:
    item_type = str(item.get("Type") or "")
    item_id = str(item.get("Id") or "")
    series_id = str(item.get("SeriesId") or "")
    image_id = series_id or item_id
    art = ""
    if image_id:
        art = (
            f"{base}/Items/{image_id}/Images/Primary"
            f"?fillHeight=600&fillWidth=600&quality=90&api_key={urllib.parse.quote(api_key)}"
        )
    if item_type == "Episode":
        season = item.get("ParentIndexNumber")
        episode = item.get("IndexNumber")
        return {
            "media_kind": "episode",
            "series_name": item.get("SeriesName") or item.get("Album") or "",
            "episode_name": item.get("Name") or "",
            "season": season,
            "episode": episode,
            "episode_code": format_episode(
                int(season) if season is not None else None,
                int(episode) if episode is not None else None,
            ),
            "title": item.get("SeriesName") or item.get("Name") or "",
            "artwork_url": art,
        }
    if item_type == "Movie":
        return {
            "media_kind": "movie",
            "title": item.get("Name") or "",
            "series_name": item.get("Name") or "",
            "artwork_url": art,
        }
    artists = item.get("Artists") or []
    artist = ""
    if isinstance(artists, list) and artists:
        artist = str(artists[0])
    return {
        "media_kind": "audio" if item_type == "Audio" else "video",
        "title": item.get("Name") or "",
        "series_name": item.get("AlbumArtist") or artist,
        "artwork_url": art,
    }


def _tvmaze_show(query: str) -> dict | None:
    q = " ".join((query or "").split())
    if not q:
        return None
    key = q.lower()
    now = time.monotonic()
    cached = _TVMAZE_CACHE.get(key)
    if cached and (now - cached[0]) < _TVMAZE_TTL:
        return cached[1]
    url = "https://api.tvmaze.com/singlesearch/shows?" + urllib.parse.urlencode({"q": q})
    try:
        payload = _http_get_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            _TVMAZE_CACHE[key] = (now, None)
            return None
        log.debug("TVMaze lookup failed for %r: %s", q, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        log.debug("TVMaze lookup failed for %r: %s", q, exc)
        return None
    if not isinstance(payload, dict):
        _TVMAZE_CACHE[key] = (now, None)
        return None
    _TVMAZE_CACHE[key] = (now, payload)
    return payload


def _tvmaze_image(show: dict) -> str | None:
    image = show.get("image") or {}
    for key in ("original", "medium"):
        url = image.get(key)
        if url and str(url).startswith("http"):
            return str(url).replace("http://", "https://")
    return None
