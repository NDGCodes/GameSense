"""Local-only verification of the accepted catalog; no network or data downloads."""

import os
from pathlib import Path

import pytest

from app.game_images import steam_image_url
from app.ml_bundle import load_content_bundle
from app.recommender_service import clear_content_bundle_cache, list_games_for_api


def test_complete_local_catalog_preserves_game_to_artwork_mapping(monkeypatch):
    path = os.getenv("GAMESENSE_LOCAL_ARTWORK_BUNDLE")
    if os.getenv("CI") or not path:
        pytest.skip("Real catalog is local-only; supply GAMESENSE_LOCAL_ARTWORK_BUNDLE outside CI")

    bundle = load_content_bundle(Path(path))
    assert bundle.source_id == "kaggle.steam-store-games-clean"
    assert len(bundle.catalog) == 27075
    expected = {game.slug: game for game in bundle.catalog}
    assert len(expected) == 27075
    assert len({game.sourceGameId for game in bundle.catalog}) == 27075

    monkeypatch.setenv("RECOMMENDER_MODE", "content")
    monkeypatch.setenv("CONTENT_BUNDLE_PATH", path)
    clear_content_bundle_cache()
    try:
        catalog = list_games_for_api(None, limit=len(bundle.catalog))
        assert len(catalog) == len(expected)
        for item in catalog:
            game = expected[item.slug]
            assert item.title == game.title
            assert item.steamAppId == game.sourceGameId
            assert steam_image_url(item.imageUrl, game.sourceGameId) == item.imageUrl
            assert item.imageUrl is not None
            assert item.imageFallbackUrl == (
                f"https://cdn.akamai.steamstatic.com/steam/apps/{game.sourceGameId}/capsule_231x87.jpg"
            )
    finally:
        clear_content_bundle_cache()
