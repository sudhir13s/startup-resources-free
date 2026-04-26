# devops — 2026-04-26 ~12:00 IST

[PERSONA: devops | confidence: see per-finding]

## Blockers

- **B1 — Next.js MUST be Web Service, NOT Static Site** — confidence 9/10. Server components / `next/headers` / route handlers (`/api/*`) fail under Static Site export. Both services run as Web Services. Cost: two cold-starts (~30-60s each).
- **B2 — Render free-tier services don't share private network** — confidence 9/10. Frontend calls API via PUBLIC Render URL via `BACKEND_URL` env var. `localhost` will fail silently. Private Network is paid-only.

## Recommendations

- **R1 — Pin Python 3.12.3 + Node 20.12.2** — confidence 7/10. Render defaults drift. Pin in `render.yaml`.
- **R2 — `CORS_ORIGINS` = exact frontend Render URL** — confidence 7/10. No `*` even in v0.1.

## Observations

- **O1 — Free-tier cold start is the UX enemy** — confidence 5/10. 15-min idle spin-down. Document + curl-warm before demo.

## Assigned action

Set `BACKEND_URL` (frontend service) + `CORS_ORIGINS` (API service) in Render dashboard BEFORE first deploy. Both `sync: false` in `render.yaml` (no secrets in repo). Render names services predictably from `name:` field — derive `https://<name>.onrender.com` for both, write down, set both env vars, then trigger deploy.

## render.yaml

```yaml
services:
  - type: web
    name: startup-resources-api
    runtime: python
    plan: free
    buildCommand: pip install -r backend/requirements.txt
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: "3.12.3"
      - key: CORS_ORIGINS
        sync: false   # set in Render dashboard

  - type: web
    name: startup-resources-web
    runtime: node
    plan: free
    buildCommand: cd frontend && npm ci && npm run build
    startCommand: cd frontend && npm start
    envVars:
      - key: NODE_VERSION
        value: "20.12.2"
      - key: BACKEND_URL
        sync: false   # set in Render dashboard
      - key: NEXT_PUBLIC_APP_ENV
        value: production
```

## .github/workflows/ci.yml

```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
jobs:
  lint-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12.3" }
      - run: pip install ruff
      - run: ruff check backend/

  lint-and-build-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20.12.2"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint
      - run: cd frontend && npm run build
        env:
          BACKEND_URL: http://localhost:8000
          NEXT_PUBLIC_APP_ENV: ci
```

No deploy step — Render auto-deploys from `main` on push.

## Env-var matrix

| Service | Key | Where to set |
|---|---|---|
| API | `CORS_ORIGINS` | Render dashboard |
| API | `PYTHON_VERSION` | render.yaml |
| Web | `BACKEND_URL` | Render dashboard |
| Web | `NODE_VERSION` | render.yaml |
| Web | `NEXT_PUBLIC_APP_ENV` | render.yaml |

## Top risk

**Env-var circular dependency.** Derive both URLs from `name:` fields BEFORE deploy. Write down. Set both. Then deploy. Failure mode: deploy succeeds, all calls CORS-rejected.
