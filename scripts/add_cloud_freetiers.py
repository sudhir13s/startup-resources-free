"""Add the big-cloud always-free / 12-month-free entries that were missing
from the seed: AWS Free Tier, GCP Free Tier, Azure Free, Oracle Always Free.

These are DIFFERENT records from the startup-credit programs already in the
seed (`aws-activate`, `gcp-startups`, `microsoft-startups`). Free-tier records
describe what every new account gets without applying — useful for hobby /
personal / startup-MVP tiers BEFORE you qualify for credits.

Idempotent: skips records whose `id` already exists.
"""
from __future__ import annotations

import json
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "data" / "seed.json"

NEW_RECORDS: list[dict] = [
    {
        "id": "aws-free-tier",
        "name": "AWS Free Tier",
        "category": "cloud",
        "subcategory": "iaas-paas",
        "headline": "AWS free tier — always-free + 12-month-free across 100+ services for any new account.",
        "free_tier_summary": "Three layers: Always Free (Lambda 1M req/mo, DynamoDB 25 GB, CloudFront 1 TB egress), 12-Months-Free (EC2 t2.micro 750h/mo, S3 5 GB, RDS db.t2.micro 750h/mo), Trials (SageMaker 250h/mo for 2 mo, etc.). Generous enough for a personal SaaS first year.",
        "quota_summary": "100+ services",
        "duration_summary": "12-month + always-free",
        "region_summary": "All AWS regions globally",
        "offer_type": "free-tier",
        "eligibility_summary": "Any new AWS account; CC required; some services US-only on free tier.",
        "use_case_tiers": ["hobby", "personal", "startup-mvp"],
        "india_accessible": True,
        "geo_priority": "global-other",
        "source_url": "https://aws.amazon.com/free/",
        "parse_confidence": "high",
        "last_verified_at": "2026-04-28",
        "notes": "12-month clock starts at sign-up; expires regardless of usage. Set billing alerts BEFORE you launch. Mumbai (ap-south-1) supported on most free-tier services.",
        "access_method": "signup",
        "tier_fit_rationale": "Always-free is genuinely always-free; 12-month is the bigger win for hobby + personal. Startup-mvp can run a real product on it for the first year. Past year-1 you must qualify for AWS Activate credits or move to a smaller cloud.",
        "restrictions": "Only US East (N. Virginia) for some services. Many free quotas are per-region, not global. Crossing into paid usage doesn't trigger a hard stop — set billing alerts.",
        "limits": {
            "always_free_layer": {
                "lambda_requests_per_month": 1000000,
                "lambda_compute_seconds_per_month": 400000,
                "dynamodb_storage_gb": 25,
                "dynamodb_read_capacity_units": 25,
                "dynamodb_write_capacity_units": 25,
                "cloudfront_data_transfer_out_gb_per_month": 1024,
                "cloudfront_https_requests_per_month": 10000000,
                "sns_publishes_per_month": 1000000,
                "sqs_requests_per_month": 1000000,
                "ses_emails_per_day": 200,
                "cognito_mau": 50000,
                "x_ray_traces_per_month": 100000,
            },
            "12_month_layer": {
                "ec2_t2_micro_hours_per_month": 750,
                "ec2_t3_micro_hours_per_month": 750,
                "ec2_supported_regions": "Most regions; check per region",
                "s3_storage_gb": 5,
                "s3_get_requests_per_month": 20000,
                "s3_put_requests_per_month": 2000,
                "rds_db_t2_micro_hours_per_month": 750,
                "rds_storage_gb": 20,
                "rds_engines": ["MySQL", "PostgreSQL", "MariaDB", "SQL Server Express"],
                "elb_hours_per_month": 750,
                "elb_data_processed_gb_per_month": 15,
                "ebs_storage_gb": 30,
                "ebs_io_requests_per_month": 2000000,
                "cloudwatch_metrics": 10,
                "cloudwatch_alarms": 10,
                "data_transfer_out_gb_per_month": 100,
            },
            "trials_short_lived": {
                "sagemaker_studio_hours_per_month_for_2_months": 250,
                "redshift_dc2_large_hours_for_2_months": 750,
            },
            "regions": "All public AWS regions including ap-south-1 (Mumbai)",
            "billing_alerts_recommended": True,
        },
    },
    {
        "id": "gcp-free-tier",
        "name": "Google Cloud Free Tier",
        "category": "cloud",
        "subcategory": "iaas-paas",
        "headline": "GCP free tier — always-free + $300 / 90-day credits for new accounts.",
        "free_tier_summary": "Always-Free (Compute Engine e2-micro 1 instance/mo in us-west1/east1/central1, Cloud Storage 5 GB, Cloud Functions 2M invocations, Firestore 1 GB + 50k reads/day, BigQuery 1 TB queries/mo, Cloud Run 2M req/mo). Plus $300 USD signup credits good for 90 days.",
        "quota_summary": "$300 credits + always-free",
        "duration_summary": "90 days + always-free",
        "region_summary": "us-west1 / us-central1 / us-east1 (free), all regions on credits",
        "offer_type": "free-tier",
        "eligibility_summary": "Any new GCP account; CC required for verification; not charged during free credits.",
        "use_case_tiers": ["hobby", "personal", "startup-mvp"],
        "india_accessible": True,
        "geo_priority": "global-other",
        "source_url": "https://cloud.google.com/free",
        "parse_confidence": "high",
        "last_verified_at": "2026-04-28",
        "notes": "Always-free Compute is US-region-only — Mumbai (asia-south1) is paid. Use the $300 credits in any region while they last. After 90 days only Always-Free continues; rest stops billing OR converts to paid (your choice at signup).",
        "access_method": "signup",
        "tier_fit_rationale": "Always-free is small but stable. The $300 / 90-day credit is the real win — enough to run a Series-A-quality stack for 3 months while you decide.",
        "restrictions": "Always-free Compute Engine + Storage are US-only. Crossing $300 credit triggers paid billing if you opted in. Free Compute requires manual upgrade-to-paid choice at credit-end.",
        "limits": {
            "signup_credit": {
                "credit_usd": 300,
                "duration_days": 90,
                "auto_charge_after_credit": "Only if you upgraded to paid during the trial",
            },
            "always_free": {
                "compute_engine_e2_micro_instance": 1,
                "compute_engine_e2_micro_regions": ["us-west1", "us-central1", "us-east1"],
                "compute_engine_e2_micro_hours_per_month": 720,
                "compute_engine_disk_gb_standard": 30,
                "compute_engine_egress_gb_per_month_out_of_north_america": 1,
                "cloud_storage_gb_standard_us_only": 5,
                "cloud_storage_class_a_ops_per_month": 5000,
                "cloud_storage_class_b_ops_per_month": 50000,
                "cloud_storage_egress_to_us_china_australia_gb_per_month": 1,
                "cloud_functions_invocations_per_month": 2000000,
                "cloud_functions_compute_time_gb_seconds_per_month": 400000,
                "cloud_run_requests_per_month": 2000000,
                "cloud_run_cpu_seconds_per_month": 180000,
                "cloud_run_memory_gb_seconds_per_month": 360000,
                "firestore_storage_gb": 1,
                "firestore_document_reads_per_day": 50000,
                "firestore_document_writes_per_day": 20000,
                "firestore_document_deletes_per_day": 20000,
                "bigquery_storage_gb": 10,
                "bigquery_query_processing_tb_per_month": 1,
                "vertex_ai_text_embedding_requests_per_month": 1000,
                "pubsub_messages_gb_per_month": 10,
                "logs_gb_per_month": 50,
            },
            "regions_for_always_free": ["us-west1", "us-central1", "us-east1"],
            "regions_for_credits": "All GCP regions including asia-south1 (Mumbai)",
        },
    },
    {
        "id": "azure-free",
        "name": "Microsoft Azure Free Account",
        "category": "cloud",
        "subcategory": "iaas-paas",
        "headline": "Azure free account — $200 / 30-day credits + 12-month-free + 25+ always-free services.",
        "free_tier_summary": "Three layers: $200 USD credits for 30 days, 12-Months-Free (B1S Linux/Windows VM 750h/mo, 64 GB SSD, 5 GB Blob, 250 GB SQL DB), Always-Free (App Service 10 apps, Functions 1M req, Cosmos DB 1000 RU + 25 GB, Cognitive Services free tiers).",
        "quota_summary": "$200 credits + 12-month + always-free",
        "duration_summary": "30 days + 12 months + always-free",
        "region_summary": "Most Azure regions; some services region-restricted",
        "offer_type": "free-tier",
        "eligibility_summary": "Any new Azure account; CC required for verification; not charged during $200 credit period.",
        "use_case_tiers": ["hobby", "personal", "startup-mvp"],
        "india_accessible": True,
        "geo_priority": "global-other",
        "source_url": "https://azure.microsoft.com/en-us/free/",
        "parse_confidence": "high",
        "last_verified_at": "2026-04-28",
        "notes": "Central India + South India + West India regions all supported on free tier. AI services (Translator, Computer Vision, Speech) have generous always-free transaction quotas — the most underrated free AI in the market.",
        "access_method": "signup",
        "tier_fit_rationale": "Best free-tier for AI features (Cognitive Services). 12-month VM + DB is solid for a real MVP. $200 / 30 days is tighter than GCP's $300 / 90 days but Azure's always-free Cognitive Services last forever.",
        "restrictions": "$200 credit valid only for first 30 days. After 30 days, free-tier services continue but anything outside free tier requires upgrading to pay-as-you-go.",
        "limits": {
            "signup_credit": {
                "credit_usd": 200,
                "duration_days": 30,
            },
            "12_month_free": {
                "vm_b1s_linux_hours_per_month": 750,
                "vm_b1s_windows_hours_per_month": 750,
                "managed_disk_p6_64gb_count": 2,
                "blob_storage_lrs_gb": 5,
                "file_storage_lrs_gb": 5,
                "sql_database_s0_dtu": 250,
                "sql_database_storage_gb": 250,
                "data_transfer_out_gb_per_month": 15,
            },
            "always_free": {
                "app_service_apps_linux_or_windows": 10,
                "azure_functions_invocations_per_month": 1000000,
                "azure_functions_compute_gb_seconds_per_month": 400000,
                "cosmos_db_storage_gb": 25,
                "cosmos_db_request_units_per_second": 1000,
                "ad_b2c_mau": 50000,
                "monitor_data_ingested_gb": 5,
                "active_directory_users": 50000,
                "translator_text_chars_per_month": 2000000,
                "computer_vision_transactions_per_month": 5000,
                "speech_transcription_hours_per_month": 5,
                "language_understanding_text_requests_per_month": 5000,
                "form_recognizer_pages_per_month": 500,
                "container_apps_vcpu_seconds_per_month": 180000,
                "container_apps_gib_seconds_per_month": 360000,
                "container_apps_requests_per_month": 2000000,
            },
            "regions_supported_for_free": "All Azure regions including Central / South / West India",
        },
    },
    {
        "id": "oracle-always-free",
        "name": "Oracle Cloud Always Free",
        "category": "cloud",
        "subcategory": "iaas",
        "headline": "Oracle Cloud's always-free is the most generous of any public cloud — 4 ARM cores + 24 GB RAM + 200 GB storage forever.",
        "free_tier_summary": "Always Free: 4 ARM Ampere A1 OCPUs + 24 GB RAM (split across up to 4 VMs), 2x AMD VM.Standard.E2.1.Micro instances, 200 GB block storage, 10 TB egress/month, 2x Autonomous Databases (20 GB each), 10 GB object storage, Always Free Load Balancer. Plus $300 / 30-day signup credits.",
        "quota_summary": "4 ARM cores + 24 GB RAM",
        "duration_summary": "Always free (forever)",
        "region_summary": "All OCI regions including ap-mumbai-1 (India)",
        "offer_type": "always-free",
        "eligibility_summary": "Any new Oracle Cloud account; CC required ($1 auth hold); home region locked at signup.",
        "use_case_tiers": ["hobby", "personal", "startup-mvp", "pre-seed"],
        "india_accessible": True,
        "geo_priority": "global-other",
        "source_url": "https://www.oracle.com/cloud/free/",
        "parse_confidence": "high",
        "last_verified_at": "2026-04-28",
        "notes": "Reclaims always-free resources after 30 days of inactivity (no CPU/network usage). Mumbai (ap-mumbai-1) supports always-free but ARM A1 capacity is sometimes exhausted — retry over hours/days. ResourceOS migration target if Render free-tier triggers fire.",
        "access_method": "signup",
        "tier_fit_rationale": "Best free-tier compute by an order of magnitude. 4 ARM cores + 24 GB RAM trivially runs FastAPI + Next.js + Postgres + Redis + scrapers all on one VM. Can host pre-seed startups for $0 forever — provided you accept Oracle's signup friction and reclamation policy.",
        "restrictions": "ARM A1 capacity reclaimed if idle 30+ days. Some regions occasionally reject A1 provisioning due to capacity. Account suspension reported (rare) when sustained 100% CPU looks abusive.",
        "limits": {
            "always_free": {
                "compute_arm_ampere_a1_ocpu": 4,
                "compute_arm_ampere_a1_ram_gb": 24,
                "compute_arm_ampere_a1_max_vms": 4,
                "compute_amd_vm_e2_1_micro_count": 2,
                "compute_amd_vm_e2_1_micro_ram_gb": 1,
                "block_storage_gb": 200,
                "object_storage_gb": 10,
                "object_storage_archive_gb": 10,
                "egress_tb_per_month": 10,
                "autonomous_databases_count": 2,
                "autonomous_database_storage_gb_each": 20,
                "load_balancer_flexible_count": 1,
                "load_balancer_bandwidth_mbps": 10,
                "vault_keys_count": 20,
                "vault_secrets_count": 150,
                "monitoring_metrics_per_month": 500000,
                "logs_per_month_gb": 10,
                "vpn_ipsec_tunnels_count": 50,
                "site_to_site_vpn": True,
                "free_dns_zones": "Always free",
            },
            "signup_credit": {
                "credit_usd": 300,
                "duration_days": 30,
            },
            "regions_supported_for_free": [
                "us-ashburn-1", "us-phoenix-1", "uk-london-1",
                "eu-frankfurt-1", "ap-tokyo-1", "ap-mumbai-1",
                "ap-singapore-1", "ap-sydney-1", "ca-toronto-1",
                "sa-saopaulo-1", "and many more",
            ],
            "reclaim_policy_idle_days": 30,
        },
    },
]


def main() -> None:
    raw = json.loads(SEED.read_text(encoding="utf-8"))
    existing_ids = {p["id"] for p in raw}

    added = 0
    for rec in NEW_RECORDS:
        if rec["id"] in existing_ids:
            print(f"  WARN: id '{rec['id']}' already exists; skipped")
            continue
        raw.append(rec)
        added += 1

    SEED.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Added {added} cloud free-tier records (total now {len(raw)}).")


if __name__ == "__main__":
    main()
