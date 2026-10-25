# pipepulse

**Pipeline health dashboard for GitLab™.**

<sub>GITLAB is a trademark of GitLab Inc. in the United States and other countries and regions. pipepulse is an independent project, not affiliated with, endorsed, sponsored or approved by GitLab Inc.</sub>

Monitor multiple GitLab projects from a single view — with history, trends, and inline failure logs.

[![demo](https://img.shields.io/badge/demo-live-2ea44f)](https://pipepulse.morv.dev)
[![CI](https://github.com/morveusz93/pipepulse/actions/workflows/ci.yml/badge.svg)](https://github.com/morveusz93/pipepulse/actions/workflows/ci.yml)

**Live demo: [pipepulse.morv.dev](https://pipepulse.morv.dev)** (generated sample data, no GitLab token needed)

![Dashboard: summary, project list with pulse bars, and an active failure expanded inline to its job log](docs/dashboard.png)

<details>
<summary>Project view and light theme</summary>

![Project view: stats vs the previous window, duration and runs-per-day trends, incident history](docs/project.png)

![Dashboard in the light theme](docs/dashboard-light.png)

</details>

---

## Why

Most CI dashboards show only the current state. pipepulse stores pipeline history in Postgres and surfaces:

- **Trends** — is your build getting slower? fail rate rising? Compared with the previous 7/30/90 days
- **MTTR** — time from a failure on the default branch to the next green pipeline, with incident history
- **Inline failure logs** — expand a failed job's last N lines without leaving the dashboard
- **Pulse** — a per-project EKG-style strip of the last 20 runs: failures spike, passing runs are sized by duration

Inspired by [larscom/gitlab-ci-dashboard](https://github.com/larscom/gitlab-ci-dashboard) and [ci-dashboard/gitlab-ci-dashboard](https://github.com/ci-dashboard/gitlab-ci-dashboard). pipepulse adds persistent history, trend analytics, and a premium-grade UI.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · async background worker |
| Database | PostgreSQL |
| Frontend | Next.js · TypeScript · Recharts |
| Infra | Docker · Helm (k3s) · GitHub Actions |
| Demo | Vercel (dashboard only, snapshot data) · `pipepulse.morv.dev` |

---

## Features (MVP)

- Track GitLab projects (gitlab.com or self-managed) with just a `read_api` token: every accessible project by default, or a chosen list
- Aggregate pipeline stats: runs, success rate, avg and p90 duration
- Per-project view: trend chart, fail rate, MTTR
- Inline job logs (ANSI colors, GitLab sections) under active failures and failed pipelines
- Filter and sort pipelines by status, ref (default branch or all) and source; slowest first
- **Demo mode** — works out of the box with generated data, no token required

---

## Design

- Monospace font for data (numbers, durations, SHAs, timestamps) — sans for labels and nav
- Color carries meaning: teal = success · coral = failure · amber = running
- Dense list layout (not cards) — more dashboard, less landing page
- Signature element: **pulse bar** — a row of thin stripes per project, each stripe = one pipeline run
- Light/dark theme (dark by default); keyboard-accessible; `prefers-reduced-motion` respected

```
┌─────────────────────────────────────────────────────────────────┐
│  Projects: 6   Active failures: 2   Avg build: 4m 12s   ✓ 94%  │
├────────────────┬──────────────────────┬────────────┬────────────┤
│ Project        │ Pulse (last 20)      │ Status     │ Duration   │
├────────────────┼──────────────────────┼────────────┼────────────┤
│ api-service    │ ▁▃▂█▂▁▃▂▁▁▂▃▁▂█▂▁▃▂▁│ ✓ success  │ 3m 48s     │
│ web-frontend   │ ▂▁▃█▁▂▃▁▂▃▁▂▁▃▁▂▁▃▁▂│ ✗ failed   │ 6m 02s     │  ← expanded
│   └─ test:e2e  │ Error: Cannot find module './auth' ...         │
│ infra-deploy   │ ▁▁▂▁▃▁▁▂▁▃▁▁▂▁▁▃▁▁▂▁│ ✓ success  │ 1m 15s     │
└────────────────┴──────────────────────┴────────────┴────────────┘
```

---

## Roadmap

- [x] Project spec & architecture decisions
- [x] Repo structure, docker-compose (api + postgres)
- [x] GitLab API client (projects, pipelines, jobs, trace)
- [x] Data model + migrations
- [x] Background polling service
- [x] API endpoints: projects, pipelines, aggregates, job log
- [x] Seed data for demo mode
- [x] Frontend: design tokens, dark/light theme
- [x] Pulse component
- [x] Summary bar + project list
- [x] Per-project view (trend chart, fail rate, MTTR)
- [x] Inline log viewer
- [x] Pipeline filters, sorting, pagination
- [x] Configuration through environment variables (token, optional project list)
- [x] Dockerfiles + Helm chart (tested on a local k3s cluster)
- [x] CI (GitHub Actions)
- [x] Frontend-only demo mode (snapshot of the real API)
- [x] Live demo on [pipepulse.morv.dev](https://pipepulse.morv.dev)
- [x] Prometheus metrics

---

## Demo

The [public demo](https://pipepulse.morv.dev) is the dashboard alone, deployed on Vercel with `PIPEPULSE_DEMO=true`. It needs
no backend or database: it serves `web/src/demo/snapshot.json`, a snapshot recorded from the
real API on generated data (6 projects, 60 days of history). Timestamps are shifted to "now" on
every request, so the demo never looks stale.

Regenerate the snapshot after changing the API or the demo data:

```bash
docker compose up -d postgres migrate
cd api && uv run python -m pipepulse.seed.snapshot ../web/src/demo/snapshot.json
```

To run pipepulse for real against your GitLab, use docker-compose (below) or the
[Kubernetes guide](deploy/README.md).

## Local development

Prerequisites: [Docker](https://docs.docker.com/engine/install/) with the Compose plugin. For working on the API outside containers also [uv](https://docs.astral.sh/uv/). Postgres runs in Docker, so you don't need to install it locally.

```bash
cp .env.example .env
docker compose up --build        # everything: dashboard on :3000, API on :8000
open http://localhost:3000
```

API without Docker (needs a reachable Postgres, see `PIPEPULSE_DATABASE_URL`):

```bash
cd api
uv sync
uv run alembic upgrade head
uv run uvicorn pipepulse.main:app --reload
uv run pytest
```

Dashboard (Next.js, needs the API running):

```bash
cd web
npm install
npm run dev                      # http://localhost:3000
npm test                         # unit tests (ANSI log parser, formatting)
```

DB-backed tests use a separate database. Create it once and they'll run against it, otherwise they're skipped:

```bash
docker compose exec postgres psql -U pipepulse -c 'CREATE DATABASE pipepulse_test'
```

### Tracking your own GitLab projects

1. Create an access token in GitLab (**Edit profile → Access tokens**) with the **`read_api`** scope.
2. In `.env`:
   ```bash
   PIPEPULSE_GITLAB_URL=https://gitlab.com          # or your self-managed instance
   PIPEPULSE_GITLAB_TOKEN=glpat-...
   PIPEPULSE_PROJECTS=my-team/backend, my-team/frontend   # optional
   ```
   Leave `PIPEPULSE_PROJECTS` empty to track every project the token can see pipelines of
   (Reporter access and up, not archived, CI enabled). To pick projects, list their paths from
   the GitLab URL: `https://gitlab.com/my-team/backend` → `my-team/backend` (subgroups
   included, e.g. `my-team/apps/mobile`).
3. `docker compose up --build -d` and open http://localhost:3000.

The worker checks the token's scopes at startup, then every 2 minutes picks up new projects
(backfilling 30 days of history) and syncs pipelines and failed job logs. Follow it with
`docker compose logs -f worker`. Changing `.env` needs `docker compose up -d` to take effect.

A project that's no longer configured (or no longer accessible) isn't deleted: it stops being
polled and moves to a "Removed from configuration" section on the dashboard, history intact.
Configure it again and it resumes; or delete it there, confirming with its path, to drop its
history for good.

The dashboard has no login, and job logs can contain sensitive output: keep it on a private
network, or put it behind your reverse proxy's authentication.

API docs: http://localhost:8000/api/docs

### Prometheus metrics

`GET /metrics` on the API (port 8000, deliberately not under `/api`, so the dashboard's
public routes never expose it) serves per-project gauges computed from the stored history:
`pipepulse_project_failing`, `_running_pipelines`, `_pipelines{status}`, `_success_ratio`,
`_duration_avg_seconds`, `_duration_p90_seconds`, `_mttr_median_seconds` (default branches,
7-day window, `?days=` to change) and `_last_polled_timestamp_seconds`, which makes a good
staleness alert, e.g. `time() - pipepulse_project_last_polled_timestamp_seconds > 900`.
The Helm chart annotates the API pods for annotation-based scraping.

Repo layout: `api/` (FastAPI + poller), `web/` (Next.js dashboard), `deploy/` (Helm chart and [self-hosting guide](deploy/README.md)).

---

## License

MIT
