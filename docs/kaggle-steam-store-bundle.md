# Kaggle Steam Store bundle handoff

The [source manifest](../data/source-manifests/kaggle.steam-store-games-clean.json) owns the selected Kaggle dataset, attribution requirement, historical snapshot provenance, and narrowly accepted local notebook/app-demo scope, including unresolved upstream terms uncertainty. Follow that scope when running the notebook or using its outputs.

The notebook fits sparse TF-IDF vocabulary/IDF/item vectors plus tag/genre metadata from the attached snapshot. This is fitted feature data, not neural fine-tuning or model training from user behavior.

The [current evidence index](current-evidence.md) records the completed private Kaggle run, returned bundle identity, and local verification. The zip and run report remain private, outside git. The steps below are for repeating that workflow with authorized access.

## User steps

1. Import `notebooks/gamesense_baseline_kaggle.ipynb` into Kaggle, make the repository files available to the notebook, and attach the dataset identified in the source manifest. Before running the setup cell, set `GAMESENSE_REPO_ROOT` to the repository directory containing `backend/` and `data/` (the default is the notebook’s current directory). The kernel needs the dependencies in `backend/requirements.txt`, including Pydantic 2; install them into the Kaggle runtime if unavailable.
2. Run `notebooks/gamesense_baseline_kaggle.ipynb`. If Kaggle mounts the dataset somewhere other than `/kaggle/input/steam-store-games`, set `GAMESENSE_STEAM_STORE_DATASET_DIR` to the folder containing `steam.csv`.
3. Let the notebook run all cells. It will normalize `steam.csv`, `steam_description_data.csv`, and `steamspy_tag_data.csv`, plus optional `steam_media_data.csv` header-image metadata; validate IDs/tags/genres; fit the non-tuned TF-IDF/tag bundle; run a seed-exclusion sanity check; and write outputs under `/kaggle/working`.
4. Download and return both files printed by the last cell: `gamesense-steam-store-content-bundle.zip` and `gamesense-steam-store-kaggle-run-report.json`. Do not commit either file to git.
5. For local verification, place the zip under an ignored path such as `artifacts/models/local-kaggle-run/gamesense-steam-store-content-bundle.zip`.
6. Complete the [README local backend setup](../README.md#local-development), including dependencies and database migrations. From `backend/`, start it with `RECOMMENDER_MODE=content CONTENT_BUNDLE_PATH=/absolute/path/to/gamesense-steam-store-content-bundle.zip uvicorn app.main:app --reload`. Start the UI using the README instructions and point it at this backend. The bundle is cached by path; restart the backend after replacing a zip at the same path. Invalid configured bundles fail rather than silently using fixtures.
7. Open the current UI's catalog screen, search or browse, then select a game card to open its detail screen and similar recommendations. The UI requests catalog pages of 30 using `/api/games?limit=30&offset=…`, debounces search, and passes the selected stable slug to `POST /api/recommendations` in Similar mode. Initial genre choices come from loaded games, and the genre filter applies to those loaded games. `/api/games` also supports a `q` filter and a `limit` (default 500, clamped to 1–1000); in content mode the filter matches titles, slugs, app IDs, genres, and tags. The backend API still accepts favorite-game text up to 240 characters and its other recommendation modes, although the present two-screen UI exposes only Similar. Catalog and recommendations use the same loaded snapshot.

Similar mode excludes the matched seed. If no similar candidates exist, it uses the Cozy scorer while still excluding that seed; an unknown seed also uses Cozy signals. The response explains the fallback and records `fallbackReason`. Cozy and Competitive require matching text or taxonomy signals, with historical popularity contributing only to ranking supported candidates. Trending uses the non-trending baseline rather than live trends. A mode can return no recommendations when no candidates have supporting signals.

Fixture mode remains the default for CI and the committed Compose stack. Content mode without `CONTENT_BUNDLE_PATH` uses the committed self-authored smoke catalog; the verified real-catalog local demo supplied the private zip explicitly.

## Game artwork in the local demo

Catalog and recommendation cards use the same responsive artwork component, with title-specific alternative text, lazy loading, and a visible title placeholder for missing or failed images. Catalog cards first try a same-ID Steam portrait (`library_600x900.jpg`), then the header and capsule candidates; the detail hero and recommendation cards use header then capsule. Publisher artwork bytes are not copied into the repository.

The normalizer joins optional `steam_media_data.csv` rows by `steam_appid`/`appid` and preserves a matching HTTPS Steam CDN `header_image` URL as `metadata.imageUrl`. The bundle exporter already preserves catalog metadata and checksums, so no bundle-format or model-feature change is needed. The API adds nullable `steamAppId`, `imageUrl`, and `imageFallbackUrl` fields to both catalog and recommendation records. Valid image paths must carry the exact `sourceGameId`; conflicting `metadata.steamAppId` disables all artwork candidates. Identity is never inferred from a title, array position, or another game's cover.

When image metadata is missing or rejected, including in existing v1 bundles, the API uses `https://cdn.akamai.steamstatic.com/steam/apps/{sourceGameId}/header.jpg` only for the accepted `kaggle.steam-store-games-clean` source and a valid numeric Steam ID with no conflicting `metadata.steamAppId`. It also supplies the same game's `capsule_231x87.jpg` as `imageFallbackUrl`. The browser tries the capsule only after the primary image fails, then shows the title placeholder if both fail. Duplicate URLs are attempted once, and rerenders do not restart exhausted candidates. A changed game or candidate URL resets the attempt state. The smaller capsule can appear softer or letterboxed within the reserved header frame; it is actual artwork for the same Steam ID.

These are best-effort public CDN mappings for the accepted local demo, not a guaranteed Steam API contract. Removed games, changed asset paths, network failures, and historical games without either image can all show the placeholder. Fictional demo and self-authored smoke fixtures do not borrow real-game artwork.

The browser requests remote artwork directly with no referrer; the backend does not fetch, proxy, cache, or mirror image bytes. Publisher artwork rights are separate from the dataset's listed CC BY 4.0 license. The dataset manifest does not grant artwork redistribution or production clearance. [Steamworks graphical asset documentation](https://partner.steamgames.com/doc/store/assets) describes the publisher-supplied capsule assets; this implementation does not assert those assets are openly licensed. No credentials, protected image service, or new catalog scrape were required for the artwork change. A subsequent approved private Kaggle execution supplied the real bundle used in the current local app audit.

CI validation uses self-authored samples for the normalizer, bundle round trip, API identity mapping, legacy compatibility, duplicate-title separation, and rejection of mismatched image URLs. Real-catalog checks stay local because the accepted dataset scope excludes CI and committing the bundle.

### Verified catalog artwork

The local artwork audit completed on 2026-10-15 UTC against the returned bundle identified in the [current evidence index](current-evidence.md). Its 27,075 games have 27,075 unique Steam IDs and slugs, including 41 duplicate-title groups. None of these legacy bundle records contains `metadata.imageUrl`; the identity-based mapping supplies artwork without rebuilding the bundle.

An HTTP HEAD census of every exact-ID header URL found 27,074 HTTP 200 `image/jpeg` responses and one HTTP 404. The affected game's same-ID `capsule_231x87.jpg` returned HTTP 200 and decoded successfully through the actual frontend component. Thus all 27,075 games had at least one advertised image asset at audit time. Representative real covers were decoded in the browser; the census did not download or decode all image bodies. Eleven transient connection failures recovered on retry. Availability can change, so bounded fallback and accessible placeholders remain necessary.

Local verification also exercised the real catalog service for every game, sampled public API queries across duplicate titles, non-ASCII titles and catalog boundaries, and checked all recommendation modes. Browser checks covered desktop/mobile layout and the actual missing-header case. A fresh app load requested 500 catalog options and zero Steam images before recommendations, keeping the full-catalog census out of the rendering path. The bundle, per-ID probe results and screenshots remain outside git; no additional artwork provider or redistribution permission was introduced.

That 2026-10-15 browser-load observation predates the current paged catalog UI. See the [current evidence index](current-evidence.md#selected-application-screenshots) for later captures, their selection, and image-decoding limitations.

### Repeat the local artwork checks

From `backend/`, run the opt-in test against the returned bundle:

```sh
GAMESENSE_LOCAL_ARTWORK_BUNDLE=/absolute/path/to/gamesense-steam-store-content-bundle.zip \
  python -m pytest -q tests/test_real_catalog_artwork.py
```

This loads and validates the bundle checksums and row mapping, then checks all 27,075 records through the catalog service. It verifies unique IDs and slugs, title preservation, and primary and fallback image URLs bound to each exact Steam ID, including duplicate titles. It makes no remote image requests. Without that environment variable, or in CI, the test skips rather than loading third-party data.

From `frontend/`, run `npm run dev` and open `/tests/game-artwork.html` on the printed local URL. The browser checks execute the actual `GameArtwork` component using self-authored SVG data URLs. They verify decoding, alternative text, lazy/asynchronous loading, no-referrer requests, reserved dimensions, error and missing-image placeholders, failure isolation between duplicate titles, primary-to-capsule fallback, duplicate URL suppression, bounded attempts, and reset behavior when identity or URL changes. All checks must display `PASS`; `document.documentElement.dataset.testStatus` becomes `passed`. The test page is a development entry point and is not included in the production app build.
