# pipepulse

**Pipeline health dashboard for GitLab.**

Monitor multiple GitLab projects from a single view — with history, trends, and inline failure logs.

![status](https://img.shields.io/badge/status-in%20development-amber)

---

## Why

Most CI dashboards show only the current state. pipepulse stores pipeline history in Postgres and surfaces:

- **Trends** — is your build getting slower? fail rate rising over 7/30 days?
- **MTTR** — time between a failure and the next success on the same branch
- **Inline failure logs** — expand a failed job's last N lines without leaving the dashboard
- **Pulse** — a per-project EKG-style sparkline of the last 20 runs (color = result, height = duration)

Inspired by [larscom/gitlab-ci-dashboard](https://github.com/larscom/gitlab-ci-dashboard) and [ci-dashboard/gitlab-ci-dashboard](https://github.com/ci-dashboard/gitlab-ci-dashboard). pipepulse adds persistent history, trend analytics, and a premium-grade UI.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · APScheduler |
| Database | PostgreSQL |
| Frontend | Next.js · TypeScript · Recharts |
| Infra | Docker · Helm · GitLab CI |
| Demo | k3s VPS · `pipepulse.morv.dev` |

---

## Features (MVP)

- Connect multiple GitLab projects via API token (`read_api` scope, stored encrypted)
- Aggregate pipeline stats: count, success/fail rate, avg duration
- Per-project view: trend chart, fail rate, MTTR
- List of recent failures with inline job log preview
- Filter/sort (e.g. failed only, by project, by date)
- **Demo mode** — works out of the box with seed data, no token required

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
- [ ] Repo structure, docker-compose (api + postgres)
- [ ] GitLab API client (projects, pipelines, jobs, trace)
- [ ] Data model + migrations
- [ ] Background polling service
- [ ] API endpoints: projects, pipelines, aggregates, job log
- [ ] Token encryption (Fernet)
- [ ] Seed data for demo mode
- [ ] Frontend: design tokens, dark/light theme
- [ ] Pulse component
- [ ] Summary bar + project list
- [ ] Per-project view (trend chart, fail rate, MTTR)
- [ ] Inline log viewer, filters/sorting
- [ ] Dockerfiles + Helm chart
- [ ] GitLab CI pipeline (pipepulse monitors itself)
- [ ] Live deploy to `pipepulse.morv.dev`
- [ ] Prometheus metrics (optional)

---

## Local development

> Coming soon — docker-compose setup will be the entry point.

---

## License

MIT
