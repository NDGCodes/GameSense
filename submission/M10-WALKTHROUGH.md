# M10 Walkthrough and Evidence Checklist

Use this file while preparing the final submission. Do not mark cloud, cluster, monitoring, or video evidence complete until it has been verified in the target environment. This checklist separates evidence verified from local repository commands from cloud/deployment evidence that has not been performed in this branch.

## Verified local evidence this repository can produce

- Codebase tour: show `frontend/`, `backend/`, `infra/terraform/`, `deploy/helm/`, `deploy/gitops/`, `observability/`, and `submission/`.
- Backend migration/test path: run `cd backend && python -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt -r requirements-dev.txt && pytest -q`.
- Frontend build: run `cd frontend && npm ci && npm run build`.
- Compose config: run `docker compose config --quiet` and, where Docker resources are available, `docker compose up --build`.
- API smoke checks after Compose starts:
  - `curl http://localhost:8000/health`
  - `curl http://localhost:8000/ready`
  - `curl -X POST http://localhost:8000/api/recommendations -H 'content-type: application/json' -d '{"mode":"cozy","favorite_game":"Cozy Comet Cafe"}'`
  - Confirm the response says the catalog is demo fixtures, not a real Steam dataset or ML output.
- Local observability smoke checks after Compose starts:
  - Prometheus at http://localhost:9090 can scrape `gamesense-backend-local`.
  - Grafana at http://localhost:3000 loads the GameSense dashboard from provisioning.
- Helm static validation: run `helm lint deploy/helm/gamesense`, `helm template gamesense deploy/helm/gamesense`, and `helm template gamesense-content deploy/helm/gamesense --set backend.recommender.mode=content`.
  - The default rendered chart keeps `RECOMMENDER_MODE=fixture`.
  - The content render sets `RECOMMENDER_MODE=content`, sets `CONTENT_FIXTURE_PATH=/app/data/fixtures/ml/sample_games.self-authored.json`, and mounts only the committed self-authored sample fixture from the chart artifact ConfigMap. The ConfigMap is annotated with the fixture path and SHA-256 checksum for review, but the backend does not enforce checksum verification at runtime.
- Kaggle notebook and returned-bundle workflow: follow the [authoritative handoff guide](../docs/kaggle-steam-store-bundle.md). This is separate from the fixture-only local evidence below.
- Terraform static validation: run `terraform -chdir=infra/terraform fmt -check -recursive`, `terraform -chdir=infra/terraform init -backend=false`, and `terraform -chdir=infra/terraform validate`.

## Evidence that still requires real external setup and has not been performed here

- GitHub Actions run on the pushed branch/PR, including backend tests, frontend build, Compose config, Terraform validate, Helm lint/render, Docker image build, and Trivy scan.
- GHCR image publishing from a push to `main` after review/merge.
- `terraform plan` and `terraform apply` against an authorized AWS account.
- AWS Console verification of the VPC, public/private subnets, NAT gateway, EKS cluster, and managed node group.
- `aws eks update-kubeconfig` and `kubectl` access to the created cluster.
- Argo CD installation, application creation from `deploy/gitops/argocd-application.yaml`, and synced/healthy status.
- Kubernetes `gamesense` namespace showing healthy deployments, services, pods, and ingress.
- A configured `DATABASE_URL` Secret or a consciously accepted ephemeral SQLite demo mode for the cluster walkthrough.
- Prometheus target confirmed `UP` in the deployed environment.
- Grafana dashboard populated with live request and latency metrics from the deployed backend.
- User-run Kaggle notebook and returned-bundle verification: follow the [handoff guide](../docs/kaggle-steam-store-bundle.md). No real-data Kaggle run is claimed by this checklist.
- Submission video/slides that show only evidence actually captured from the environment being claimed.

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

## Milestone 8 local evidence freeze

Record only commands that were actually run for this branch. See the [M8 evidence ledger](../docs/m8-final-local-evidence.md) for the captured results, interpreter coverage, raw artifact location, and explicit non-claims.
