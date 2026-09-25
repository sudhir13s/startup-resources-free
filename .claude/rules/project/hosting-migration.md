# Project Rule: Hosting Migration Plan

> Locked migration spec for moving off Render free tier when triggers hit. Oracle Cloud Always Free Mumbai is primary; fallback ladder defined for if Oracle's signup / reclamation / ARM-only constraints bite.
>
> **NOT in v0.1 / v0.2 / v0.3 scope.** Build only when triggers hit.

## Switch triggers (any one fires the migration)

1. **Cold start kills demo UX** — public-share happens, real users complain about 30–60s first hit.
2. **750 hr/mo cap** — both services need always-on for >31 days (paid users emerge).
3. **India latency required** — Indian users complain about US/EU/SG-only Render regions (~150ms RTT vs ~10ms from Mumbai).
4. **Postgres 90-day expiry hits** — when v0.2 SQLite → Postgres migration lands and we need permanent persistence (Render free Postgres dies after 90 days).
5. **Long refresh runs** — a `refresh/runner.py` run, triggered in-process, exceeds Render's free-instance runtime budget for a single request.
6. **Commercial use** — project goes monetized (Render free still works but Vercel-style ToS doesn't apply; this trigger is informational).

Until ANY of these fires, stay on Render. Don't migrate prematurely.

---

## Primary: Oracle Cloud Always Free (Mumbai region)

### Why
- **Truly always-free** — no trial expiry, no CC charge.
- **Mumbai (ap-mumbai-1) region available** — India-primary win.
- **4 ARM cores + 24 GB RAM + 200 GB block + 10 TB egress/month** total free quota.
- One Ampere A1 ARM VM trivially runs FastAPI + Next.js + SQLite + Caddy + scrapers + cron.
- No sleep, no cold start, persistent disk.

### Architecture
Single VM (`VM.Standard.A1.Flex`, 2 OCPU + 12 GB RAM — fits in always-free):

```
┌─────────────────────────────────────────┐
│ Ubuntu 24.04 ARM, Mumbai region         │
│                                         │
│  Caddy (TLS auto, reverse proxy)        │
│    ├─ resourceos.<your-domain>          │
│    │     └─> :3000 (Next.js)            │
│    └─ api.resourceos.<your-domain>      │
│          └─> :8000 (FastAPI / uvicorn)  │
│                                         │
│  systemd units                          │
│    ├─ resourceos-web.service (Next.js)  │
│    └─ resourceos-api.service (uvicorn)  │
│         (refresh stays button-triggered,│
│          in-process — no timer unit)    │
│                                         │
│  /var/lib/resourceos/                   │
│    ├─ data/providers_seed.json          │
│    └─ resourceos.db (SQLite, mirrors    │
│         the `data` git branch)          │
└─────────────────────────────────────────┘
```

### Setup runbook (~1 hr first time)

1. **Oracle account** — oracle.com/cloud/free. CC required for verification; not charged. Pick **Mumbai (ap-mumbai-1)** as home region during signup. Cannot change region later.
2. **Provision VM** — Compute → Instances → Create. Image: `Canonical Ubuntu 24.04` (ARM build). Shape: `VM.Standard.A1.Flex`, 2 OCPU + 12 GB RAM. Networking: public IPv4 + IPv6. SSH key: paste your pubkey.
3. **Open ports** — Networking → VCN → Security List → ingress rules: 80, 443. Subnet → Default Security List default-allows-22 (SSH).
4. **Cloud-init script** (paste during instance create or run after SSH):
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3.12 python3.12-venv git caddy ufw
   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
   sudo apt install -y nodejs
   sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
   ```
5. **Clone repo + boot services** — see [`scripts/oracle-bootstrap.sh`](../../../scripts/oracle-bootstrap.sh) (TODO: add when migrating).
6. **Caddyfile** at `/etc/caddy/Caddyfile`:
   ```
   resourceos.<your-domain> {
     reverse_proxy localhost:3000
   }
   api.resourceos.<your-domain> {
     reverse_proxy localhost:8000
     header Access-Control-Allow-Origin "https://resourceos.<your-domain>"
   }
   ```
   Caddy auto-issues TLS via Let's Encrypt.
7. **systemd units** under `/etc/systemd/system/resourceos-{api,web}.service` running uvicorn
   (root of the repo — no `backend/` subdirectory) + `npm start` from `frontend/`. No timer
   unit: refresh stays button-triggered and runs in-process inside the API service, same as on
   Render — there is nothing to schedule.
8. **DNS** — point A/AAAA `resourceos` and `api.resourceos` records to VM public IP. Cloudflare DNS free is fine.
9. **GitHub deploy hook** — GH Actions workflow on push to `main` SSHs to VM, `git pull && systemctl restart resourceos-{api,web}`. Add deploy SSH key as repo secret.

### Risks (called out before signup)
- **Reclamation** — Oracle reclaims always-free instances if idle 30+ days (no CPU/network activity). Mitigation: low-rate monitoring ping + occasional access keeps it alive.
- **CC verification** — they hold $1 auth on the card. Some Indian cards bounce; use a different card or Visa/Mastercard.
- **Capacity rejection** — Mumbai A1 ARM capacity sometimes exhausted; retry over hours/days. If never available, use a different region (Singapore / London).
- **Account suspension** — rare but reported when usage looks "abusive" (sustained CPU 100% for days). ResourceOS workload is fine; just don't run crypto miners.
- **No managed Postgres** — must self-host on the same VM (postgresql-16 from apt). Backup via `pg_dump` to Cloudflare R2 nightly.

---

## Fallback ladder (if Oracle blocks at any step)

Pick the **first** that works for the failure mode hit. Each adds $X/mo cost — accept the cheapest that works.

### Fallback A — AWS Lightsail with Activate credits
**When:** Oracle rejects CC, capacity unavailable in Mumbai, or signup blocked.

- AWS Activate $1k credit (already in seed catalog — sign up via the AWS Activate link).
- Lightsail $3.50/mo VPS (1 vCPU, 0.5 GB RAM, 20 GB SSD, 1 TB egress) in Mumbai (`ap-south-1`).
- $1k credit = ~285 months at lowest tier. Effectively years of free.
- Same architecture as Oracle (Ubuntu + Caddy + systemd).
- Loss vs Oracle: 0.5 GB RAM tight for FastAPI + Next.js together; bump to $5/mo plan (1 GB RAM) — credit still lasts ~16 years.

### Fallback B — Hetzner CX22 (€3.79/mo, EU only)
**When:** AWS credit exhausted or AWS signup is too painful.

- Hetzner Cloud, Falkenstein/Helsinki regions.
- 2 vCPU + 4 GB RAM + 40 GB SSD + 20 TB egress.
- Cheapest reliable always-on VPS.
- Loss vs Oracle: EU latency from India ~150ms (worse than Render's US).

### Fallback C — DigitalOcean Droplet ($4/mo, Bangalore)
**When:** Hetzner EU latency unacceptable AND no AWS credits.

- $4/mo basic droplet, 1 vCPU + 1 GB RAM + 25 GB SSD + 1 TB transfer.
- **Bangalore (`blr1`) region** = lowest India latency.
- Often $200 signup credit via student / referral programs.
- Loss vs Oracle: paid forever; small RAM.

### Fallback D — Stay on Render paid
**When:** No appetite for self-hosting / VPS ops.

- Render Starter plan: $7/mo per service = $14/mo total for both.
- Removes sleep + cold start.
- Adds: persistent disk, free Postgres for as long as paid.
- Zero ops burden, same `render.yaml` already locked.
- Loss vs Oracle: $14/mo forever, US/EU/SG only (no India region).

### Fallback E — Hybrid: Render paid api + Cloudflare Pages frontend
**When:** Frontend needs global edge AND we accept a split deploy.

- Cloudflare Pages free hosts Next.js (with `next-on-pages` adapter).
- Render Starter $7/mo runs FastAPI only.
- Loss vs Oracle: $7/mo, more moving parts, Pages adapter has quirks for some Next.js features.

### Decision tree

```
Can Oracle Mumbai signup + provision A1 ARM?
├─ YES → Oracle (primary)
└─ NO ─┬─ Have AWS Activate credit?
       │  └─ YES → Lightsail Mumbai (Fallback A)
       │  └─ NO  → Has time + ops appetite?
       │           ├─ YES → Hetzner CX22 (Fallback B) or DO Bangalore (Fallback C)
       │           └─ NO  → Render Starter $14/mo (Fallback D)
       └─ Want zero ops + edge frontend?
                    └─ Cloudflare Pages + Render Starter api (Fallback E)
```

---

## What does NOT change between Render → Oracle

These remain identical regardless of host:

- Repo layout (`domain/`, `storage/`, `freellm/`, `refresh/`, `api/`, `frontend/`, `data/` — all
  at repo root; no `backend/` subdirectory).
- `data/providers_seed.json` schema.
- FastAPI routes.
- Next.js pages + components.
- env-var names (`BACKEND_URL`/`BACKEND_HOST`, `CORS_ORIGINS`, `ADMIN_TOKEN`,
  `GITHUB_DATA_TOKEN`, `DATA_BRANCH`, all `*_API_KEY` — see the README's env var table).
- GitHub Actions CI (lint + test).
- Refresh stays button-triggered, in-process — no cron to move. The database's persistence
  mechanism (the `data` git branch) is unaffected by which host runs the API.

Migration cost = ops setup + DNS, not code rewrites. Should fit a single Saturday.

---

## Anti-patterns (block in review)

- **Don't migrate before a trigger fires.** Premature migration = wasted weekend.
- **Don't dual-deploy.** Pick one host. Two deploys = two sources of truth = drift.
- **Don't hardcode Render URLs in code** — all URL refs MUST come from env vars (`BACKEND_URL`/`BACKEND_HOST`) so migration is config-only.
- **Don't lose the version history.** The `data` git branch already carries the full append-only
  history independent of the host — confirm `git fetch origin data` succeeds from the new host
  before decommissioning Render, rather than introducing a new export/import step.
- **Don't migrate v0.3 Media Benchmark BEFORE the host swap.** ffmpeg + video gen on Render free will fail; migrate first if those features land before Oracle is up.

---

## Migration checklist (when trigger fires)

- [ ] Confirm trigger (which one of 1–6 above).
- [ ] Sign up at oracle.com/cloud/free. Pick Mumbai. Verify CC.
- [ ] Provision A1 Flex VM (2 OCPU, 12 GB). Wait for capacity.
- [ ] Run cloud-init script. SSH-verify.
- [ ] Open ports 80/443 in VCN security list.
- [ ] DNS: A/AAAA records to public IP.
- [ ] Caddy + systemd units in place. Smoke-test on `https://resourceos.<domain>`.
- [ ] Confirm the new host can pull the `data` branch (`GITHUB_DATA_TOKEN` set, `git fetch
      origin data` succeeds) — this replaces any manual database export/import.
- [ ] Update GH Actions deploy workflow to SSH-deploy to Oracle.
- [ ] Run `python -m pytest` + `npm run build` against new host.
- [ ] Cut DNS over. 5-min TTL ahead of cutover.
- [ ] Decommission Render services after 7-day soak.
- [ ] If Oracle fails at any step → walk fallback ladder above.

When this rule activates, write the actual migration as a dated artifact under `docs/architecture/oracle-migration/<YYYY-MM-DD>T<HH-MM>-runbook.md` per the global `specialist-discussions.md` rule.
