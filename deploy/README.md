# Self-hosting pipepulse on Kubernetes

The Helm chart in `helm/pipepulse` runs the full app (API, poller, dashboard, Postgres) against
your own GitLab. It's tested on k3s; any cluster with an Ingress controller works.

> The public demo doesn't use any of this: it's the dashboard alone on Vercel, serving a
> snapshot of generated data (see the root README).

```
your-host ─▶ Ingress ─┬─ /api/* ─▶ api (FastAPI)
                       └─ /*     ─▶ web (Next.js)
                          worker (polls GitLab) · postgres · migrate job (on every release)
```

## 1. Images

Build and push both images to a registry your cluster can pull from:

```bash
docker build -t <registry>/pipepulse/api:<tag> api
docker build -t <registry>/pipepulse/web:<tag> web
docker push <registry>/pipepulse/api:<tag> && docker push <registry>/pipepulse/web:<tag>
```

## 2. GitLab token

A token with the `read_api` scope, as a Secret created out of band (never in values files):

```bash
kubectl create namespace pipepulse
kubectl -n pipepulse create secret generic pipepulse-secrets --from-literal=gitlab-token='glpat-...'
```

## 3. Install

```bash
helm upgrade --install pipepulse helm/pipepulse -n pipepulse \
  --set image.repository=<registry>/pipepulse --set image.tag=<tag> \
  --set secrets.existingSecret=pipepulse-secrets \
  --set gitlab.url=https://gitlab.com \
  --set ingress.host=pipepulse.example.com
```

The worker picks up every project the token can see pipelines of within a couple of minutes
and backfills 30 days of history; `kubectl -n pipepulse logs -f deploy/pipepulse-worker` shows
its progress. To track only some, set e.g. `--set 'gitlab.projects={group/api,group/web}'`.
Projects you drop stop being polled and keep their history until deleted on the dashboard.

The dashboard has no login and job logs can contain sensitive output: restrict the Ingress
(e.g. an auth middleware or an internal-only host) rather than exposing it publicly.

TLS: with [cert-manager](https://cert-manager.io) installed, apply `cluster/cluster-issuer.yaml`
(set your email first) and keep `ingress.tls.clusterIssuer: letsencrypt`. Otherwise set
`ingress.tls.enabled=false` and terminate TLS elsewhere. See `helm/pipepulse/values.yaml` for
resources, external databases and the rest.

## Trying it locally

[k3d](https://k3d.io) runs k3s in Docker:

```bash
docker compose build
docker tag pipepulse-api localhost/pipepulse/api:dev && docker tag pipepulse-web localhost/pipepulse/web:dev
k3d cluster create pipepulse -p "8088:80@loadbalancer"
k3d image import localhost/pipepulse/api:dev localhost/pipepulse/web:dev -c pipepulse
helm install pp helm/pipepulse -n pipepulse --create-namespace \
  --set image.repository=localhost/pipepulse,image.tag=dev,image.pullPolicy=Never \
  --set ingress.host=pipepulse.localhost,ingress.tls.enabled=false \
  --set secrets.gitlabToken=glpat-... --set 'gitlab.projects={my-team/backend}' --wait
open http://pipepulse.localhost:8088
```
