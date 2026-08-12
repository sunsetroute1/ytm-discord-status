from __future__ import annotations

import urllib.parse

from .media import NowPlaying


def listen_url(track: NowPlaying, target: str = "youtube_music") -> str:
    """Build a public HTTPS search/listen URL for the current track."""
    query = " ".join(p for p in (track.artist, track.title) if p).strip() or track.title
    q = urllib.parse.quote(query)
    if target == "deezer":
        return f"https://www.deezer.com/search/{q}"
    if target == "spotify":
        return f"https://open.spotify.com/search/{q}"
    # Default: YouTube Music
    return f"https://music.youtube.com/search?q={q}"
