# Self-hosting pipepulse on Kubernetes

The Helm chart runs the full app (API, poller, dashboard, Postgres) against your own GitLab.
Images (`linux/amd64`, `linux/arm64`) and the chart are published to GHCR on every release, so
there is nothing to build. It's tested on k3s and, in CI, on kind; any cluster with an Ingress
controller works.

> The public demo doesn't use any of this: it's the dashboard alone on Vercel, serving a
> snapshot of generated data (see the root README).

```
your-host ─▶ Ingress ─┬─ /api/* ─▶ api (FastAPI)
                       └─ /*     ─▶ web (Next.js)
                          worker (polls GitLab) · postgres · migrate job (on every release)
```

## Quick look, no token

Demo mode seeds 6 projects with 60 days of generated history:

```bash
helm install pipepulse oci://ghcr.io/morveusz93/charts/pipepulse \
  -n pipepulse --create-namespace --set demo.enabled=true
```

The dashboard is served on `pipepulse.localhost` through your cluster's default IngressClass;
set `ingress.host` to something your cluster answers on. No cluster at hand? See
[Trying it locally](#trying-it-locally).

## Tracking your GitLab

### 1. Token

A token with the `read_api` scope, as a Secret created out of band (never in values files):

```bash
kubectl create namespace pipepulse
kubectl -n pipepulse create secret generic pipepulse-secrets --from-literal=gitlab-token='glpat-...'
```

### 2. Install

```bash
helm upgrade --install pipepulse oci://ghcr.io/morveusz93/charts/pipepulse -n pipepulse \
  --set secrets.existingSecret=pipepulse-secrets \
  --set gitlab.url=https://gitlab.com \
  --set ingress.host=pipepulse.example.com
```

Pin a version with `--version 0.2.0`; each chart version runs the images of the same version.

The worker picks up every project the token can see pipelines of within a couple of minutes
and backfills 30 days of history; `kubectl -n pipepulse logs -f deploy/pipepulse-worker` shows
its progress. To track only some, set e.g. `--set 'gitlab.projects={group/api,group/web}'`.
Projects you drop stop being polled and keep their history until deleted on the dashboard.

The dashboard has no login and job logs can contain sensitive output: restrict the Ingress
(e.g. an auth middleware or an internal-only host) rather than exposing it publicly.

### TLS

With [cert-manager](https://cert-manager.io) installed, apply `cluster/cluster-issuer.yaml`
(set your email first) and add
`--set ingress.tls.enabled=true,ingress.tls.clusterIssuer=letsencrypt`. Without it, terminate
TLS in front of the cluster. `helm show values oci://ghcr.io/morveusz93/charts/pipepulse` lists
the rest: resources, an external database, poll interval, Prometheus annotations.

## Trying it locally

[k3d](https://k3d.io) runs k3s in Docker:

```bash
k3d cluster create pipepulse -p "8088:80@loadbalancer"
helm install pipepulse oci://ghcr.io/morveusz93/charts/pipepulse \
  -n pipepulse --create-namespace --set demo.enabled=true --wait
open http://pipepulse.localhost:8088
```

Swap `--set demo.enabled=true` for `--set secrets.gitlabToken=glpat-... --set 'gitlab.projects={my-team/backend}'`
to point it at real projects.

## Your own images

To run a fork or unreleased changes, build and push both images, then point the chart at them:

```bash
docker build -t <registry>/pipepulse/api:<tag> api
docker build -t <registry>/pipepulse/web:<tag> web
docker push <registry>/pipepulse/api:<tag> && docker push <registry>/pipepulse/web:<tag>
helm upgrade --install pipepulse helm/pipepulse -n pipepulse \
  --set image.repository=<registry>/pipepulse --set image.tag=<tag> ...
```

Every push to `main` also publishes `ghcr.io/morveusz93/pipepulse/{api,web}:main`.
