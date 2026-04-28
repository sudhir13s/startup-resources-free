"""Enrich the top 10 seed records with detailed `limits` + extended fields.

Numbers sourced from each vendor's public free-tier docs as of 2026-04-28.
Run this once: `python scripts/enrich_seed_top10.py`. It mutates
data/seed.json in place. Verify with `git diff data/seed.json` before commit.

Until the agentic pipeline (v0.2) extracts these per-provider, this is the
fastest way to make the detail modal show real numbers for the most-asked
providers.
"""
from __future__ import annotations

import json
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "data" / "seed.json"

ENRICHMENTS: dict[str, dict] = {
    "vercel": {
        "subcategory": "frontend-hosting",
        "access_method": "github-auth",
        "tier_fit_rationale": "Hobby plan generous for personal sites, prototypes, MVPs. Commercial-use ban on Hobby forces paid Pro at first revenue — plan migration before launch.",
        "restrictions": "Hobby plan is non-commercial only. Any monetized site (ads, paid users, e-commerce) requires Pro ($20/user/month).",
        "limits": {
            "bandwidth_gb_per_month": 100,
            "build_minutes_per_month": 6000,
            "serverless_function_invocations_per_day": 100000,
            "serverless_function_max_duration_s": 10,
            "serverless_function_max_memory_mb": 1024,
            "edge_function_invocations_per_day": 500000,
            "edge_middleware_invocations_per_day": 1000000,
            "preview_deployments": "Unlimited",
            "team_members": 1,
            "domains_per_project": 50,
            "image_optimizations_per_month": 1000,
            "log_retention_hours": 1,
            "regions": "Global edge network (~30 PoPs)",
            "supported_runtimes": ["Node.js 18", "Node.js 20", "Edge", "Python", "Go", "Ruby"],
            "commercial_use_allowed": False,
            "ssl_certificates": "Auto Let's Encrypt",
            "custom_domain": True,
        },
    },
    "render": {
        "subcategory": "paas",
        "access_method": "github-auth",
        "tier_fit_rationale": "Free Web Service is best for hobby projects + dogfood demos. The 15-min idle spin-down is fine for personal sites; not suitable for any production user-facing product.",
        "restrictions": "Free services spin down after 15 min idle (cold-start ~30-60s on first hit). Free Postgres is deleted after 90 days.",
        "limits": {
            "web_service_hours_per_month": 750,
            "build_minutes_per_month": 500,
            "spin_down_after_idle_min": 15,
            "cold_start_seconds": "30-60",
            "ram_mb": 512,
            "cpu_shared_vcpu": 0.1,
            "bandwidth_gb_per_month": 100,
            "static_sites": "Unlimited",
            "static_site_bandwidth_gb_per_month": 100,
            "postgres_free_storage_gb": 1,
            "postgres_max_age_days_before_deletion": 90,
            "redis_free_ram_mb": 25,
            "regions": ["Oregon", "Frankfurt", "Singapore", "Ohio", "Virginia"],
            "ssl_certificates": "Auto Let's Encrypt",
            "custom_domain": True,
            "background_workers": "Available on free",
            "cron_jobs": "Available on free",
        },
    },
    "cloudflare-workers": {
        "subcategory": "edge-compute",
        "access_method": "email-verify",
        "tier_fit_rationale": "Free quota generous for hobby + small production workloads. 10ms CPU/request is the constraint — fine for stateless functions, edge auth, simple APIs.",
        "limits": {
            "requests_per_day": 100000,
            "cpu_time_ms_per_request": 10,
            "max_request_size_mb": 100,
            "max_response_size_mb": 100,
            "scripts_per_account": 100,
            "kv_reads_per_day": 100000,
            "kv_writes_per_day": 1000,
            "kv_storage_gb": 1,
            "kv_keys": 1000,
            "durable_objects": "Paid only ($5/mo)",
            "queues": "Paid only ($5/mo)",
            "workers_ai_neurons_per_day": 10000,
            "regions": "Global edge (>300 PoPs)",
            "custom_domain": True,
            "ssl_certificates": "Auto",
        },
    },
    "groq": {
        "subcategory": "llm-inference",
        "access_method": "email-verify",
        "tier_fit_rationale": "Fastest free LLM inference on the market. RPD caps make it unsuitable for production user-facing chat at scale, but excellent for batch extraction, dev/test, and low-traffic apps.",
        "limits": {
            "models_available": [
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "llama-3.2-90b-vision",
                "mixtral-8x7b-32768",
                "gemma-7b-it",
                "whisper-large-v3",
            ],
            "requests_per_minute_llama_70b": 30,
            "requests_per_day_llama_70b": 14400,
            "tokens_per_minute_llama_70b": 6000,
            "tokens_per_day_llama_70b": 1000000,
            "context_window_llama_70b": 128000,
            "context_window_llama_8b": 128000,
            "context_window_mixtral": 32768,
            "vision_supported": True,
            "function_calling_supported": True,
            "stream_supported": True,
            "structured_output_supported": True,
            "whisper_audio_seconds_per_hour": 7200,
            "regions": ["US"],
            "openai_compatible_api": True,
        },
    },
    "google-ai-studio": {
        "subcategory": "llm-inference",
        "access_method": "email-verify",
        "tier_fit_rationale": "Most generous free RPD for vision-capable LLM. Gemini 2.0 Flash + 1.5 Pro both have free tiers usable for hobby AND personal-tool production.",
        "limits": {
            "models_available": [
                "gemini-2.0-flash-exp",
                "gemini-1.5-flash",
                "gemini-1.5-flash-8b",
                "gemini-1.5-pro",
                "text-embedding-004",
            ],
            "requests_per_minute_flash": 15,
            "requests_per_day_flash": 1500,
            "tokens_per_minute_flash": 1000000,
            "requests_per_minute_pro": 2,
            "requests_per_day_pro": 50,
            "tokens_per_minute_pro": 32000,
            "context_window_flash": 1000000,
            "context_window_pro": 2000000,
            "vision_supported": True,
            "audio_input_supported": True,
            "video_input_supported": True,
            "function_calling_supported": True,
            "structured_output_supported": True,
            "image_generation": "Imagen 3 (paid only)",
            "data_used_for_training": "Free tier inputs may be used to improve models",
            "regions": "Global (with regional residency on paid tier)",
        },
    },
    "supabase": {
        "subcategory": "postgres-baas",
        "access_method": "github-auth",
        "tier_fit_rationale": "Production-ready free tier for personal + startup-MVP. 500 MB DB, 2 projects, daily backups for 7 days. Scales naturally to paid Pro at $25/mo when traction warrants.",
        "restrictions": "Free projects pause after 7 days of inactivity (resume on first request, ~10s wakeup).",
        "limits": {
            "projects": 2,
            "database_size_mb": 500,
            "database_engine": "PostgreSQL 15",
            "auth_users": 50000,
            "auth_third_party_oauth": True,
            "storage_gb": 1,
            "edge_function_invocations_per_month": 500000,
            "realtime_concurrent_connections": 200,
            "realtime_messages_per_month": 2000000,
            "vector_embeddings": "pgvector included",
            "daily_backups_retention_days": 7,
            "point_in_time_recovery": "Paid only",
            "auto_pause_after_days_idle": 7,
            "regions": [
                "us-east-1", "us-west-1", "eu-west-1", "eu-central-1",
                "ap-south-1 (Mumbai)", "ap-southeast-1", "ap-southeast-2",
            ],
            "ssl_certificates": "Auto",
            "custom_domain": "Paid only",
        },
    },
    "cloudflare-r2": {
        "subcategory": "object-storage",
        "access_method": "email-verify",
        "tier_fit_rationale": "Best free object storage by far — 10 GB + zero egress fee. S3-API-compatible. The only large free-tier blob storage that won't surprise-bill you on hot files.",
        "limits": {
            "storage_gb": 10,
            "class_a_operations_per_month": 1000000,
            "class_b_operations_per_month": 10000000,
            "egress_fee": "$0 (free egress to anywhere)",
            "egress_gb_per_month": "Unlimited",
            "max_object_size_gb": 4995,
            "buckets_per_account": 1000,
            "api_compatibility": "S3-compatible",
            "regions": "Global (auto-replicated)",
            "presigned_urls": True,
            "lifecycle_rules": True,
            "versioning": True,
        },
    },
    "aws-activate": {
        "subcategory": "cloud-credits",
        "access_method": "manual-apply",
        "tier_fit_rationale": "Best startup-credit program if you can swing the eligibility. Founders tier is self-serve ($1k); Portfolio tier ($5k-$100k) needs an accredited accelerator/VC referral.",
        "currency": "USD",
        "credit_amount": 5000,
        "credit_duration_days": 730,
        "restrictions": "Credits can only be used on AWS services. Cannot transfer between accounts. Expire on the listed date — no rollover.",
        "limits": {
            "tiers": {
                "founders": {
                    "credit_usd": 1000,
                    "duration_months": 24,
                    "eligibility": "Self-serve. Bootstrapped or pre-funded startup.",
                    "approval_time_hours": 24,
                },
                "portfolio_low": {
                    "credit_usd": 5000,
                    "duration_months": 24,
                    "eligibility": "Accelerator / VC partner referral required.",
                },
                "portfolio_high": {
                    "credit_usd": 100000,
                    "duration_months": 24,
                    "eligibility": "Accredited accelerator / Tier-1 VC portfolio company.",
                },
            },
            "services_eligible": "All AWS services except Marketplace + Reserved Instances",
            "support_included_founders": "Basic support",
            "support_included_portfolio": "Business support ($100/mo value)",
            "training_credits_aws_skill_builder_usd": 1000,
            "regions": "All AWS regions globally",
            "ec2_eligible": True,
            "rds_eligible": True,
            "lambda_eligible": True,
            "s3_eligible": True,
            "bedrock_eligible": True,
            "sagemaker_eligible": True,
        },
    },
    "yc": {
        "subcategory": "tier-1-accelerator",
        "access_method": "manual-apply",
        "tier_fit_rationale": "Top global accelerator. $500k investment, 13-week intensive program in SF. Acceptance ~1.5%. Takes 7% equity ($125k as SAFE + $375k post-money SAFE).",
        "currency": "USD",
        "credit_amount": 500000,
        "restrictions": "Founders must relocate to SF Bay Area for the full 13-week batch. Equity (~7%) is taken via standard SAFE.",
        "limits": {
            "investment_amount_usd": 500000,
            "investment_structure": "$125k SAFE (standard YC deal) + $375k uncapped post-money SAFE with MFN",
            "equity_taken_percent": 7,
            "batches_per_year": 2,
            "batch_duration_weeks": 13,
            "acceptance_rate_percent": "~1.5",
            "demo_day_investors_attending": "~1500 active VCs",
            "alumni_network_size": ">5000 founders",
            "alumni_perks_value_usd": ">1000000",
            "free_credits_perks_breakdown": {
                "AWS Activate": "$100k credits",
                "GCP for Startups": "$200k credits",
                "Stripe Atlas": "Free incorporation",
                "Brex": "Banking + cards",
                "Hubspot": "$50k value",
                "Notion": "Free workspace",
                "Many others": "100+ partner perks",
            },
            "office_space": "Required attendance in SF Bay Area for batch",
            "post_demo_day_support": "Bookface (alumni network) + Continuity (follow-on funding)",
        },
    },
    "startup-india-seed": {
        "subcategory": "non-dilutive-grant",
        "access_method": "manual-apply",
        "tier_fit_rationale": "India-only grant from DPIIT-recognized incubators. Up to ₹20 lakh as grant for PoC/prototype + up to ₹50 lakh as convertible debt for market entry. Reduces equity dilution massively.",
        "currency": "INR",
        "credit_amount": 5000000,
        "restrictions": "Eligible only for DPIIT-recognized startups < 2 years old, incorporated in India, not derived from a separation/restructuring of an existing business. Specific sectors prioritized.",
        "limits": {
            "grant_amount_inr_max": 2000000,
            "grant_purpose": "Proof of concept / prototype / product trials",
            "convertible_debt_inr_max": 5000000,
            "convertible_debt_purpose": "Market entry / commercialization / scaling",
            "company_age_max_years": 2,
            "company_must_be_dpiit_recognized": True,
            "indian_subsidiary_required": True,
            "founders_indian_citizens_required": False,
            "shareholding_indian_promoters_min_percent": 51,
            "sectors_priority": [
                "AI/ML", "Deep tech", "IoT", "Fintech",
                "Health tech", "Climate", "Mobility", "Agritech",
                "Education tech", "Defense / Aerospace",
            ],
            "incubator_partner_required": True,
            "approved_incubators_count": ">300",
            "milestones_required": True,
            "tranches_typical": "3 (40% / 30% / 30%)",
            "reporting_required": "Quarterly utilization certificate",
            "decision_timeline_months": "3-6",
        },
    },
}


def main() -> None:
    raw = json.loads(SEED.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in raw}

    enriched = 0
    for pid, extra in ENRICHMENTS.items():
        if pid not in by_id:
            print(f"  WARN: id '{pid}' not in seed; skipped")
            continue
        rec = by_id[pid]
        for k, v in extra.items():
            rec[k] = v
        enriched += 1

    SEED.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Enriched {enriched} records.")


if __name__ == "__main__":
    main()
