# M10 Walkthrough Plan

Use this file as the evidence checklist while recording the final submission. Do not mark items complete until verified in the target environment.

1. Codebase tour: show `frontend/`, `backend/`, `infra/terraform/`, `deploy/helm/`, `deploy/gitops/`, `observability/`, and this `submission/` folder.
2. CI/CD: push a feature branch to GitHub and show Actions running end-to-end.
3. Terraform: run `terraform plan`, then show the AWS Console VPC, two public subnets, and EKS managed node group after apply.
4. Argo CD: install/configure Argo CD, apply `deploy/gitops/argocd-application.yaml`, and show the GameSense app synced.
5. Kubernetes: show healthy pods, services, and ingress in the `gamesense` namespace.
6. Prometheus: show the deployed backend target as `UP`.
7. Grafana: show the GameSense dashboard populated with live request and latency metrics.
8. Submission assets: record the video, add slide links, and reference only real evidence.

External prerequisites: AWS credentials and permissions, container registry, GitHub repository secrets, DNS/ingress configuration, kubectl context, Helm, Terraform, and Argo CD access.
