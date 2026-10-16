# Milestone 2 local ML data-validation pipeline

Milestone 2 adds local-only pipeline commands for the tiny self-authored sample catalog. The commands use the Milestone 0 source manifest schema and Milestone 1 canonical catalog models. They do not download external datasets, train models, generate recommendations, or change API behavior.

## Commands

Run commands from `backend/` after installing the backend requirements:

```bash
python -m app.ml_pipeline source-check \
  --manifest ../data/source-manifests/example.self-authored.json \
  --repo-root ..

python -m app.ml_pipeline normalize \
  --manifest ../data/source-manifests/example.self-authored.json \
  --fixture ../data/fixtures/ml/sample_games.self-authored.json \
  --output /tmp/gamesense-ml-m2/normalized.json

python -m app.ml_pipeline validate \
  --manifest ../data/source-manifests/example.self-authored.json \
  --normalized /tmp/gamesense-ml-m2/normalized.json \
  --output /tmp/gamesense-ml-m2/validation.json

python -m app.ml_pipeline manifest \
  --manifest ../data/source-manifests/example.self-authored.json \
  --normalized /tmp/gamesense-ml-m2/normalized.json \
  --validation-report /tmp/gamesense-ml-m2/validation.json \
  --output /tmp/gamesense-ml-m2/pipeline-manifest.json
```

## Scope and license gate

- `source-check` rejects unapproved manifests, checksum mismatches, license uncertainties, disallowed local/CI/repository use, and any non-self-authored source for this milestone.
- Other external sources still require their own approved manifest before any ingestion or training. The selected Kaggle source has its own narrowly approved manifest and private local run; see [current evidence](current-evidence.md).
- `normalize` accepts only `data/fixtures/ml/sample_games.self-authored.json`-style tiny self-authored fixture records and maps them into `CatalogGameSchema` records.
- `validate` reports catalog schema errors, source mismatches, duplicate identifiers, and missing genre/tag signals.
- `manifest` records deterministic row counts, validation findings, and checksums for local evidence.

## Kaggle Steam Store Games local bundle commands

After the user attaches the Kaggle `Steam Store Games (Clean dataset)` files in Kaggle, the notebook uses the same backend pipeline helpers for the accepted local-demo scope:

```bash
python -m app.ml_pipeline steam-store-source-check \
  --manifest ../data/source-manifests/kaggle.steam-store-games-clean.json

python -m app.ml_pipeline normalize-steam-store \
  --manifest ../data/source-manifests/kaggle.steam-store-games-clean.json \
  --dataset-dir /path/to/kaggle/steam-store-games \
  --output /tmp/gamesense-steam-normalized-catalog.json

python -m app.ml_pipeline validate \
  --manifest ../data/source-manifests/kaggle.steam-store-games-clean.json \
  --normalized /tmp/gamesense-steam-normalized-catalog.json
```

`steam-store-source-check` is intentionally separate from the self-authored fixture gate. It accepts only the named Kaggle source for the recorded local notebook/app-demo scope, requires attribution, rejects repository/CI use, and keeps Steam/SteamSpy upstream terms uncertainty visible as a warning rather than legal clearance.

## Expected evidence for the committed tiny sample

For `data/source-manifests/example.self-authored.json` and `data/fixtures/ml/sample_games.self-authored.json`:

- source review state: `approved`
- source type: `self-authored`
- fixture SHA-256: `7bdc6bfeee54e01ada92be2b676237c643f413f642bd4598914032573ac571bd`
- raw records: `2`
- normalized games: `2`
- valid games: `2`
- invalid games: `0`
- validation findings: `[]`
