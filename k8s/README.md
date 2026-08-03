# NOVA — Kubernetes Deployment

The Helm chart at [`../helm/NOVA`](../helm/NOVA) is the source of
truth for every Kubernetes resource NOVA needs. This directory holds
**generated reference output only** — plain `kubectl apply`-able YAML,
for anyone who wants to see (or diff, or `kubectl apply -f` directly
without installing Helm) exactly what the chart produces with default
values.

## `rendered/all-resources.yaml`

Generated with:

```bash
helm template NOVA helm/NOVA --namespace NOVA > k8s/rendered/all-resources.yaml
```

Regenerate it after any chart change — it is not kept in sync
automatically, and a stale copy is worse than no copy, so treat a diff
here as a signal to re-run the command above before trusting it.

Applying it directly (no Helm required, e.g. via a raw `kubectl apply -k`
GitOps pipeline) works, but loses everything Helm hooks provide —
specifically, **the `pre-install`/`pre-upgrade` migration Job
(`alembic upgrade head`) will run as an ordinary Job at the same time as
everything else**, not before it. Either apply
`rendered/all-resources.yaml` in two passes (Job first, then everything
else once it completes), or use `helm install`/`helm upgrade` instead,
which sequences this correctly on its own.

## What's actually in it

| Resource | Count | Notes |
|---|---|---|
| `StatefulSet` | 2 | Postgres, Redis — each with a `volumeClaimTemplate` |
| `Deployment` | 6 | api, frontend, worker-critical, worker-default, beat, flower |
| `Service` | 5 | api, frontend, flower (ClusterIP) + postgres, redis (headless) |
| `HorizontalPodAutoscaler` | 2 | api, worker-default — see the chart's `values.yaml` comments for why worker-critical and beat are deliberately excluded |
| `PersistentVolumeClaim` | 1–2 | shared `uploads` (always), `reports` (only if `storage.reports.emptyDir=false`) |
| `Ingress` | 1 | routes `/` to frontend, `/api` to the API |
| `ConfigMap` / `Secret` | 1 each | non-secret vs. secret app config — see `values.yaml`'s `config`/`secrets` blocks |
| `Job` | 1 | `alembic upgrade head`, as a Helm hook |
| `PodDisruptionBudget` | 1 | api |
| `Pod` (helm test) | 1 | `helm test` hook — hits `/health/ready` |

## Verifying it for real

This was actually deployed to a throwaway `kind` cluster during
development (`kind create cluster`, then `helm install`), not just
`helm template`-rendered and eyeballed — see the PR/commit history for
the exact verification steps.
