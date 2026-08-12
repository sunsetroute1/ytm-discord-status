from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WhitelistEntry:
    """Substring matched against Windows source_app_user_model_id (case-insensitive)."""

    id: str
    label: str
    tokens: tuple[str, ...]
    # Browser processes are unsafe (any tab). Only allowed with catalog confirmation.
    is_browser: bool = False


# Whitelist-only. Anything not listed is ignored (blacklisted by omission).
DEFAULT_WHITELIST: tuple[WhitelistEntry, ...] = (
    # Streaming / store apps
    WhitelistEntry("spotify", "Spotify", ("spotify",)),
    WhitelistEntry("apple_music", "Apple Music", ("applemusic", "apple.music", "appleinc.applemusic")),
    WhitelistEntry("amazon_music", "Amazon Music", ("amazonmusic", "amazon.music", "amazon.com.amazonmusic")),
    WhitelistEntry("deezer", "Deezer", ("deezer",)),
    WhitelistEntry("tidal", "TIDAL", ("tidal",)),
    WhitelistEntry("soundcloud", "SoundCloud", ("soundcloud",)),
    WhitelistEntry("pandora", "Pandora", ("pandora",)),
    WhitelistEntry("iheart", "iHeartRadio", ("iheartradio", "iheart")),
    WhitelistEntry("qobuz", "Qobuz", ("qobuz",)),
    WhitelistEntry("napster", "Napster", ("napster",)),
    WhitelistEntry("youtube_music_app", "YouTube Music", ("youtubemusic", "youtube.music")),
    # Local / desktop players (music-focused)
    WhitelistEntry("winamp", "Winamp", ("winamp",)),
    WhitelistEntry("foobar2000", "foobar2000", ("foobar2000", "foobar")),
    WhitelistEntry("musicbee", "MusicBee", ("musicbee",)),
    WhitelistEntry("aimp", "AIMP", ("aimp",)),
    WhitelistEntry("itunes", "iTunes", ("itunes",)),
    WhitelistEntry("mediamonkey", "MediaMonkey", ("mediamonkey",)),
    WhitelistEntry("quodlibet", "Quod Libet", ("quodlibet",)),
    WhitelistEntry("clementine", "Clementine", ("clementine",)),
    WhitelistEntry("strawberry", "Strawberry", ("strawberry",)),
    WhitelistEntry("rhythmbox", "Rhythmbox", ("rhythmbox",)),
    WhitelistEntry("musicplayer2", "Music Player 2", ("musicplayer2",)),
    WhitelistEntry("dopamine", "Dopamine", ("dopamine",)),
    WhitelistEntry("neutron", "Neutron Music Player", ("neutronmusic", "neutron")),
)

# Optional: browser SMTC for music.youtube.com / web players.
# Requires catalog confirmation so random/adult tabs never become presence.
BROWSER_WHITELIST: tuple[WhitelistEntry, ...] = (
    WhitelistEntry("chrome", "Chrome", ("chrome",), is_browser=True),
    WhitelistEntry("msedge", "Edge", ("msedge", "edge"), is_browser=True),
    WhitelistEntry("brave", "Brave", ("brave",), is_browser=True),
    WhitelistEntry("firefox", "Firefox", ("firefox",), is_browser=True),
    WhitelistEntry("opera", "Opera", ("opera",), is_browser=True),
    WhitelistEntry("vivaldi", "Vivaldi", ("vivaldi",), is_browser=True),
    WhitelistEntry("chromium", "Chromium", ("chromium",), is_browser=True),
)

ALL_ENTRIES = {e.id: e for e in (*DEFAULT_WHITELIST, *BROWSER_WHITELIST)}

# Safe defaults: dedicated music apps only (no browsers).
DEFAULT_ENABLED_IDS = tuple(e.id for e in DEFAULT_WHITELIST)


def resolve_whitelist(enabled_ids: tuple[str, ...]) -> list[WhitelistEntry]:
    out: list[WhitelistEntry] = []
    seen: set[str] = set()
    for eid in enabled_ids:
        entry = ALL_ENTRIES.get(eid)
        if entry and entry.id not in seen:
            out.append(entry)
            seen.add(entry.id)
    return out


def match_whitelist(app_id: str, entries: list[WhitelistEntry]) -> WhitelistEntry | None:
    needle = (app_id or "").lower()
    if not needle:
        return None
    for entry in entries:
        if any(token in needle for token in entry.tokens):
            return entry
    return None
