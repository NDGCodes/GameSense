# GameSense

GameSense is a Steam-style game discovery app foundation for the DevOps/app-infrastructure phase of the project. This slice proves the local app, database migration, tests, containerization, CI/CD, GitOps, Kubernetes, Terraform, observability paths, and a license-scoped content-bundle path for a user-run Kaggle notebook.

The repository does **not** commit raw Steam/Kaggle data, generated recommendation bundles, fine-tuned models, live Steam trend signals, or unrestricted redistribution claims. Fixture mode still uses a tiny hand-written demo catalog so local and CI flows are testable without downloading or misrepresenting a real Steam dataset. Content mode can load a returned local Kaggle bundle from an ignored path when the user supplies it.

## Architecture overview

- `frontend/` - React/Vite single-page app that calls the API, labels demo-fixture recommendations, and can list catalog titles from a loaded content bundle.
- `backend/` - FastAPI service with health/readiness checks, database-backed recommendation fixtures, content-bundle loading, Alembic migrations, tests, and Prometheus metrics.
- `docker-compose.yml` - local Postgres, backend, frontend, Prometheus, and Grafana stack.
- `.github/workflows/ci.yml` - CI validation, Docker image build, Trivy image scanning, and GHCR publishing on `main` pushes.
- `terraform/` - AWS VPC and EKS foundation (plan/apply only with explicit cloud authorization).
- `helm/` - Helm chart for the frontend/backend workloads, services, ingress, probes, and scrape annotations.
- `deploy/gitops/` - Argo CD `Application` manifest for the Helm chart.
- `monitoring/` - Prometheus scrape config and Grafana dashboard provisioning.
- `submission/` - [M9 local submission package](submission/M9-SUBMISSION-PACKAGE.md) plus [M10 walkthrough and evidence checklist](submission/M10-WALKTHROUGH.md).

The [current local rubric evidence index](docs/local-rubric-evidence.md) records the latest tests, full-stack browser flow, image scans, and static infrastructure checks. It separates these from live cloud and submission proof.

## Local development

Prerequisites: Docker, Docker Compose, Node.js 20+, Python 3.10 or 3.11 for the supported local backend test path, and optionally Terraform, Helm, kubectl, and AWS credentials for later infrastructure validation.

```bash
# Run the local full stack: Postgres, migrations, API, frontend, Prometheus, Grafana
docker compose up --build

# Smoke-test content recommender mode against the committed self-authored sample fixture
docker compose --profile content-smoke run --rm content-smoke

# API only with local SQLite (runs migrations first)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload

# UI only; set VITE_API_BASE_URL=http://localhost:8000 if not using nginx proxy
cd frontend
npm ci
npm run dev
```

Local URLs after `docker compose up --build`:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- Backend health: http://localhost:8000/health
- Backend readiness: http://localhost:8000/ready
- Backend metrics: http://localhost:8000/metrics
- Shared demo saved-game list: `GET /api/saved-games`, `PUT /api/saved-games/{active-catalog-slug}` with `{"note":"..."}`, and `DELETE /api/saved-games/{slug}`. The list persists in PostgreSQL and does not alter the catalog or recommendation ranking.
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin, local demo only)

## Validation commands

```bash
# Backend API, migration, catalog, and local ML data-pipeline tests
cd backend
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
pytest -q

# Milestone 2 local-only ML data-validation pipeline for the tiny self-authored sample
python -m app.ml_pipeline source-check --manifest ../data/source-manifests/example.self-authored.json --repo-root ..
python -m app.ml_pipeline normalize --manifest ../data/source-manifests/example.self-authored.json --fixture ../data/fixtures/ml/sample_games.self-authored.json --output /tmp/gamesense-ml-m2/normalized.json
python -m app.ml_pipeline validate --manifest ../data/source-manifests/example.self-authored.json --normalized /tmp/gamesense-ml-m2/normalized.json --output /tmp/gamesense-ml-m2/validation.json
python -m app.ml_pipeline manifest --manifest ../data/source-manifests/example.self-authored.json --normalized /tmp/gamesense-ml-m2/normalized.json --validation-report /tmp/gamesense-ml-m2/validation.json --output /tmp/gamesense-ml-m2/pipeline-manifest.json

# Milestone 4 offline evaluation for the local baseline recommender
python -m app.ml_evaluation
python -m app.ml_evaluation --output /tmp/gamesense-ml-m4/evaluation.json

# Focused CI coverage for the local ML data pipeline and integrated recommender
pytest -q tests/test_ml_pipeline.py tests/test_recommender.py tests/test_api.py

# Frontend build
cd frontend
npm ci
npm run build

# Compose, Helm, and Terraform static validation
docker compose config --quiet
helm lint helm
helm template gamesense helm >/tmp/gamesense-rendered.yaml
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform init -backend=false
terraform -chdir=terraform validate
```

