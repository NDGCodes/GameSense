import pytest

from app.game_images import game_image_fields, steam_image_url
from app.schemas import CatalogGameSchema


def game(**overrides):
    return CatalogGameSchema.model_validate({
        "sourceId": "kaggle.steam-store-games-clean", "sourceGameId": "900000001",
        "slug": "steam-900000001", "title": "Self-authored sample", **overrides,
    })


def test_legacy_bundle_identity_provides_same_id_image_without_title_matching():
    fields = game_image_fields(game())
    assert fields == {
        "steamAppId": "900000001",
        "imageUrl": "https://cdn.akamai.steamstatic.com/steam/apps/900000001/header.jpg",
        "imageFallbackUrl": "https://cdn.akamai.steamstatic.com/steam/apps/900000001/capsule_231x87.jpg",
    }
    assert game_image_fields(game(title="A completely different title")) == fields


def test_dataset_image_metadata_takes_precedence_for_exact_game():
    url = "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/900000001/abc123/header.jpg?t=1"
    assert game_image_fields(game(metadata={"imageUrl": url}))["imageUrl"] == url


def test_duplicate_titles_keep_distinct_identity_bound_covers():
    first = game(sourceGameId="900000001", title="Same title")
    second = game(sourceGameId="900000002", title="Same title")
    for record in (second, first, second):
        fields = game_image_fields(record)
        assert fields["steamAppId"] == record.sourceGameId
        assert fields["imageUrl"] == (
            f"https://cdn.akamai.steamstatic.com/steam/apps/{record.sourceGameId}/header.jpg"
        )
        assert fields["imageFallbackUrl"].endswith(f"/{record.sourceGameId}/capsule_231x87.jpg")


@pytest.mark.parametrize("overrides", [
    {"sourceId": "gamesense-self-authored-smoke-fixture"},
    {"sourceGameId": "not-a-steam-id"},
    {"sourceGameId": "0"},
    {"sourceGameId": "../10"},
    {"metadata": {"steamAppId": "900000002"}},
])
def test_unknown_or_inconsistent_identity_has_no_artwork(overrides):
    assert game_image_fields(game(**overrides)) == {
        "steamAppId": None, "imageUrl": None, "imageFallbackUrl": None,
    }


@pytest.mark.parametrize("url", [
    "https://cdn.akamai.steamstatic.com/steam/apps/900000002/header.jpg",
    "https://cdn.akamai.steamstatic.com.evil.example/steam/apps/900000001/header.jpg",
    "https://example.com/steam/apps/900000001/header.jpg",
    "http://cdn.akamai.steamstatic.com/steam/apps/900000001/header.jpg",
    "https://user:pass@cdn.akamai.steamstatic.com/steam/apps/900000001/header.jpg",
    "https://cdn.akamai.steamstatic.com/steam/apps/900000001/../900000002/header.jpg",
    "https://cdn.akamai.steamstatic.com:bad/steam/apps/900000001/header.jpg",
    "data:image/svg+xml,example",
    None,
])
def test_untrusted_or_other_game_metadata_is_not_served(url):
    assert steam_image_url(url, "900000001") is None
    assert game_image_fields(game(metadata={"imageUrl": url}))["imageUrl"].endswith("/900000001/header.jpg")
