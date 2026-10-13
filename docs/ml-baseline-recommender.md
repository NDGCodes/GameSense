# Milestone 3 local baseline recommender

This milestone added an isolated local recommender module at `backend/app/recommender.py`. Milestone 5 can now expose it through the app when `RECOMMENDER_MODE=content`; the fixture recommender remains the default for backward compatibility.

## Scope

Implemented:

- Local candidate ranking for `similar`, `cozy`, `competitive`, and `non-trending` modes.
- Candidate union from:
  - dense description-vector cosine similarity when precomputed vectors are supplied by the caller;
  - local TF-IDF similarity over title, description, genres, and tags;
  - exact tag/genre signals, plus caller-provided trending exclusions for `non-trending`.
- Reciprocal Rank Fusion with deterministic tie-breaking by title and slug.
- Seed-item exclusion for `similar` recommendations.
- Source-grounded explanation data that identifies source ids, source game ids, source fields, component ranks, component scores, matched tags/genres/tokens, and fusion settings.

Not implemented in this milestone:

- Downloading model weights, training an encoder, or generating real catalog embeddings.
- External catalog acquisition or use of data beyond the existing self-authored sample fixture.
- Deployment or later ML milestones.

Dense vectors are treated as caller-owned precomputed inputs. Unit tests use clearly named synthetic vectors only to make deterministic assertions; they are not represented as model output.

## Validation performed

The focused recommender tests passed locally with:

```bash
cd backend
PYTHONPATH=. pytest -q tests/test_recommender.py
```

Result: `5 passed in 0.09s`.

Milestone 4 adds an offline evaluation CLI and model card in `backend/app/ml_evaluation.py` and `docs/ml-baseline-model-card.md`. The evaluation is a deterministic smoke check over the tiny self-authored fixture and clearly labeled synthetic vector inputs; it is not evidence of real-catalog or user-interaction recommendation quality.

Milestone 6 adds local container and observability support for the integrated content path. `docker compose --profile content-smoke run --rm content-smoke` exercises `RECOMMENDER_MODE=content` against `data/fixtures/ml/sample_games.self-authored.json` without external data. The API emits bounded Prometheus metrics for recommendation requests, content/fixture fallbacks, model algorithm/version/snapshot metadata, and catalog item counts. Metric labels must stay low-cardinality and must not include favorite-game text, user identifiers, secrets, request bodies, or any external dataset identifiers beyond approved source snapshot names.

The full backend test suite passed locally in a Python 3.10 virtual environment with:

```bash
cd backend
PYTHONPATH=. pytest -q
```

Result: `19 passed, 1 warning in 3.17s`.

The passing recommender tests cover stable ranking, seed exclusion, exact tag/genre matches, TF-IDF ranking, dense-vector inputs, missing-vector fallback, non-trending filtering, and source-grounded explanations.
