"""Lift nested per-service breakdowns out of `limits` into `sub_offerings`
for the four big-cloud free-tier records, and set `always_on` flags.

Idempotent — re-running produces the same JSON. Run once:
    python scripts/lift_sub_offerings.py
"""
from __future__ import annotations

import json
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "data" / "seed.json"

# Per-record lift instructions: which limits subkeys → sub_offerings + always_on.
LIFTS: dict[str, dict] = {
    "aws-free-tier": {
        "always_on": False,  # Free Lambda/EC2 don't sleep, but the program is non-permanent
        "lifts": [
            {
                "from": "always_free_layer",
                "service_name": "Always Free",
                "headline": "Lambda 1M req/mo, DynamoDB 25 GB, CloudFront 1 TB egress, SNS/SQS/SES",
            },
            {
                "from": "12_month_layer",
                "service_name": "12-Month Free",
                "headline": "EC2 t2.micro 750h, S3 5 GB, RDS 750h, EBS 30 GB, ELB 750h",
            },
            {
                "from": "trials_short_lived",
                "service_name": "Short Trials",
                "headline": "SageMaker 250h/mo for 2 mo, Redshift dc2.large 750h for 2 mo",
            },
        ],
    },
    "gcp-free-tier": {
        "always_on": False,  # e2-micro is always-on but credits-tier compute isn't
        "lifts": [
            {
                "from": "always_free",
                "service_name": "Always Free",
                "headline": "Compute e2-micro (US), Cloud Storage 5 GB, Functions 2M req, Run 2M req, Firestore 1 GB",
            },
            {
                "from": "signup_credit",
                "service_name": "$300 Signup Credit",
                "headline": "$300 USD usable across all services for 90 days",
            },
        ],
    },
    "azure-free": {
        "always_on": False,
        "lifts": [
            {
                "from": "always_free",
                "service_name": "Always Free",
                "headline": "App Service 10 apps, Functions 1M req, Cosmos DB 25 GB + 1k RU/s, Cognitive Services free quotas",
            },
            {
                "from": "12_month_free",
                "service_name": "12-Month Free",
                "headline": "B1S Linux/Win VM 750h, Blob 5 GB, SQL DB 250 GB, 64 GB managed disks",
            },
            {
                "from": "signup_credit",
                "service_name": "$200 Signup Credit",
                "headline": "$200 USD usable across all services for 30 days",
            },
        ],
    },
    "oracle-always-free": {
        "always_on": True,  # ARM A1 + AMD micro both stay running 24/7
        "lifts": [
            {
                "from": "always_free",
                "service_name": "Always Free",
                "headline": "4 ARM cores + 24 GB RAM, 200 GB block, 10 TB egress, 2 Autonomous DBs, Load Balancer",
            },
            {
                "from": "signup_credit",
                "service_name": "$300 Signup Credit",
                "headline": "$300 USD usable across all services for 30 days",
            },
        ],
    },
}

# Records where always_on is unambiguously true based on vendor docs.
ALWAYS_ON_TRUE_FOR: set[str] = {
    "vercel",  # Hobby is no-sleep
    "cloudflare-workers",  # Edge — no idle concept
    "cloudflare-r2",  # Storage — always-online
    "groq",
    "openrouter",
    "google-ai-studio",
    "huggingface",
    "supabase",  # auto-pause after 7 days idle but operational always-on within
    "neon",
    "mongodb-atlas",
    "github-actions",
    "backblaze-b2",
    "clerk",
    "auth0",
    "sentry",
    "grafana-cloud",
}

# Records where always_on is false (sleep / batch / non-applicable).
ALWAYS_ON_FALSE_FOR: set[str] = {
    "render",  # Free Web Service spin-down after 15 min idle
    "fly-io",  # Free machines auto-stop
    "google-colab",  # session-based
    "kaggle",  # session-based
}


def main() -> None:
    raw = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in raw}

    lifted = []
    flagged_on = []
    flagged_off = []

    for pid, instr in LIFTS.items():
        rec = by_id.get(pid)
        if rec is None:
            print(f"  WARN: id '{pid}' missing — skipped lift")
            continue
        rec["always_on"] = instr["always_on"]
        flagged_off.append(pid) if instr["always_on"] is False else flagged_on.append(pid)

        sub = []
        limits = dict(rec.get("limits") or {})
        for L in instr["lifts"]:
            key = L["from"]
            if key in limits:
                sub.append(
                    {
                        "service_name": L["service_name"],
                        "headline": L["headline"],
                        "limits": limits.pop(key),
                    },
                )
        # Surviving limits keys (non-nested top-level info) stay in `limits`.
        if sub:
            rec["sub_offerings"] = sub
            rec["limits"] = limits
            lifted.append(pid)

    # Set always_on flags for clearly-on / clearly-off records that don't have lifts.
    for rec in raw:
        pid = rec["id"]
        if pid in LIFTS:
            continue  # already handled
        if pid in ALWAYS_ON_TRUE_FOR:
            rec["always_on"] = True
            flagged_on.append(pid)
        elif pid in ALWAYS_ON_FALSE_FOR:
            rec["always_on"] = False
            flagged_off.append(pid)

    SEED.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Lifted sub_offerings on {len(lifted)} records: {lifted}")
    print(f"always_on=True on {len(flagged_on)} records")
    print(f"always_on=False on {len(flagged_off)} records")


if __name__ == "__main__":
    main()
