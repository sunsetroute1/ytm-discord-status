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
    # Also used for apps that play movies/TV as well as music (e.g. Jellyfin).
    require_catalog_match: bool = False


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
    # Self-hosted media (music, films, TV — trusted app, not a browser tab).
    WhitelistEntry(
        "jellyfin",
        "Jellyfin",
        (
            "jellyfinmediaplayer",
            "jellyfin-media-player",
            "jellyfin media player",
            "jellyfinmp",
            "jellyfin",
        ),
    ),
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

# Blacklist mode: mirror all SMTC sessions except these (personal / generic players).
DEFAULT_BLACKLIST: tuple[WhitelistEntry, ...] = (
    WhitelistEntry("vlc", "VLC", ("vlc",)),
    WhitelistEntry(
        "photos",
        "Photos",
        ("microsoft.photos", "microsoft.windows.photos", "photos.exe"),
    ),
    WhitelistEntry(
        "movies_tv",
        "Movies & TV",
        ("zunevideo", "microsoft.zunevideo", "moviesandtv", "movies & tv"),
    ),
    WhitelistEntry("mpv", "mpv", ("mpv",)),
    WhitelistEntry("mpc", "MPC-HC / MPC-BE", ("mpc-hc", "mpc-be", "mpc-qt")),
    WhitelistEntry("potplayer", "PotPlayer", ("potplayer",)),
    WhitelistEntry("gom", "GOM Player", ("gomplayer", "gom.exe")),
    WhitelistEntry("kmplayer", "KMPlayer", ("kmplayer",)),
    WhitelistEntry("zoom", "Zoom", ("zoom.exe", "zoom.us", "zoomworkplace")),
    WhitelistEntry("teams", "Microsoft Teams", ("teams.exe", "ms-teams", "microsoft teams")),
    WhitelistEntry("skype", "Skype", ("skype",)),
    WhitelistEntry("discord", "Discord", ("discord.exe", "discordptb", "discordcanary")),
)

ALL_ENTRIES = {e.id: e for e in (*DEFAULT_WHITELIST, *BROWSER_WHITELIST)}
ALL_BLACKLIST_ENTRIES = {e.id: e for e in DEFAULT_BLACKLIST}

# Safe defaults: dedicated music apps only (no browsers).
DEFAULT_ENABLED_IDS = tuple(e.id for e in DEFAULT_WHITELIST)
DEFAULT_BLACKLIST_IDS = tuple(e.id for e in DEFAULT_BLACKLIST)

MEDIA_MODES = ("whitelist", "blacklist")


def resolve_whitelist(enabled_ids: tuple[str, ...]) -> list[WhitelistEntry]:
    out: list[WhitelistEntry] = []
    seen: set[str] = set()
    for eid in enabled_ids:
        entry = ALL_ENTRIES.get(eid)
        if entry and entry.id not in seen:
            out.append(entry)
            seen.add(entry.id)
    return out


def resolve_blacklist(enabled_ids: tuple[str, ...]) -> list[WhitelistEntry]:
    out: list[WhitelistEntry] = []
    seen: set[str] = set()
    for eid in enabled_ids:
        entry = ALL_BLACKLIST_ENTRIES.get(eid)
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


def match_blacklist(app_id: str, entries: list[WhitelistEntry]) -> WhitelistEntry | None:
    """Same token matching as whitelist; used to reject sessions in blacklist mode."""
    return match_whitelist(app_id, entries)


def known_catalog_entries() -> list[WhitelistEntry]:
    """All known apps (music + browsers) for labeling in blacklist mode."""
    return list(ALL_ENTRIES.values())


def synthetic_media_entry(app_id: str) -> WhitelistEntry:
    """Fallback entry for unknown apps in blacklist (all-media) mode."""
    raw = (app_id or "").strip() or "Media"
    short = raw.split("!")[-1].split("\\")[-1]
    if short.lower().endswith(".exe"):
        short = short[:-4]
    label = short[:64] if short else "Media"
    return WhitelistEntry("other", label, (), is_browser=False)
