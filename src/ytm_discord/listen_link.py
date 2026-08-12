from __future__ import annotations

import urllib.parse

from .media import NowPlaying
from .privacy import clean_artist_for_match, clean_title_for_match


def listen_url(track: NowPlaying, target: str = "youtube_music") -> str:
    """Build a public HTTPS search/listen URL for the current track."""
    artist = clean_artist_for_match(track.artist)
    title = clean_title_for_match(track.title)
    query = " ".join(p for p in (artist, title) if p).strip() or title or track.title
    q = urllib.parse.quote(query)
    if target == "deezer":
        return f"https://www.deezer.com/search/{q}"
    if target == "spotify":
        return f"https://open.spotify.com/search/{q}"
    # Default: YouTube Music (same URL shape that worked when clicks first landed)
    return f"https://music.youtube.com/search?q={q}"
