# M9 submission package: current local evidence

This is a reviewer-facing walkthrough and evidence index for the current GameSense repository. The dated [M8 freeze](../docs/m8-final-local-evidence.md) remains a record of fixture-only checks on an earlier checkout. A later private Kaggle run and current-main local app audit supersede its fixture-only description of the **current** project. See the [current evidence index](../docs/current-evidence.md) for the actual captures and gaps. Private task files named there are local evidence, not links a grader can open from this repository.

## Suggested walkthrough

1. **Scope and source.** Show the [README](../README.md), [source manifest](../data/source-manifests/kaggle.steam-store-games-clean.json), and [Kaggle handoff](../docs/kaggle-steam-store-bundle.md). The approved private Kaggle notebook fitted a sparse TF-IDF/tag baseline from the historical Steam Store Games snapshot and returned a private 27,075-game bundle. Its algorithm is `tfidf-tag-content-baseline`, model version `gamesense-steam-store-tfidf-tag-v1`, and snapshot label `kaggle.steam-store-games-clean-local-snapshot`. The bundle has stable Steam ID based slugs and was loaded locally. These labels are not exact-run hashes; the private bundle SHA-256 and source hashes identify the observed run. Attribute Nik Davis's Kaggle dataset and disclose unresolved Steam/SteamSpy upstream terms. This local acceptance is not redistribution clearance.
2. **Application.** Show `frontend/`, `backend/`, `backend/alembic/versions/`, and `docker-compose.yml`. The current React UI has a paged, searchable catalog and a selected-game detail screen. Selecting a game requests similar games by stable slug and excludes the seed. Use the [selected two captures](../docs/current-evidence.md#selected-application-screenshots) for catalog/library and selected-game recommendations. Some catalog cards look blank; the captures do not prove all remote images decoded. The artwork component tries same-ID assets and shows a title placeholder if candidates fail. The UI does not offer saved-game controls, though the API implements GET, PUT, and DELETE for a shared PostgreSQL list.
3. **Local verification.** Point to the [current evidence index](../docs/current-evidence.md): the isolated Compose run reported PostgreSQL ready and 27,075 catalog items; `pytest -v backend/tests` returned 58 passed, 1 skipped, 1 warning; both built images ran as non-root users; saved-game PUT/GET/DELETE and browser catalog/recommendation calls worked. Fixture mode and the committed self-authored sample still support reproducible local/CI smoke checks when the private bundle is unavailable. Do not present the fixture response as the real-bundle response.
4. **CI and security.** Show `.github/workflows/ci.yml` and [the observed successful main run](https://github.com/NDGCodes/GameSense/actions/runs/38832359777). It ran tests and frontend build, scanned both images with the HIGH/CRITICAL failure gate, then logged GHCR pushes tagged `ff4734a`. This supports a successful publish operation in that run. GHCR package-page visibility to a grader is unverified; its screenshot is absent. The configured scan found zero matching issues in those image builds under `ignore-unfixed`, not a universal vulnerability-free result.
5. **Infrastructure boundary.** Show `terraform/`, `k8s/namespace.yaml`, `helm/`, `deploy/gitops/`, and `monitoring/`. Terraform fmt/init/validate and Helm lint/render passed locally. Helm renders two configured replicas each, ClusterIP services, and Ingress paths `/api` to backend and `/` to frontend. These are definitions and static checks. No AWS-backed plan, EKS installation, live pods/ingress, destroy, cluster monitoring, or final commit-to-deployment demonstration is evidenced.

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

Select at most two application browser PNGs for the submission: `gamesense-grading-evidence/screenshots/2026-10-16-main-localhost-3000-application.png` for the catalog at verified `http://localhost:3000/`, and `gamesense-grading-evidence/screenshots/2026-10-16-main-desktop-recommendations.png` for the selected-game result at verified `http://127.0.0.1:25184/`. The other five originals stay private as backups. The PNGs crop browser chrome, so neither shows the URL in the address bar; the [evidence index](../docs/current-evidence.md#selected-application-screenshots) names the supporting session/Compose/health records and the window-capture limit. They are not committed or automatically attached to a submission. The same private task holds original pytest, Compose, CI, Trivy, Terraform, and Helm output files.

Genuine terminal screenshots of pytest and Compose startup, GitHub history/green-run/Trivy screenshots, and GHCR package-page screenshots remain uncaptured or access-blocked. The repository is private and evaluator access is unverified. Live AWS/EKS, Kubernetes/Ingress, cluster observability, and a final deployed-update demo remain deferred. [M10](M10-WALKTHROUGH.md) tracks the remaining presentation proof. No recording or completed slide deck is claimed here.

The real bundle is a local TF-IDF/tag baseline on a historical snapshot. It does not support claims of tuned accuracy, personalization, live trends, current Steam coverage, neural fine-tuning, unrestricted data or artwork rights, or production deployment.
