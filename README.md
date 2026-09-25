# ResourceOS

**Every free tier, startup credit and grant worth knowing — in one filterable dashboard.**

ResourceOS tracks free and discounted offers across cloud, GPUs, AI APIs, databases, storage,
auth, startup credits, grants and accelerators. Filter by project stage (hobby → Series A),
category and region, open any offer for exactly what's free, and refresh the data on demand
using free AI services only. **India-first**: programs open to Indian founders are surfaced by default.

- **Live:** <https://startup-resources.onrender.com>
- **How it works:** [architecture notes](architecture/architecture-notes.md)

---

## Quick start

```bash
git clone https://github.com/sudhir13s/startup-resources-free.git
cd startup-resources-free

# API on :8000 (Python 3.12, uv shown)
uv venv --python 3.12
uv pip install -r requirements-dev.txt
uv run python -m api

# Dashboard on :3000 (second terminal)
npm --prefix frontend install
BACKEND_URL=http://localhost:8000 npm --prefix frontend run dev
```

Open <http://localhost:3000>. The API creates `data/resourceos.db` and loads the catalog from
`data/providers_seed.json` on first boot. No keys are needed to browse; they are only needed for
**Refresh**.

---

## Prerequisites

- **Python 3.12** — any 3.12 environment works. Reusing a shared environment? Install only the
  packages it lacks: `requirements-dev.txt` pins exact versions.
- **Node.js 20+**
- **Optional:** free LLM and search API keys, only for refreshing data (see below).

---

## Development

```bash
uv run python -m pytest                 # tests
uv run python -m ruff check .           # lint
npm --prefix frontend run build         # frontend production build

# Refresh data locally without the UI
uv run python -m refresh run --db data/resourceos.db --seed data/providers_seed.json
```

**CI is manual** — it never runs on push or PR:

```bash
gh workflow run ci.yml --ref <branch>
gh run watch
```

Or GitHub → **Actions** → **CI** → **Run workflow**.

---

## Deploy on Render

`render.yaml` defines two free web services: `startup-resources-api` (FastAPI) and
`startup-resources` (Next.js). Deploy with **New → Blueprint → this repository**, then set the
variables below in each service's **Environment** tab. Service-to-service URLs are wired automatically.

Render's free disk is temporary, so the database is saved to a Cloudflare R2 bucket after each
refresh and restored on every boot. Free services sleep after 15 idle minutes (first request
takes 30–60 s).

| Variable | Service | Needed for | Value |
|---|---|---|---|
| `RESOURCEOS_PASSPHRASE` | API **and** frontend (same value) | Refresh button | Any long random string, e.g. `openssl rand -hex 24` |
| `RESOURCEOS_R2_ENDPOINT` | API | Keeping data across restarts | S3 endpoint from the R2 overview page, `https://<account-id>.r2.cloudflarestorage.com` |
| `RESOURCEOS_R2_BUCKET` | API | Keeping data across restarts | R2 bucket name, e.g. `resourceos-data` |
| `RESOURCEOS_R2_ACCESS_KEY_ID` | API | Keeping data across restarts | R2 API token access key |
| `RESOURCEOS_R2_SECRET_ACCESS_KEY` | API | Keeping data across restarts | R2 API token secret |
| `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `CEREBRAS_API_KEY`, `MISTRAL_API_KEY`, `SAMBANOVA_API_KEY`, `NVIDIA_API_KEY`, `TOGETHER_API_KEY`, `HF_TOKEN` | API | Refresh (AI extraction) | Free-tier keys; any subset works, more keys = more free quota |
| `TAVILY_API_KEY`, `EXA_API_KEY`, `JINA_API_KEY`, `LINKUP_API_KEY`, `SERPAPI_API_KEY` | API | Discovering new providers | Free-tier keys; optional |

**Create the R2 bucket:**

1. Cloudflare dashboard → **Storage & databases → R2 object storage** → activate R2 (checkout
   needs a card; the free tier costs $0).
2. **Overview → Create bucket** (e.g. `resourceos-data`).
3. **Overview → Account Details → API Tokens: Manage → Create User API token** with
   **Object Read & Write**, applied to that bucket only.
4. Copy the **Access Key ID**, **Secret Access Key** (shown once) and the **S3 endpoint** into
   the four variables above.

Optional overrides (defaults work on Render): `RESOURCEOS_R2_OBJECT_KEY` (default
`resourceos.db`), `RESOURCEOS_DB_PATH`, `SEED_PATH`, `CORS_ORIGINS`. For local runs, copy
`.env.example`.

**First refresh:** open the dashboard → **Refresh data** → enter the passphrase → follow the
**Runs** page. The first successful run writes the object into the R2 bucket.

---

## License

[MIT](LICENSE).
