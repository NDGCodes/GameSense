"""Optional remote artwork for the accepted Steam snapshot demo; no artwork is stored."""

import re
from urllib.parse import urlsplit

from app.schemas import CatalogGameSchema

STEAM_SOURCE_ID = "kaggle.steam-store-games-clean"
STEAM_IMAGE_HOSTS = {
    "cdn.akamai.steamstatic.com",
    "cdn.cloudflare.steamstatic.com",
    "shared.akamai.steamstatic.com",
    "shared.cloudflare.steamstatic.com",
    "shared.fastly.steamstatic.com",
    "steamcdn-a.akamaihd.net",
}


def steam_app_id(value: object) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,9}", value) else None


def steam_image_url(value: object, app_id: str) -> str | None:
    """Accept dataset image metadata only from Steam CDN paths for this exact ID."""
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value.strip())
        if url.scheme != "https" or url.hostname not in STEAM_IMAGE_HOSTS or url.port not in (None, 443):
            return None
        if url.username or url.password or url.fragment:
            return None
        if not re.fullmatch(
            rf"/(?:store_item_assets/)?steam/apps/{re.escape(app_id)}/(?:[a-fA-F0-9]+/)?[a-zA-Z0-9_-]+\.(?:jpg|jpeg|png|webp)",
            url.path,
        ):
            return None
    except ValueError:
        return None
    return value.strip()


def game_image_fields(game: CatalogGameSchema) -> dict[str, str | None]:
    empty = {"steamAppId": None, "imageUrl": None, "imageFallbackUrl": None}
    if game.sourceId != STEAM_SOURCE_ID:
        return empty
    app_id = steam_app_id(game.sourceGameId)
    if app_id is None or str(game.metadata.get("steamAppId", app_id)) != app_id:
        return empty
    image_url = steam_image_url(game.metadata.get("imageUrl"), app_id)
    # Older v1 bundles carry identity but no artwork metadata. Never infer an ID from a title.
    return {
        "steamAppId": app_id,
        "imageUrl": image_url or f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
        # Some historical apps retain a small capsule even when their header is gone.
        "imageFallbackUrl": f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/capsule_231x87.jpg",
    }
