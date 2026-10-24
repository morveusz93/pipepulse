# pipepulse web

Next.js dashboard for pipepulse. See the repository root README.

```bash
npm install
npm run dev        # http://localhost:3000, expects the API on :8000
```

`PIPEPULSE_API_URL` points server-side rendering and the `/api` rewrite at the backend
(default `http://localhost:8000`). Append `?theme=light` or `?theme=dark` to any URL to force a theme.
