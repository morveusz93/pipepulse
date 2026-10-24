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

## 2. Secrets

Tokens are encrypted with a Fernet key; the admin password protects connection management.
Create both out of band, never in values files:

```bash
kubectl create namespace pipepulse
kubectl -n pipepulse create secret generic pipepulse-secrets \
  --from-literal=encryption-key="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  --from-literal=admin-password='<choose one>'
```

## 3. Install

```bash
helm upgrade --install pipepulse helm/pipepulse -n pipepulse \
  --set image.repository=<registry>/pipepulse --set image.tag=<tag> \
  --set demo.enabled=false --set secrets.existingSecret=pipepulse-secrets \
  --set ingress.host=pipepulse.example.com
```

Then log in, add a GitLab connection with a `read_api` token and pick projects; the worker
backfills their history on its next cycle.

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
  --set ingress.host=pipepulse.localhost,ingress.tls.enabled=false --wait
open http://pipepulse.localhost:8088
```

That installs the demo variant (generated data, nightly reseed); add the flags from step 3 for
a real setup.
