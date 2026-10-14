# Kaggle Steam Store bundle handoff

The [source manifest](../data/source-manifests/kaggle.steam-store-games-clean.json) owns the selected Kaggle dataset, attribution requirement, historical snapshot provenance, and narrowly accepted local notebook/app-demo scope, including unresolved upstream terms uncertainty. Follow that scope when running the notebook or using its outputs.

The notebook fits sparse TF-IDF vocabulary/IDF/item vectors plus tag/genre metadata from the attached snapshot. This is fitted feature data, not neural fine-tuning or model training from user behavior.

## User steps

1. Import `notebooks/gamesense_baseline_kaggle.ipynb` into Kaggle, make the repository files available to the notebook, and attach the dataset identified in the source manifest. Before running the setup cell, set `GAMESENSE_REPO_ROOT` to the repository directory containing `backend/` and `data/` (the default is the notebook’s current directory). The kernel needs the dependencies in `backend/requirements.txt`, including Pydantic 2; install them into the Kaggle runtime if unavailable.
2. Run `notebooks/gamesense_baseline_kaggle.ipynb`. If Kaggle mounts the dataset somewhere other than `/kaggle/input/steam-store-games`, set `GAMESENSE_STEAM_STORE_DATASET_DIR` to the folder containing `steam.csv`.
3. Let the notebook run all cells. It will normalize `steam.csv`, `steam_description_data.csv`, and `steamspy_tag_data.csv`; validate IDs/tags/genres; fit the non-tuned TF-IDF/tag bundle; run a seed-exclusion sanity check; and write outputs under `/kaggle/working`.
4. Download and return both files printed by the last cell: `gamesense-steam-store-content-bundle.zip` and `gamesense-steam-store-kaggle-run-report.json`. Do not commit either file to git.
5. For local verification, place the zip under an ignored path such as `artifacts/models/local-kaggle-run/gamesense-steam-store-content-bundle.zip`.
6. Complete the [README local backend setup](../README.md#local-development), including dependencies and database migrations. From `backend/`, start it with `RECOMMENDER_MODE=content CONTENT_BUNDLE_PATH=/absolute/path/to/gamesense-steam-store-content-bundle.zip uvicorn app.main:app --reload`. Start the UI using the README instructions and point it at this backend. The bundle is cached by path; restart the backend after replacing a zip at the same path. Invalid configured bundles fail rather than silently using fixtures.
7. Open the UI and choose a title-labeled option from the editable Favorite game datalist; the option submits its stable slug to distinguish duplicate titles. The UI initially loads up to 500 alphabetically sorted options. For games outside that list, enter a catalog title, slug, or Steam app ID manually; a slug or app ID avoids title ambiguity. The backend accepts favorite-game text up to 240 characters. `/api/games` supports a `q` filter and a `limit` (default 500, clamped to 1–1000); in content mode the filter matches titles, slugs, app IDs, genres, and tags. Catalog and recommendations use the same loaded snapshot and the UI displays its disclosure.

Similar mode excludes the matched seed. If no similar candidates exist, it uses the Cozy scorer while still excluding that seed; an unknown seed also uses Cozy signals. The response explains the fallback and records `fallbackReason`. Cozy and Competitive require matching text or taxonomy signals, with historical popularity contributing only to ranking supported candidates. Trending uses the non-trending baseline rather than live trends. A mode can return no recommendations when no candidates have supporting signals.

Fixture mode remains the default for CI and demos. Content mode without `CONTENT_BUNDLE_PATH` uses the committed self-authored smoke catalog.
