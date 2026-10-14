# GameSense baseline recommender model card

## Model/component details

- **Component:** `backend/app/recommender.py`
- **Version:** `gamesense-local-baseline-recommender-v1`
- **Offline evaluation CLI:** `python -m app.ml_evaluation`
- **Evaluation report version:** `gamesense-baseline-offline-eval-v1`
- **Status:** Local baseline only. It can be selected for the app recommendation endpoint with `RECOMMENDER_MODE=content`; fixture mode remains the default serving path.

## Intended use

This baseline is intended for local development and milestone validation of recommendation plumbing ideas. It ranks records from a caller-provided catalog with deterministic reciprocal-rank fusion over available local signals:

- optional caller-owned dense vectors;
- TF-IDF over title, description, genres, and tags;
- exact genre/tag matches and caller-provided trending exclusions.

The current evaluation exists to verify that this tiny local baseline remains deterministic, source-grounded, and honestly scoped. It is not intended to demonstrate production recommendation quality.

## Evaluation scope

The Milestone 4 offline evaluation uses only:

- the committed two-row, self-authored smoke fixture at `data/fixtures/ml/sample_games.self-authored.json`;
- clearly labeled synthetic dense-vector and mode-query-vector inputs embedded in `backend/app/ml_evaluation.py` for deterministic tests.

The CLI reports:

- catalog coverage over the active records in the tiny fixture;
- intra-list diversity as mean pairwise Jaccard distance over lowercase genre/tag sets, with `null` for lists shorter than two items;
- golden-query sanity checks for `similar`, `cozy`, `competitive`, and `non-trending` modes.

Outputs are printed to stdout by default. Persisting a report is opt-in with `--output <path>`; generated reports should be kept in temporary or task evidence locations, not committed as datasets, model weights, generated embeddings, or larger artifacts.

## What the evaluation can and cannot support

The evaluation can support narrow engineering claims such as:

- the report schema is deterministic and reproducible for the tiny fixture;
- the baseline excludes a seed item in the `similar` sanity check;
- the baseline honors the caller-provided trending exclusion in the `non-trending` sanity check;
- the synthetic vector inputs are labeled as synthetic test inputs rather than trained embeddings or model outputs.

The evaluation **does not** support claims about real-world recommendation quality, relevance, personalization, marketplace coverage, ranking fairness, robustness, retention, conversion, or user satisfaction.

## Limitations of the fixture evaluation

The returned Kaggle bundle is a separate fitted component; see the [handoff guide](kaggle-steam-store-bundle.md) for its workflow and limitations.

- No real Steam catalog, real game catalog, or external catalog data is used.
- No user-interaction logs, ratings, clicks, purchases, wishlists, or relevance labels are used.
- No model training, fine-tuning, generated embeddings, model weights, or learned parameters are produced.
- The fixture has only two fictional records, so metrics are smoke checks rather than statistically meaningful estimates.
- Synthetic vectors are hand-authored test inputs and are not evidence that any embedding model performs well.
- Current API/frontend serving options are described in the [README](../README.md#kaggle-content-bundle-handoff); fixture evaluation does not establish production readiness.

## Validation performed

Milestone 4 validation was run locally from `backend/` with `PYTHONPATH=.`:

```bash
pytest -q tests/test_ml_evaluation.py
pytest -q
python -m app.ml_evaluation --output /tmp/gamesense-ml-m4-evaluation/evaluation.json
```

Passing results are documented in the pull request summary for this milestone.
