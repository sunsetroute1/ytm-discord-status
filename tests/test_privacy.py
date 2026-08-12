from __future__ import annotations

from ytm_discord.privacy import (
    _CATALOG_CACHE,
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


def test_catalog_rejects_nonsense() -> None:
    _CATALOG_CACHE.clear()
    assert (
        catalog_confirms_music(
            "zzzxqnotarealartist999",
            "zzzxqnotarealsong999personalvideo",
        )
        is False
    )
