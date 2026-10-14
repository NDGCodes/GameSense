# Kaggle Steam Store bundle handoff

This handoff uses Kaggle **Steam Store Games (Clean dataset)**: <https://www.kaggle.com/datasets/nikdavis/steam-store-games>. Kaggle lists the dataset as **Attribution 4.0 International (CC BY 4.0)**. The dataset page describes the data as Steam Store/SteamSpy-derived and gathered around May 2019, so GameSense records the upstream Steam/SteamSpy terms uncertainty and does not claim legal clearance, unrestricted redistribution, live Steam trends, personalization, or tuned accuracy.

The notebook fits sparse TF-IDF vocabulary/IDF/item vectors plus tag/genre metadata from the attached snapshot. This is fitted feature data, not neural fine-tuning or model training from user behavior.

## User steps

1. Open Kaggle and create a notebook with the GameSense repository files available, then attach `Steam Store Games (Clean dataset)` (`nikdavis/steam-store-games`) as an input dataset.
2. Run `notebooks/gamesense_baseline_kaggle.ipynb`. If Kaggle mounts the dataset somewhere other than `/kaggle/input/steam-store-games`, set `GAMESENSE_STEAM_STORE_DATASET_DIR` to the folder containing `steam.csv`.
3. Let the notebook run all cells. It will normalize `steam.csv`, `steam_description_data.csv`, and `steamspy_tag_data.csv`; validate IDs/tags/genres; fit the non-tuned TF-IDF/tag bundle; run a seed-exclusion sanity check; and write outputs under `/kaggle/working`.
4. Download and return both files printed by the last cell: `gamesense-steam-store-content-bundle.zip` and `gamesense-steam-store-kaggle-run-report.json`. Do not commit either file to git.
5. For local verification, place the zip under an ignored path such as `artifacts/models/local-kaggle-run/gamesense-steam-store-content-bundle.zip`.
6. Start the backend in content mode with `RECOMMENDER_MODE=content` and `CONTENT_BUNDLE_PATH=/absolute/path/to/gamesense-steam-store-content-bundle.zip`.
7. Open the UI, choose a title from the Favorite game datalist, and request recommendations. The `/api/games` catalog and `/api/recommendations` results should come from the same loaded bundle snapshot, exclude the selected seed for Similar mode, and display attribution/limitations.

Fixture mode remains available for CI and for demos without the returned Kaggle bundle.
