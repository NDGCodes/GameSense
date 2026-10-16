# M8 Final Local Evidence Freeze and Claim Audit

M8 is a local/static evidence freeze. It does not download or ingest real Steam/Kaggle data, train or fine-tune models, tune recommendation accuracy, provision AWS resources, or verify a live deployment. All executable local recommender evidence uses the committed self-authored fixture data.

## Evidence bundle

Evidence artifacts were captured outside the worktree in the private `gamesense-ml-m8-evidence/` firstmate task directory from commit `492d3c6e2d4002e5ef1101e6d68b8310ee9e3ff6`.

Commands below record that historical checkout, including its former infrastructure paths. Use the [README validation commands](../README.md#validation-commands) for the current layout and the [local rubric evidence index](local-rubric-evidence.md) for later evidence.

Tool versions recorded in `tool-versions.txt`:

- Python: 3.10.13 (`~/.pyenv/versions/3.10.13/bin/python`)
- Node.js: v25.6.1
- npm: 11.9.0
- Docker: 29.8.2
- Docker Compose: v5.5.1
- Helm: v4.3.0
- Terraform: v1.16.5 on `darwin_arm64`

| Check | Command | Evidence | Result |
| --- | --- | --- | --- |
| Backend tests | `cd backend && PYTHONPATH=. pytest -q` in a Python 3.10.13 venv with `requirements.txt` and `requirements-dev.txt` installed | `backend-pytest.txt`, `pip-install.log` | Passed: 26 tests, 1 Starlette/httpx deprecation warning |
| Frontend build | `cd frontend && npm ci && npm run build` | `npm-ci.log`, `frontend-build.txt` | Passed |
| Compose config | `docker compose config --quiet` | `compose-config.txt` | Passed; command produced no output |
| Compose content smoke | `docker compose --profile content-smoke run --rm content-smoke` | `compose-content-smoke.txt` | Passed: `content recommender smoke passed` |
| Helm lint | `helm lint deploy/helm/gamesense` | `helm-lint.txt` | Passed: 1 chart linted, 0 failed |
| Helm default render | `helm template gamesense deploy/helm/gamesense` | `helm-template-default.yaml` | Passed render; default chart keeps fixture recommender mode |
| Helm content render | `helm template gamesense-content deploy/helm/gamesense --set backend.recommender.mode=content` | `helm-template-content.yaml` | Passed render; content mode mounts the committed self-authored fixture artifact |
| Terraform fmt | `terraform -chdir=infra/terraform fmt -check -recursive` | `terraform-fmt.txt` | Passed; command produced no output |
| Terraform init | `terraform -chdir=infra/terraform init -backend=false` | `terraform-init.txt` | Passed; reused locked providers/modules |
| Terraform validate | `terraform -chdir=infra/terraform validate` | `terraform-validate.txt` | Passed: configuration is valid |

Docker resources were available for the Compose static check and content-smoke run. No `terraform plan`, `terraform apply`, AWS, Kubernetes, real-data, training, fine-tuning, or accuracy-tuning command was run.

## Supported local Python evidence

Local backend validation is evidenced with Python 3.10.13. Python 3.11 is the development target used by `backend/Dockerfile` and `.github/workflows/ci.yml`, but this M8 evidence bundle did not run a Python 3.11 interpreter in this worktree. See [local development](../README.md#local-development) for prerequisites. Python 3.14 behavior is not diagnosed here; any earlier Python 3.14 failure cause remains unverified and is not claimed.

## Claim ledger

| Source claim | M8 disposition |
| --- | --- |
| GameSense is a local app/database/recommender infrastructure foundation using tiny hand-written demo fixtures. | Verified by backend tests, frontend build, Compose config/content smoke, and fixture-only documentation. |
| Repository does not include real Steam dataset acquisition, generated recommendation data, model training, or model serving. | Verified by scope audit and unchanged local-only fixture paths; no real-data or model-training command was run. |
| Frontend, backend, Compose, Terraform, Helm/GitOps, and observability directories exist as the architecture surface. | Verified by repository structure and static validations for Compose, Helm, and Terraform. |
| Backend API, migration, catalog, ML pipeline, evaluation, and recommender tests can run locally. | Verified by `backend-pytest.txt` with 26 passing tests. |
| Frontend can build locally. | Verified by `frontend-build.txt`. |
| Docker Compose configuration is syntactically valid and content-smoke can exercise the committed content fixture when Docker is available. | Verified by `compose-config.txt` and `compose-content-smoke.txt`. |
| Helm chart lints and renders default/content configurations. | Verified by `helm-lint.txt`, `helm-template-default.yaml`, and `helm-template-content.yaml`. |
| Terraform configuration is formatted, initializes without backend, and validates statically. | Verified by `terraform-fmt.txt`, `terraform-init.txt`, and `terraform-validate.txt`; no cloud plan/apply is claimed. |
| Prometheus/Grafana dashboards and scrape configs are local development assets. | Non-claim for live monitoring; M8 did not verify a deployed Prometheus/Grafana environment. |
| GitHub Actions, GHCR publishing, AWS/EKS, Argo CD, Kubernetes health, DNS/TLS, and production monitoring evidence. | Explicit non-claims for M8; require later external setup and authorization. |
| Kaggle-compatible notebook path exists for later phases. | Static/local-only claim only; M8 did not download Kaggle data, run real-data training, fine-tune, or prove real-catalog accuracy. |
| Python 3.14 failure cause. | Unverified; no root cause is claimed. |
