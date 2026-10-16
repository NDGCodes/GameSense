# M10 Walkthrough and Evidence Checklist

Use this file while preparing the final submission. The [current evidence index](../docs/current-evidence.md) records what was actually captured on current main; the [M8 freeze](../docs/m8-final-local-evidence.md) is historical. Choose at most the two selected application images for submission; five other originals remain private backups. The other screenshot and deployed-demo criteria below remain open.

## Verified local evidence this repository can produce

- Codebase tour: show `frontend/`, `backend/`, `terraform/`, `helm/`, `deploy/gitops/`, `monitoring/`, and `submission/`.
- Backend migration/test path: run `cd backend && python -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt -r requirements-dev.txt && pytest -q`.
- Frontend build: run `cd frontend && npm ci && npm run build`.
- Compose config: run `docker compose config --quiet` and, where Docker resources are available, `docker compose up --build`.
- Fixture-mode API smoke checks after the default Compose stack starts:
  - `curl http://localhost:8000/health`
  - `curl http://localhost:8000/ready`
  - `curl -X POST http://localhost:8000/api/recommendations -H 'content-type: application/json' -d '{"mode":"cozy","favorite_game":"Cozy Comet Cafe"}'`
  - Confirm this default response identifies demo fixtures. For real-catalog recommendations, follow the [bundle handoff](../docs/kaggle-steam-store-bundle.md) with the private zip and `RECOMMENDER_MODE=content`.
- Current UI: browse/search the paged catalog at http://localhost:3000, select a game, and inspect its detail and similar-game cards. Genre filters apply to all loaded games. Saved-game GET/PUT/DELETE is an API capability, not a visible UI control. Artwork is best effort; a blank-looking catalog card in a capture is not proof of a decoded image.
- Local observability smoke checks after Compose starts:
  - Prometheus at http://localhost:9090 can scrape `gamesense-backend-local`.
  - Grafana at http://localhost:3001 loads the GameSense dashboard from provisioning.
- Helm static validation: run `helm lint helm`, `helm template gamesense helm`, and `helm template gamesense-content helm --set backend.recommender.mode=content`.
  - The default rendered chart keeps `RECOMMENDER_MODE=fixture`.
  - The content render sets `RECOMMENDER_MODE=content`, sets `CONTENT_FIXTURE_PATH=/app/data/fixtures/ml/sample_games.self-authored.json`, and mounts only the committed self-authored sample fixture from the chart artifact ConfigMap. The ConfigMap is annotated with the fixture path and SHA-256 checksum for review, but the backend does not enforce checksum verification at runtime.
- For the completed private Kaggle run and local API/browser results, see the [current evidence index](../docs/current-evidence.md); for repeat setup and limitations, follow the [handoff guide](../docs/kaggle-steam-store-bundle.md).
- Terraform static validation: run `terraform -chdir=terraform fmt -check -recursive`, `terraform -chdir=terraform init -backend=false`, and `terraform -chdir=terraform validate`.

## Evidence already observed on current main

Use the [current evidence index](../docs/current-evidence.md) for recorded test/API/runtime results, the selected application PNGs and supporting localhost records, and the observed Actions/Trivy/GHCR results. It owns capture filenames and URLs, private artifact locations, and evidence limitations.

## Evidence that still requires capture or external setup

- Genuine terminal screenshots of the current pytest and Compose startup output; original logs are private but are not screenshots.
- GitHub commit-history, green-run, and Trivy-output browser screenshots, and both GHCR SHA-tag package-page screenshots. The isolated browser could not access the private repository, and the package-listing API lacked `read:packages`. The repository's evaluator access and submission-form URL also remain unverified.
- `terraform plan` and `terraform apply` against an authorized AWS account.
- AWS Console verification of the VPC, public/private subnets, NAT gateway, EKS cluster, and managed node group.
- `aws eks update-kubeconfig` and `kubectl` access to the created cluster.
- Argo CD installation, application creation from `deploy/gitops/argocd-application.yaml`, and synced/healthy status.
- Kubernetes `gamesense` namespace applied and healthy deployments, services, pods, and ingress. The chart statically configures two replicas for each app, ClusterIP services, and `/api` and `/` Ingress paths; no live cluster proof exists.
- A configured `DATABASE_URL` Secret or a consciously accepted ephemeral SQLite demo mode for the cluster walkthrough.
- Prometheus target confirmed `UP` in the deployed environment.
- Grafana dashboard populated with live request and latency metrics from the deployed backend.
- A real commit → pipeline → deployed-update walkthrough or recording; a successful CI run alone does not prove a deployed update.
- Submission video/slides using only evidence actually captured from the environment being claimed. No completed recording or slide deck is evidenced here.

## External prerequisites

- AWS account, region, IAM permissions, and budget approval.
- Terraform CLI and AWS CLI configured outside the repository.
- kubectl, Helm, and Argo CD access.
- Container registry access and GitHub Actions permissions.
- DNS/ingress/TLS decisions for the public endpoint.
- Database credentials stored in a secret manager or Kubernetes Secret, never committed to git.

## Out-of-scope for this phase

- External data use beyond the recorded scope in the [source manifest](../data/source-manifests/kaggle.steam-store-games-clean.json).
- Accuracy tuning, fine-tuning, and deployment of generated artifacts.
- Claiming production readiness, live cluster health, or monitoring evidence from local-only validation.

## Historical M8 local evidence freeze

The [M8 evidence ledger](../docs/m8-final-local-evidence.md) records commands, interpreter coverage, raw artifact names, and non-claims for that earlier fixture-only checkout. Use the [current evidence index](../docs/current-evidence.md) for later Kaggle, current-main app, and CI observations.
