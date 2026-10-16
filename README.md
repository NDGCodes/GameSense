# GameSense

GameSense is a Steam-style game discovery web app. You can browse and search a game catalog, filter it by genre, open a game, and get similar-game recommendations with Steam artwork. Recommendations come from a content-based model: sparse TF-IDF over each game's tags, genres, and description, fitted on the Kaggle *Steam Store Games* dataset.

The project is also a complete DevOps capstone. Every push to `main` is tested, security-scanned, containerised, published to GitHub Container Registry, and deployed to AWS EKS through GitOps with Argo CD. Prometheus and Grafana monitor the running app.

## Demo and evidence

Everything for review lives in [`demo/`](demo/):

| Item | File |
|---|---|
| Presentation deck (36 slides) | [`demo/GameSense-Capstone.pptx`](demo/GameSense-Capstone.pptx) · [PDF](demo/GameSense-Capstone.pdf) |
| Presentation video: slides, then a live walkthrough | [`demo/CapstoneProject_Video.mp4`](demo/CapstoneProject_Video.mp4) |
| Evidence screenshots | [`demo/screenshots/`](demo/screenshots/) |

| Module | Evidence |
|---|---|
| M1 Application | [App at localhost:3000](demo/screenshots/M1-M4-application-localhost-3000.png) |
| M2 Testing | [pytest -v](demo/screenshots/M2-pytest-api-command-log.png) · [59 passed](demo/screenshots/M2-pytest-result-command-log.png) |
| M3 Git | [Commit history](demo/screenshots/M3-git-history-command-log.png) |
| M4 Docker | [docker compose up --build](demo/screenshots/M4-compose-command-log.png) · [non-root containers](demo/screenshots/M4-runtime-command-log.png) |
| M5 CI/CD | [Green Actions run](demo/screenshots/M5-github-actions-success.png) · [GHCR backend](demo/screenshots/M5-ghcr-backend-sha.png) · [GHCR frontend](demo/screenshots/M5-ghcr-frontend-sha.png) |
| M6 Trivy | [Trivy scan output](demo/screenshots/M6-trivy-backend.png) and [explanation](#security-scanning-trivy) |
| M7 Terraform | [plan](demo/screenshots/M7-terraform-plan-command-log.png) · [apply](demo/screenshots/M7-terraform-apply.png) · [EKS console](demo/screenshots/M7-aws-console-eks-cluster.png) · [VPC console](demo/screenshots/M7-aws-console-vpc.png) |
| M8 Kubernetes | [pods](demo/screenshots/M8-eks-pods.png) · [services](demo/screenshots/M8-eks-svc.png) · [helm list + Ingress](demo/screenshots/M8-eks-helm.png) · [app via Ingress](demo/screenshots/M8-eks-app-ingress.png) · [Argo CD synced](demo/screenshots/M8-argocd-synced.png) |
| M9 Observability | [/metrics](demo/screenshots/M9-eks-metrics.png) · [Prometheus targets UP](demo/screenshots/M9-eks-prometheus-up.png) · [Grafana dashboard](demo/screenshots/M9-eks-grafana.png) |

The AWS console screenshots show the `Nishant_Aws` account name while blurring the account number, including its appearances in ARNs. The author's email remains blurred in the Argo CD screenshot.

## Architecture

```mermaid
flowchart LR
    dev[Developer] -->|git push main| gha[GitHub Actions<br/>test · build · Trivy]
    gha -->|images :sha| ghcr[(GHCR)]
    gha -->|commit tag to<br/>helm/values-eks.yaml| git[(GitHub repo)]
    git -->|watched by| argo[Argo CD]
    subgraph aws[AWS ap-south-1 · provisioned by Terraform]
      subgraph eks[EKS 1.35 · 2 × t3.medium]
        argo -->|helm render + sync| app
        subgraph app[namespace gamesense]
          fe[Frontend ×2<br/>React + Nginx]
          be[Backend ×2<br/>FastAPI]
          db[(PostgreSQL)]
          prom[Prometheus] --> graf[Grafana]
        end
        lb[Traefik Ingress<br/>AWS load balancer]
      end
    end
    ghcr -. pull .-> app
    user[Browser] --> lb
    lb -->|/| fe
    lb -->|/api| be
    be --> db
    prom -->|scrape /metrics| be
```

| Component | Role |
|---|---|
| `frontend/` | React 19 + Vite catalog, search, genre filter, game detail, similar-game cards. Served by unprivileged Nginx, which proxies `/api` to the backend. |
| `backend/` | FastAPI API, SQLAlchemy models, Alembic migrations, recommender, Prometheus metrics, pytest suite. |
| PostgreSQL | Demo catalog and the saved-games list. Compose and EKS both run PostgreSQL 16. |
| `.github/workflows/ci.yml` | CI/CD: tests, frontend build, image build, Trivy, GHCR publish, GitOps tag update. |
| `terraform/` | AWS VPC and EKS cluster with a managed node group, plus optional ECR repositories. |
| `k8s/` | Namespace and the disposable PostgreSQL manifest. |
| `helm/` | Application chart: Deployments, Services, Ingress, probes, scrape annotations. `values-eks.yaml` is the EKS overlay. |
| `deploy/gitops/` | Argo CD `Application` that deploys the chart from `main`. |
| `monitoring/` | Prometheus and Grafana: a Helm chart for the cluster and config files for Compose. |
| `data/`, `notebooks/` | Data source manifests, a tiny self-authored fixture, and the Kaggle notebook that fits the model. |
| `demo/` | Deck, video, and evidence screenshots. |

## Tech stack

| Area | Tools |
|---|---|
| Languages | Python 3.11, JavaScript (React 19), HCL, YAML |
| Backend | FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, pg8000, Uvicorn |
| Frontend | React 19, Vite 8, Nginx |
| Database | PostgreSQL 16 (SQLite for tests and quick local runs) |
| ML | Sparse TF-IDF + tag/genre similarity in pure Python, fitted in a Kaggle notebook |
| Testing & quality | pytest, frontend build, `helm lint`, `terraform fmt`/`validate` |
| Security | Trivy image scanning (HIGH/CRITICAL gate), non-root containers, secrets kept out of Git |
| Containers | Docker (multi-stage frontend), Docker Compose |
| CI/CD | GitHub Actions, GitHub Container Registry (GHCR) |
| Infrastructure | Terraform, AWS VPC, EKS, EC2 managed node group, optional ECR |
| Kubernetes | Helm, Traefik ingress, Argo CD (GitOps) |
| Observability | `prometheus_client`, Prometheus, Grafana |

## Application

### REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness: database reachable and catalog size |
| GET | `/api/games` | Catalog page. Supports `q`, `limit` (1–1000, default 500), and `offset` |
| POST | `/api/recommendations` | Recommendations for `{"mode": "similar"\|"cozy"\|"competitive"\|"trending", "favorite_game": "<slug or title>"}` |
| GET | `/api/saved-games` | Shared saved-games list (PostgreSQL) |
| PUT | `/api/saved-games/{slug}` | Save a catalog game (idempotent) |
| DELETE | `/api/saved-games/{slug}` | Remove a saved game |
| GET | `/metrics` | Prometheus metrics |

Interactive API docs are served at `/docs`.

### Database and migrations

`backend/alembic/versions/` holds three migrations: the demo game table with fictional fixture rows, the canonical catalog tables, and the saved-games table. Run them with `alembic upgrade head`.

### Recommender modes

- **Fixture mode** (default; used in CI and plain Compose): six fictional, hand-written demo games stored in the database, so every flow is testable without external data.
- **Content mode** (`RECOMMENDER_MODE=content`): loads a content bundle zip from `CONTENT_BUNDLE_PATH`. The bundle holds the catalog, TF-IDF vocabulary, and item vectors, and its checksums are verified on load. *Similar* ranks by cosine similarity and excludes the seed game; if a seed has no similar candidates, the model falls back to the *cozy* scorer. Without a bundle, content mode uses the committed self-authored sample.

The Kaggle notebook (`notebooks/gamesense_baseline_kaggle.ipynb`) normalises and validates the dataset, fits the bundle, and writes it to Kaggle's working directory. The full bundle (27,075 games) stays private. The EKS demo serves a 100-game subset.

## Local setup

Prerequisites: Docker with Compose. Python 3.11 and Node 20+ are needed only for running outside containers.

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| App | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Health / readiness / metrics | http://localhost:8000/health · `/ready` · `/metrics` |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin / admin, local only) |

Compose starts PostgreSQL, runs the migrations, and then starts the backend, the frontend, Prometheus, and Grafana with health checks. The database uses a named volume.

Optional workflows:

```bash
# Content-mode smoke test against the committed self-authored sample
docker compose --profile content-smoke run --rm content-smoke

# Backend only (SQLite fallback when DATABASE_URL is unset)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head && uvicorn app.main:app --reload

# Real catalog locally with a private bundle (never committed)
RECOMMENDER_MODE=content CONTENT_BUNDLE_PATH=/abs/path/to/bundle.zip uvicorn app.main:app --reload

# Frontend dev server on :5173 (set VITE_API_BASE_URL=http://localhost:8000 if not proxied)
cd frontend && npm ci && npm run dev
```

## Testing

```bash
cd backend && pytest -v
```

59 tests cover the API endpoints, Alembic migrations, catalog schemas, the recommender, the ML data pipeline, bundle loading, and artwork mapping. API tests run against a fresh temporary SQLite database built by the migrations (`tmp_path`), never the production database. `backend/tests/conftest.py` configures the import path. One test needs the private bundle and skips when it isn't available.

## CI/CD pipeline

`.github/workflows/ci.yml` runs on every pull request and on every push to `main`.

| Job | What it does | Runs on |
|---|---|---|
| `validate-foundation` | `pytest`, the focused ML tests, `npm ci && npm run build`, `docker compose config`, the content-mode smoke test, `terraform fmt -check` + `validate`, `helm lint` + `helm template` for the app and monitoring charts | PRs and `main` |
| `container-security` (×2) | Builds the backend and frontend images and scans each with Trivy; fails on HIGH/CRITICAL | PRs and `main` |
| `publish-images` (×2) | Pushes `ghcr.io/ndgcodes/gamesense-{backend,frontend}:<short-sha>`. Tags are the commit SHA, never `latest` | `main` only |
| `update-gitops` | Rewrites both image tags in `helm/values-eks.yaml` and commits `Deploy <sha> to EKS [skip ci]` as `github-actions[bot]` | `main` only |

A failing test or a HIGH/CRITICAL CVE stops the run before anything is published. The bot's commit uses `GITHUB_TOKEN`, which does not trigger another workflow run, so there is no loop. Argo CD sees that commit and deploys it.

### Security scanning (Trivy)

Trivy scans each built image for known CVEs, both in the OS packages of its base image (Debian for the backend, Alpine for the Nginx frontend) and in the language libraries inside it (Python packages for the backend). The step uses `severity: HIGH,CRITICAL`, `ignore-unfixed: true`, and `exit-code: 1`, so any HIGH or CRITICAL vulnerability that has a fix available fails the pipeline. The recorded runs report **0** matching findings for both images. That means the gate passed for these builds; it does not mean the images can never contain vulnerabilities, which is why every build is scanned again.

Secrets never go into Git. The database URL, passwords, and registry tokens are Kubernetes Secrets created at deploy time. Terraform state, plans, and `.env` files are git-ignored.

## Terraform infrastructure

`terraform/` uses the official `terraform-aws-modules` VPC (5.x) and EKS (20.24) modules. It provisions:

- A **VPC** `10.42.0.0/16` across two availability zones, with **2 public and 2 private subnets**, one NAT gateway, and the subnet tags EKS needs for load balancers.
- An **EKS 1.35 cluster** with public endpoint access and admin access for the cluster creator.
- A **managed node group** of `t3.medium` nodes on AL2023 (desired 2).
- Optional private **ECR** repositories (`create_demo_registry`), which are force-deleted on destroy.

The capstone run in `ap-south-1` (Mumbai) created **58 resources**.

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars   # set region, allowed_account_ids
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check && terraform -chdir=terraform validate
terraform -chdir=terraform plan -out=tfplan
terraform -chdir=terraform apply tfplan
aws eks update-kubeconfig --region <region> --name <cluster_name>   # printed as an output
```

`allowed_account_ids` makes Terraform refuse to run against any other AWS account. `terraform.tfvars.example` contains no credentials. Authenticate with your normal AWS CLI profile.

## Kubernetes deployment

The first install uses Helm directly. After that, Argo CD owns the release, so the two never compete.

```bash
# 1. Namespace, database credentials (generate the password; never commit it), and PostgreSQL
kubectl apply -f k8s/namespace.yaml
kubectl -n gamesense create secret generic gamesense-database \
  --from-literal=POSTGRES_PASSWORD="$PG_PASSWORD" \
  --from-literal=DATABASE_URL="postgresql+pg8000://gamesense:$PG_PASSWORD@gamesense-postgres:5432/gamesense"
kubectl apply -f k8s/postgres-demo.yaml

# 2. Registry pull secret (GHCR packages are private; token needs read:packages)
kubectl -n gamesense create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io --docker-username=<github-user> --docker-password="$GHCR_TOKEN"

# 3. Optional real-catalog subset for content mode
kubectl -n gamesense create configmap gamesense-content-bundle --from-file=content-bundle.zip=<bundle.zip>

# 4. Migrations: the backend container runs `alembic upgrade head` on start. For the first install, run it once
#    as a Job (backend image, command `alembic upgrade head`, DATABASE_URL from the secret) so replicas don't race

# 5. Ingress controller (Traefik, Kubernetes Ingress provider, LoadBalancer service)
helm repo add traefik https://traefik.github.io/charts
helm upgrade --install gamesense-ingress traefik/traefik -n gamesense-ingress --create-namespace \
  --set providers.kubernetesCRD.enabled=false --set providers.kubernetesIngress.enabled=true \
  --set providers.kubernetesIngress.publishedService.enabled=true --set service.type=LoadBalancer

# 6. Application
helm upgrade --install gamesense helm -n gamesense -f helm/values-eks.yaml --wait

# 7. Verify
kubectl get pods,svc,ingress -n gamesense
helm list -n gamesense
```

The chart runs 2 replicas each of the frontend and backend, with readiness (`/ready`) and liveness (`/health`) probes and ClusterIP Services. One Ingress routes `/` to the frontend and `/api` to the backend. `ingress.host: ""` serves the app on the load balancer hostname, so no DNS is needed. The chart also supports the AWS Load Balancer Controller through `ingress.className: alb`.

### GitOps with Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.5/manifests/install.yaml
# For a private repo: add a repository Secret with a read-only token (label argocd.argoproj.io/secret-type=repository)
kubectl apply -f deploy/gitops/argocd-application.yaml
```

The Application renders `helm/` from `main` with `values.yaml` + `values-eks.yaml`, using automated sync, prune, and self-heal. A push to `main` therefore ends with Argo CD rolling out the new SHA-tagged images, with no manual `kubectl` or `helm` step.

## Observability

The backend exposes Prometheus metrics at `/metrics`. Labels are bounded and never contain user input.

| Metric | Meaning |
|---|---|
| `gamesense_http_requests_total{method,route,status_code}` | Request count by route and status |
| `gamesense_http_request_duration_seconds` | Request latency histogram |
| `gamesense_recommendation_requests_total{mode,algorithm,version,data_snapshot}` | Recommendations served, by mode and model version |
| `gamesense_recommendation_seconds` | Recommendation latency |
| `gamesense_recommendation_fallbacks_total{reason,algorithm}` | Fallbacks (for example, a seed with no similar candidates) |
| `gamesense_recommendation_catalog_items` / `_model_info` | Active catalog size and model metadata |

**In the cluster**, `monitoring/` is a Helm chart that installs Prometheus and Grafana in the app namespace. Prometheus discovers annotated backend pods (namespace-scoped RBAC only), and Grafana is provisioned with the *GameSense Application Metrics* dashboard: requests, catalog size, fallbacks, p95 latency, and HTTP rate by route.

```bash
kubectl -n gamesense create secret generic gamesense-grafana --from-literal=admin-password="$GRAFANA_PASSWORD"
helm upgrade --install gamesense-monitoring monitoring -n gamesense --wait
kubectl -n gamesense port-forward svc/gamesense-monitoring-prometheus 9090:9090   # /targets
kubectl -n gamesense port-forward svc/gamesense-monitoring-grafana 3001:3000
```

**Locally**, Compose runs the same dashboard against `monitoring/prometheus/prometheus.yml`.

## Data and attribution

Steam Store Games (Clean dataset) by Nik Davis on Kaggle, listed as CC BY 4.0; data described by the Kaggle page as Steam Store/SteamSpy-derived and gathered around May 2019.

Raw Kaggle data and generated model bundles are never committed. `.gitignore` blocks data, model, and artifact paths, and the [source manifest](data/source-manifests/kaggle.steam-store-games-clean.json) records provenance, licence, and accepted usage. The model is sparse TF-IDF plus tag/genre similarity fitted on catalog metadata, with no neural fine-tuning or user-behaviour training. Game artwork loads directly from Steam's public CDN by app ID; the app does not copy or proxy publisher images.

## Known issues and limitations

- **Demo-grade data layer:** PostgreSQL on EKS uses `emptyDir`, so data is lost when its pod is replaced. Production would use RDS or a persistent volume.
- **No TLS or DNS:** the app is served over plain HTTP on the AWS load balancer hostname, with no authentication. Production needs a domain, TLS, and auth.
- **Short-lived cluster:** the EKS environment exists only for the capstone demo and is destroyed afterwards, so the load balancer URL in the screenshots no longer resolves.
- **Data snapshot:** the catalog is a 2019 Kaggle snapshot, not live Steam data. *Trending* uses historical signals, not live trends. The EKS demo serves only a 100-game subset.
- **Recommender scope:** an untuned content-based baseline with no personalisation; accuracy has not been tuned against user behaviour.
- **Artwork:** best-effort Steam CDN URLs. Delisted or old games may show a title placeholder.
- **Private packages:** the GHCR images are private, so a cluster needs the `ghcr-pull` secret to pull them.
- **Saved games:** available through the API (GET/PUT/DELETE) but not yet exposed in the UI.

## Teardown

```bash
kubectl delete -f deploy/gitops/argocd-application.yaml            # removes the app resources
helm uninstall gamesense-monitoring -n gamesense
helm uninstall gamesense-ingress -n gamesense-ingress              # wait until its AWS load balancer is gone
terraform -chdir=terraform destroy
```

[Terraform destroy completion screenshot — 60 resources destroyed](demo/screenshots/M10-terraform-destroy.png).
