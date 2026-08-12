from __future__ import annotations

from ytm_discord.privacy import (
    _CATALOG_CACHE,
    _catalog_queries,
    _embedded_artist_title,
    _identity_candidates,
    catalog_confirms_music,
    clean_artist_for_match,
    clean_title_for_match,
)


def test_clean_title_strips_common_ytm_clutter() -> None:
    cases = {
        "Get Lucky (Official Video)": "Get Lucky",
        "Get Lucky - Official Video": "Get Lucky",
        "Get Lucky | Official Audio": "Get Lucky",
        "Get Lucky [HD]": "Get Lucky",
        "Get Lucky [4K]": "Get Lucky",
        "Get Lucky (Explicit)": "Get Lucky",
        "Get Lucky (Clean)": "Get Lucky",
        "Get Lucky (Remastered)": "Get Lucky",
        "Get Lucky (2013 Remaster)": "Get Lucky",
        "Public Enemy EVERYTHING [OFFICIAL VIDEO]": "Public Enemy EVERYTHING",
        "EARFQUAKE【Official Video】": "EARFQUAKE",
        "Party (feat. RMR) [Official Video]": "Party",
        "Blinding Lights (Official Music Video)": "Blinding Lights",
        "Song [Audio]": "Song",
    }
    for raw, expected in cases.items():
        assert clean_title_for_match(raw) == expected, raw


def test_clean_artist_strips_topic_and_vevo() -> None:
    assert clean_artist_for_match("Daft Punk - Topic") == "Daft Punk"
    assert clean_artist_for_match("The WeekndVEVO") == "The Weeknd"
    assert clean_artist_for_match("The Weeknd - VEVO") == "The Weeknd"


def test_catalog_confirms_known_song() -> None:
    _CATALOG_CACHE.clear()
    assert catalog_confirms_music("Daft Punk", "Get Lucky") is True


def test_catalog_confirms_short_title_with_feat() -> None:
    _CATALOG_CACHE.clear()
    # SMTC often omits "(feat. …)" that catalogs include.
    assert catalog_confirms_music("Kid Ink", "Party") is True


def test_catalog_confirms_official_video_suffix() -> None:
    _CATALOG_CACHE.clear()
    # YouTube Music often appends [OFFICIAL VIDEO] to real tracks.
    assert catalog_confirms_music("Public Enemy", "Public Enemy EVERYTHING [OFFICIAL VIDEO]") is True


def test_catalog_confirms_dash_and_pipe_suffixes() -> None:
    _CATALOG_CACHE.clear()
    assert catalog_confirms_music("Daft Punk", "Get Lucky - Official Video") is True
    _CATALOG_CACHE.clear()
    assert catalog_confirms_music("Daft Punk", "Get Lucky | Official Audio") is True


def test_catalog_confirms_remaster_and_explicit() -> None:
    _CATALOG_CACHE.clear()
    assert catalog_confirms_music("Daft Punk", "Get Lucky (Remastered)") is True
    _CATALOG_CACHE.clear()
    assert catalog_confirms_music("Daft Punk", "Get Lucky (Explicit)") is True


def test_catalog_confirms_topic_artist() -> None:
    _CATALOG_CACHE.clear()
    assert catalog_confirms_music("Daft Punk - Topic", "Get Lucky") is True


def test_catalog_confirms_label_as_artist() -> None:
    # YouTube Music often puts the record label in the artist field.
    _CATALOG_CACHE.clear()
    assert catalog_confirms_music("ANTI- Records", "The Gods of Science") is True


def test_embedded_artist_title_parsing() -> None:
    assert _embedded_artist_title("The Last Emperor - Clear Day") == (
        "The Last Emperor",
        "Clear Day",
    )
    assert _embedded_artist_title("Artist – Song") == ("Artist", "Song")
    assert _embedded_artist_title("Artist | Song") == ("Artist", "Song")
    # Not an artist-song embedding
    assert _embedded_artist_title("Clear Day") is None
    assert _embedded_artist_title("Live - From Madison Square Garden") is None
    assert _embedded_artist_title("123 - 456") is None
    # Video suffixes must not become fake song identities
    assert _embedded_artist_title("Get Lucky - Official Video") is None
    assert _embedded_artist_title("Get Lucky | Official Audio") is None


def test_identity_candidates_channel_vs_real_artist() -> None:
    pairs = _identity_candidates("ZteamZ", "The Last Emperor - Clear Day")
    assert pairs[0] == ("ZteamZ", "The Last Emperor - Clear Day")
    assert ("The Last Emperor", "Clear Day") in pairs
    # When SMTC artist already matches the embedded left side, don't invent extras.
    assert _identity_candidates("The Last Emperor", "The Last Emperor - Clear Day") == [
        ("The Last Emperor", "The Last Emperor - Clear Day")
    ]
    # Real artist + video suffix title: no bogus Get Lucky / Official Video pair
    assert _identity_candidates("Daft Punk", "Get Lucky - Official Video") == [
        ("Daft Punk", "Get Lucky - Official Video")
    ]


def test_catalog_queries_are_bounded_and_deduped() -> None:
    queries = _catalog_queries("ZteamZ", "The Last Emperor - Clear Day")
    assert queries[0] == "ZteamZ The Last Emperor - Clear Day"
    assert "The Last Emperor Clear Day" in queries
    assert len(queries) == len(set(q.lower() for q in queries))
    assert len(queries) <= 8


def test_catalog_confirms_channel_artist_with_embedded_track() -> None:
    # Brave/YTM SMTC: playlist/channel in artist, "Artist - Song" in title.
    _CATALOG_CACHE.clear()
    assert catalog_confirms_music("ZteamZ", "The Last Emperor - Clear Day") is True


def test_catalog_rejects_nonsense() -> None:
    _CATALOG_CACHE.clear()
    assert (
        catalog_confirms_music(
            "zzzxqnotarealartist999",
            "zzzxqnotarealsong999personalvideo",
        )
        is False
    )
