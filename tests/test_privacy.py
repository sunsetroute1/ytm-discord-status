from __future__ import annotations

from ytm_discord.privacy import catalog_confirms_music


def test_catalog_confirms_known_song() -> None:
    assert catalog_confirms_music("Daft Punk", "Get Lucky") is True


def test_catalog_rejects_nonsense() -> None:
    assert (
        catalog_confirms_music(
            "zzzxqnotarealartist999",
            "zzzxqnotarealsong999personalvideo",
        )
        is False
    )
