# M9 submission package: current local evidence

This is a reviewer-facing walkthrough and evidence index for the current GameSense repository. The dated [M8 freeze](../docs/m8-final-local-evidence.md) remains a record of fixture-only checks on an earlier checkout. A later private Kaggle run and current-main local app audit supersede its fixture-only description of the **current** project. See the [current evidence index](../docs/current-evidence.md) for the actual captures and gaps. Private task files named there are local evidence, not links a grader can open from this repository.

## Suggested walkthrough

1. **Scope and source.** Show the [README](../README.md), [source manifest](../data/source-manifests/kaggle.steam-store-games-clean.json), and [Kaggle handoff](../docs/kaggle-steam-store-bundle.md). Use the [current evidence index](../docs/current-evidence.md) for the completed private run and exact bundle identity, and the source manifest for attribution and accepted usage constraints.
2. **Application.** Show `frontend/`, `backend/`, `backend/alembic/versions/`, and `docker-compose.yml`. The current React UI has a paged, searchable catalog and a selected-game detail screen. Selecting a game requests similar games by stable slug and excludes the seed. Use the [selected two captures](../docs/current-evidence.md#selected-application-screenshots) for catalog/library and selected-game recommendations. Some catalog cards look blank; the captures do not prove all remote images decoded. The artwork component tries same-ID assets and shows a title placeholder if candidates fail. The UI does not offer saved-game controls, though the API implements GET, PUT, and DELETE for a shared PostgreSQL list.
3. **Local verification.** Use the [current evidence index](../docs/current-evidence.md) for the recorded real-bundle readiness, tests, runtime users, and API/browser observations. Fixture mode and the committed self-authored sample still support reproducible local/CI smoke checks when the private bundle is unavailable. Do not present the fixture response as the real-bundle response.
4. **CI and security.** Show `.github/workflows/ci.yml`; use the [current evidence index](../docs/current-evidence.md) for the observed Actions run, scan policy/results, publish logs, and registry visibility limits. The configured scan gate is not a universal vulnerability-free guarantee.
5. **Infrastructure boundary.** Show `terraform/`, `k8s/namespace.yaml`, `helm/`, `deploy/gitops/`, and `monitoring/`. Use the [current evidence index](../docs/current-evidence.md#evidence-still-absent-or-deferred) for static check results and deployment limits, and [M10](M10-WALKTHROUGH.md) for the outstanding walkthrough steps.

For a fixture-only API smoke check with the default Compose stack, use:

```bash
docker compose up --build
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl -X POST http://localhost:8000/api/recommendations \
  -H 'content-type: application/json' \
  -d '{"mode":"cozy","favorite_game":"Cozy Comet Cafe"}'
```

The committed Compose mapping serves the frontend at `http://localhost:5173` and Grafana at `http://localhost:3000`. The private audit used a task-only override to capture the app at port 3000. To show real-catalog recommendations, follow the [bundle handoff](../docs/kaggle-steam-store-bundle.md) with the private zip and `RECOMMENDER_MODE=content`; do not claim the default Compose request above uses that bundle.

## Evidence to supply and outstanding criteria

Supply at most the two application images selected in the [current evidence index](../docs/current-evidence.md#selected-application-screenshots), together with its supporting localhost records. That index owns the capture filenames, observed URLs, address-bar limitation, and private artifact locations; the images are not committed or automatically attached to a submission.

Use the index’s [remaining evidence gaps](../docs/current-evidence.md#evidence-still-absent-or-deferred) and [M10](M10-WALKTHROUGH.md) to prepare outstanding screenshots and deployment presentation proof. No recording or completed slide deck is claimed here.

The real bundle is a local TF-IDF/tag baseline on a historical snapshot. It does not support claims of tuned accuracy, personalization, live trends, current Steam coverage, neural fine-tuning, unrestricted data or artwork rights, or production deployment.