Terraform commands download providers/modules but must not be followed by `plan` or `apply` unless AWS usage is authorized. Do not claim live AWS, Kubernetes, Prometheus, Grafana, or submission evidence until it is verified in the target environment.

The [M8 final local evidence freeze and claim audit](docs/m8-final-local-evidence.md) maps README and walkthrough claims to local/static evidence or explicit non-claims, including interpreter coverage.

## Kaggle content-bundle handoff

See [Kaggle Steam Store bundle handoff](docs/kaggle-steam-store-bundle.md) for notebook setup, returned artifacts, local backend startup, catalog selection, and recommendation limitations. The [source manifest](data/source-manifests/kaggle.steam-store-games-clean.json) owns the selected source’s provenance, attribution, and accepted usage scope.

## Demo fixture catalog

The migration in `backend/alembic/versions/` creates `demo_games` and inserts a small set of fictional, hand-written records with `source = "demo-fixture"`. These fixtures exist only to make API/UI/database flows reproducible. They are not a real Steam catalog, were not downloaded, and were not generated by a recommendation model.

## Recommendation observability

The API exposes local Prometheus metrics at `/metrics`; Docker Compose scrapes them and provisions the existing Grafana dashboard. Recommendation metrics intentionally use bounded labels only (`mode`, `algorithm`, `version`, `data_snapshot`, and fallback `reason`) and never include favorite-game text, user identifiers, secrets, or request bodies.

Planned/implemented local metrics for the integrated recommender:

- `gamesense_recommendation_requests_total{mode,algorithm,version,data_snapshot}` - request counts by recommender mode and model/version metadata.
- `gamesense_recommendation_fallbacks_total{reason,algorithm}` - bounded fallback counts, currently including content-mode similar-seed fallbacks.
- `gamesense_recommendation_model_info{algorithm,version,data_snapshot}` - info-style gauge set to `1` for the active response metadata.
- `gamesense_recommendation_catalog_items{algorithm,data_snapshot}` - active catalog item count visible to the recommender.
- Existing HTTP and latency metrics remain available as `gamesense_http_requests_total` and `gamesense_recommendation_seconds`.

These dashboards are local development assets only; this repository state does not claim a live deployment or active monitoring.

## Deployment notes

- Docker Compose uses local Postgres credentials only for the disposable development stack.
- The backend reads `DATABASE_URL` when provided and otherwise falls back to local SQLite for quick manual runs.
- The Helm chart can consume a Kubernetes Secret containing `DATABASE_URL` via `backend.database.urlSecretName`; without one, the container falls back to ephemeral SQLite for demo rendering.
- The frontend Nginx image proxies API calls through `BACKEND_UPSTREAM`; Compose defaults it to `backend:8000`, and the Helm chart sets it to the rendered backend Service name.
- Chart defaults point at the expected GHCR image names; use `helm/values-local.yaml` for local clusters with preloaded images.
- CI publishes images to GHCR only on pushes to `main`; pull requests build and scan images locally without pushing.
- Argo CD points at this repository's `main` branch and the Helm chart path. Confirm image visibility/auth, DNS, TLS, and database secret values during a real deployment.

## Current scope checklist

Implemented in this slice:

- [x] Full-stack local app foundation with API/UI flow.
- [x] Database-backed demo catalog with Alembic migration and tests.
- [x] Dockerfiles and Docker Compose for local app, database, Prometheus, and Grafana.
- [x] GitHub Actions validation, image build/publish workflow, and Trivy scanning.
- [x] Terraform foundation for AWS VPC and EKS.
- [x] Helm chart and Argo CD GitOps manifest.
- [x] Prometheus metrics and Grafana dashboard starter.
- [x] M9 local submission package and walkthrough checklist that separate local evidence from cloud evidence.
- [x] Local baseline recommender and offline smoke evaluation/model card for the tiny self-authored fixture.
- [x] Kaggle notebook handoff and local content-bundle loader for the selected Steam Store Games source, with attribution and uncertainty disclosures.
- [x] Responsive recommendation cover cards with identity-bound Steam headers, same-game capsule fallback, and missing-artwork placeholders for the local demo.
- [x] Returned real bundle imported and catalog artwork checked locally; see [coverage evidence and repeatable checks](docs/kaggle-steam-store-bundle.md#verified-catalog-artwork).

Deferred until the later authorized phases:

- [ ] Accuracy tuning, fine-tuning, generated artifact deployment, or real-data quality claims.
- [ ] Production database provisioning, secrets management, TLS, DNS, and live AWS deployment.
