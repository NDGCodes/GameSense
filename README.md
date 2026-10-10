# GameSense

GameSense is an initial foundation for a Steam-game discovery and recommendation app. This repository is intentionally scoped as the first build slice: it provides runnable local services, container and Kubernetes scaffolding, Terraform starter files for AWS EKS, GitOps manifests, and observability assets without claiming that cloud resources or live dashboards already exist.

## Architecture overview

- `frontend/` - React/Vite single-page app for search and recommendation-mode demos.
- `backend/` - FastAPI service with health, recommendation, and Prometheus metrics endpoints.
- `infra/terraform/` - AWS VPC and EKS starter configuration for the M10 infrastructure walkthrough.
- `deploy/helm/` - Helm chart for the app workload, service, ingress, and Prometheus annotations.
- `deploy/gitops/` - Argo CD application manifest pointing at the Helm chart.
- `observability/prometheus/` - Local Prometheus scrape configuration.
- `observability/grafana/` - Grafana dashboard provisioning and a starter app metrics dashboard.
- `submission/` - M10 walkthrough checklist and evidence placeholders.

## Local development

Prerequisites: Docker, Docker Compose, Node.js 20+, Python 3.11+, and optionally Terraform, kubectl, Helm, and an AWS account for the cloud walkthrough.

```bash
# Run local app, API, Prometheus, and Grafana
docker compose up --build

# API only
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# UI only
cd frontend && npm install && npm run dev
```

Local URLs after `docker compose up --build`:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- Backend metrics: http://localhost:8000/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin for local demo only)

## M10 walkthrough checklist

Implemented artifacts in this slice:

- [x] Demo-oriented codebase structure and key files.
- [x] React/Vite frontend shell wired to the API.
- [x] FastAPI backend with `/health`, `/api/recommendations`, and `/metrics`.
- [x] Docker Compose local validation path.
- [x] Helm chart for Kubernetes deployment, service, and ingress.
- [x] Argo CD application manifest for GitOps demonstration.
- [x] Prometheus scrape config and Grafana dashboard starter.
- [x] Terraform starter for AWS VPC, public subnets, and EKS managed node group.

Requires real external setup before claiming evidence:

- [ ] GitHub repository, branch push, and GitHub Actions run.
- [ ] `terraform init/plan/apply` against an AWS account.
- [ ] Verified AWS Console VPC, subnets, and EKS node group.
- [ ] Argo CD installation and synced application in a real cluster.
- [ ] Healthy Kubernetes pods, services, and ingress with reachable endpoints.
- [ ] Prometheus target confirmed `UP` in the deployed environment.
- [ ] Grafana dashboard showing live application metrics.
- [ ] Submission video and slides with real screenshots/recordings.

Do not treat this scaffold as production-ready. Secrets, registry coordinates, domain names, TLS, managed database provisioning, and recommendation model training are deliberate follow-up work.
