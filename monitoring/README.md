# GameSense cluster monitoring

This directory is also a Helm chart. It installs namespace-scoped Prometheus and Grafana, reusing the dashboard under `grafana/dashboards/`. Compose continues to use the existing local provisioning files.

Create a `gamesense-grafana` Secret with an `admin-password` key outside Git, then deploy:

```sh
helm upgrade --install gamesense-monitoring monitoring --namespace gamesense --wait
kubectl -n gamesense port-forward svc/gamesense-monitoring-prometheus 9090:9090
kubectl -n gamesense port-forward svc/gamesense-monitoring-grafana 3001:3000
```

Prometheus discovers annotated running backend pods only in the release namespace. Its ServiceAccount can get/list/watch pods in that namespace; no cluster-wide role is granted. Grafana uses the in-cluster Prometheus Service and provisions the GameSense dashboard. Both Services are ClusterIP; use local port forwards for evidence.

The demo retains six hours of metrics and uses `emptyDir`. Pod replacement removes history. This is capstone evidence infrastructure, not durable production monitoring. Generate recommendation traffic before inspecting the dashboard and wait for at least two scrapes for rate panels. Save the Targets page showing each backend pod UP and a dashboard with actual populated panels.

```sh
helm lint monitoring
helm template gamesense-monitoring monitoring --namespace gamesense
```
