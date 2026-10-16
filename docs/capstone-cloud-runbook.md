# Temporary AWS capstone run

Use the rubric in the parent workspace as the submission authority. Current execution evidence lives outside this Git repository in `submission-evidence/2026-10-16/`; distinguish captured results from these instructions.

## Infrastructure

Use a short-lived AWS login and verify `aws sts get-caller-identity` before planning. Set `allowed_account_ids` to the authorized account, select the region, and verify the Kubernetes version is under standard support in that region. The chart supports EKS 1.35 on AL2023 worker images. AWS credits do not remove the need to monitor costs and destroy resources after the demo.

Run Terraform init, format check, validate, and a saved plan before applying. Keep state and saved plans private. The optional `create_demo_registry` variable creates two private, immutable-tag ECR repositories for temporary image staging when the GHCR packages cannot be pulled. These repositories use `force_delete` so Terraform teardown removes their demo images. GHCR remains the required CI publish target.

## Application

Apply `k8s/namespace.yaml`. Create `gamesense-database` with `POSTGRES_PASSWORD` and the matching SQLAlchemy `DATABASE_URL` pointing at `gamesense-postgres:5432/gamesense`. Generate the password locally and avoid printing or committing it. Apply `k8s/postgres-demo.yaml`; this database is shared by the two backend replicas but is deliberately disposable (`emptyDir`). Wait for PostgreSQL and complete an Alembic migration using the selected backend image before launching both replicas.

Install an ingress controller and select its class in Helm. For the temporary Traefik demo, use the official chart with Kubernetes Ingress enabled; the application chart supports an empty `ingress.host` so a temporary load-balancer hostname can serve the app without purchasing DNS. Clear ALB annotations when choosing Traefik. Scope load-balancer sources to the demo operator where practical. The temporary HTTP fixture demo contains no personal or private catalog data; public production use requires authentication, durable storage, DNS, and TLS.

Deploy SHA-tagged frontend/backend images using `helm upgrade --install gamesense helm -n gamesense --wait`, with image registry/repository/tag overrides for the chosen registry, `backend.database.urlSecretName=gamesense-database`, and two replicas per app. The fixture catalog is the default. The 2026-10-16 demo instead served a 100-game subset of the private Kaggle bundle (the most-owned titles), loaded at the operator's direction from a `gamesense-content-bundle` ConfigMap created outside Git. That puts it on the temporary cluster, beyond the bundle's recorded local-use scope. The full bundle was not uploaded, and the ConfigMap is deleted at teardown.

## GitOps with Argo CD

Argo CD deploys `deploy/gitops/argocd-application.yaml`: the chart from `main`, with `helm/values-eks.yaml` layered on top. On each push to `main`, CI publishes SHA-tagged GHCR images and then commits those tags to `values-eks.yaml`. Argo CD detects the commit and syncs automatically. Create these outside Git first: an Argo CD repository Secret holding a read-only token, a `ghcr-pull` docker-registry Secret holding a `read:packages` token in the `gamesense` namespace, and the `gamesense-content-bundle` ConfigMap. Install Argo CD from a pinned release manifest. Use either Helm or Argo CD for ongoing changes to the release, never both.

Install the [monitoring chart](../monitoring/README.md), generate actual recommendation requests, and collect pod, Service, Helm release, Ingress, metrics, Prometheus UP, and populated Grafana screenshots.

## Demonstration and cleanup

For the final demonstration, commit a small visible app change, push to main, show the resulting successful Actions run and SHA-tagged GHCR images, deploy that exact revision, and show the updated app. A recorded walkthrough must show the actual sequence; still images alone do not satisfy the recorded/live presentation requirement.

Before Terraform destroy, uninstall the ingress controller and wait for its AWS load balancer to disappear. Uninstall application and monitoring releases. Destroy the saved demo infrastructure with the same account and variables. Capture the destroy completion and verify no cluster, tagged VPC/NAT, EC2 workers, ECR repositories, or load balancers from the run remain. KMS deletion may remain scheduled according to AWS's mandatory waiting period; report that explicitly if present.
