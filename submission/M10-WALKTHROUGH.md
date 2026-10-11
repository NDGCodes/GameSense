# M10 Walkthrough and Evidence Checklist

Use this file while preparing the final submission. Do not mark cloud, cluster, monitoring, or video evidence complete until it has been verified in the target environment.

## What this repository slice can prove locally

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
- Helm static validation: run `helm lint deploy/helm/gamesense` and `helm template gamesense deploy/helm/gamesense`.
- Terraform static validation: run `terraform -chdir=infra/terraform fmt -check -recursive`, `terraform -chdir=infra/terraform init -backend=false`, and `terraform -chdir=infra/terraform validate`.

## Evidence that still requires real external setup

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
- Submission video/slides that show only evidence actually captured from the environment being claimed.

## External prerequisites

- AWS account, region, IAM permissions, and budget approval.
- Terraform CLI and AWS CLI configured outside the repository.
- kubectl, Helm, and Argo CD access.
- Container registry access and GitHub Actions permissions.
- DNS/ingress/TLS decisions for the public endpoint.
- Database credentials stored in a secret manager or Kubernetes Secret, never committed to git.

## Out-of-scope for this phase

- Downloading Steam or other third-party datasets before license and usage terms are verified.
- Training, serving, or tuning recommendation models.
- Claiming production readiness, live cluster health, or monitoring evidence from local-only validation.
