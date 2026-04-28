/**
 * Human-readable label + unit suffix for canonical limits keys.
 *
 * Keeps the detail modal's Limits / Sub-offerings sections clean:
 *
 *   Web Service           : 750 hours/month
 *   Build Minutes         : 500 minutes/month
 *   RAM                   : 512 MB
 *   Cold Start            : 30-60 seconds
 *
 * Non-canonical keys (LLM-emitted ad-hoc) fall back to Title-Case
 * generated from snake_case via `prettyKey()`.
 *
 * Mirrors the shape declared in `schema/limits.py`. When you add a
 * canonical key there, add the label here.
 */

export type LimitFieldMeta = {
  label: string;
  unit?: string;
  /** Force a value formatter — useful for booleans that need labels
   * other than Yes/No (e.g. custom_domain_supported → "Yes" / "No"). */
};

export const LIMIT_FIELD_META: Record<string, LimitFieldMeta> = {
  // ===== Cloud / Hosting =====
  compute_hours_per_month: { label: "Compute", unit: "hours/month" },
  web_service_hours_per_month: { label: "Web Service", unit: "hours/month" },
  build_minutes_per_month: { label: "Build Minutes", unit: "minutes/month" },
  vcpu: { label: "vCPU" },
  cpu_shared_vcpu: { label: "CPU Shared", unit: "vCPU" },
  ram_gb: { label: "RAM", unit: "GB" },
  ram_mb: { label: "RAM", unit: "MB" },
  storage_gb: { label: "Storage", unit: "GB" },
  bandwidth_gb: { label: "Bandwidth", unit: "GB/month" },
  bandwidth_gb_per_month: { label: "Bandwidth", unit: "GB/month" },
  cold_start_seconds: { label: "Cold Start", unit: "seconds" },
  spin_down_after_idle_min: { label: "Spin Down After Idle", unit: "minutes" },
  always_on: { label: "Always On" },
  custom_domain_supported: { label: "Custom Domain" },
  ssl_certificates: { label: "SSL Certificates" },
  commercial_use_allowed: { label: "Commercial Use" },
  max_request_size_mb: { label: "Max Request Size", unit: "MB" },
  max_response_size_mb: { label: "Max Response Size", unit: "MB" },
  regions: { label: "Regions" },
  static_sites: { label: "Static Sites" },
  static_site_bandwidth_gb_per_month: {
    label: "Static Site Bandwidth",
    unit: "GB/month",
  },
  postgres_free_storage_gb: { label: "Postgres Free Storage", unit: "GB" },
  postgres_max_age_days_before_deletion: {
    label: "Postgres Max Age Before Deletion",
    unit: "days",
  },
  redis_free_ram_mb: { label: "Redis Free RAM", unit: "MB" },
  background_workers: { label: "Background Workers" },
  cron_jobs: { label: "Cron Jobs" },
  serverless_invocations_per_day: {
    label: "Serverless Invocations",
    unit: "per day",
  },
  serverless_function_max_duration_s: {
    label: "Function Max Duration",
    unit: "seconds",
  },
  serverless_function_max_memory_mb: {
    label: "Function Max Memory",
    unit: "MB",
  },
  edge_function_invocations_per_day: {
    label: "Edge Function Invocations",
    unit: "per day",
  },
  preview_deployments: { label: "Preview Deployments" },
  image_optimizations_per_month: {
    label: "Image Optimizations",
    unit: "per month",
  },

  // ===== GPU =====
  gpu_model: { label: "GPU Model" },
  vram_gb: { label: "VRAM", unit: "GB" },
  hours_per_week: { label: "Hours per Week" },
  max_session_hours: { label: "Max Session", unit: "hours" },
  concurrent_sessions: { label: "Concurrent Sessions" },
  preemptible: { label: "Preemptible" },
  runtime_supported: { label: "Runtimes" },
  idle_timeout_minutes: { label: "Idle Timeout", unit: "minutes" },

  // ===== AI API =====
  models: { label: "Models" },
  rpm: { label: "Requests/min" },
  rpd: { label: "Requests/day" },
  tpm: { label: "Tokens/min" },
  tpd: { label: "Tokens/day" },
  context_window: { label: "Context Window", unit: "tokens" },
  vision_supported: { label: "Vision" },
  function_calling_supported: { label: "Function Calling" },
  structured_output_supported: { label: "Structured Output" },
  audio_input_supported: { label: "Audio Input" },
  audio_output_supported: { label: "Audio Output" },
  embedding_supported: { label: "Embeddings" },
  image_generation_supported: { label: "Image Generation" },
  video_generation_supported: { label: "Video Generation" },
  openai_compatible_api: { label: "OpenAI-Compatible API" },
  free_quota_resets: { label: "Quota Resets" },
  data_used_for_training: { label: "Data Used for Training" },

  // ===== Database =====
  database_size_mb: { label: "Database Size", unit: "MB" },
  database_engine: { label: "Database Engine" },
  row_limit: { label: "Row Limit" },
  connections: { label: "Connections" },
  branching_supported: { label: "Branching" },
  point_in_time_recovery: { label: "Point-in-Time Recovery" },
  auto_pause_after_days_idle: {
    label: "Auto-Pause After Idle",
    unit: "days",
  },
  daily_backups_retention_days: { label: "Backup Retention", unit: "days" },
  realtime_supported: { label: "Realtime" },
  vector_supported: { label: "Vector Search" },
  read_replicas: { label: "Read Replicas" },

  // ===== Storage =====
  egress_gb_per_month: { label: "Egress", unit: "GB/month" },
  egress_fee: { label: "Egress Fee" },
  operations_class_a: { label: "Class A Operations" },
  operations_class_b: { label: "Class B Operations" },
  api_compatibility: { label: "API Compatibility" },
  versioning: { label: "Versioning" },
  lifecycle_rules: { label: "Lifecycle Rules" },
  presigned_urls: { label: "Presigned URLs" },
  max_object_size_gb: { label: "Max Object Size", unit: "GB" },

  // ===== Auth =====
  monthly_active_users: { label: "Monthly Active Users" },
  social_providers: { label: "Social Providers" },
  mfa_supported: { label: "MFA" },
  sso_supported: { label: "SSO" },
  webhooks_supported: { label: "Webhooks" },
  organizations_supported: { label: "Organizations" },
  seats: { label: "Seats" },

  // ===== Observability =====
  events_per_month: { label: "Events", unit: "per month" },
  log_retention_days: { label: "Log Retention", unit: "days" },
  metrics_retention_days: { label: "Metrics Retention", unit: "days" },
  traces_supported: { label: "Traces" },
  dashboards_count: { label: "Dashboards" },

  // ===== Domain =====
  free_tlds: { label: "Free TLDs" },
  dns_records_max: { label: "DNS Records Max" },
  email_forwarding_supported: { label: "Email Forwarding" },

  // ===== Learning =====
  course_count: { label: "Courses" },
  certificate_supported: { label: "Certificate Supported" },
  cost_for_certificate_usd: { label: "Cost for Certificate", unit: "USD" },
  duration_hours: { label: "Duration", unit: "hours" },

  // ===== Grant =====
  grant_amount: { label: "Grant Amount" },
  currency: { label: "Currency" },
  application_window: { label: "Application Window" },
  decision_timeline_months: { label: "Decision Timeline" },
  sectors_priority: { label: "Sectors Priority" },
  incubator_partner_required: { label: "Incubator Partner Required" },
  milestones_required: { label: "Milestones Required" },
  tranches_typical: { label: "Tranches Typical" },
  reporting_required: { label: "Reporting Required" },
  company_age_max_years: { label: "Company Age Max", unit: "years" },
  indian_subsidiary_required: { label: "Indian Subsidiary Required" },

  // ===== Accelerator =====
  investment_amount: { label: "Investment Amount" },
  investment_structure: { label: "Investment Structure" },
  equity_taken_percent: { label: "Equity Taken", unit: "%" },
  batches_per_year: { label: "Batches per Year" },
  batch_duration_weeks: { label: "Batch Duration", unit: "weeks" },
  acceptance_rate_percent: { label: "Acceptance Rate", unit: "%" },
  alumni_network_size: { label: "Alumni Network" },
  alumni_perks_value_usd: { label: "Alumni Perks Value", unit: "USD" },
  office_space: { label: "Office Space" },
  remote_supported: { label: "Remote Supported" },
  demo_day_investors_attending: { label: "Demo Day Investors" },

  // ===== Startup Credit =====
  credit_amount_usd: { label: "Credit Amount", unit: "USD" },
  duration_months: { label: "Duration", unit: "months" },
  eligible_stages: { label: "Eligible Stages" },
  eligible_age_max_years: { label: "Eligible Age Max", unit: "years" },
  requires_investor_backing: { label: "Requires Investor Backing" },
  services_eligible: { label: "Services Eligible" },
  support_included: { label: "Support Included" },
  training_credits_usd: { label: "Training Credits", unit: "USD" },
  tiers: { label: "Tiers" },

  // ===== Perk =====
  perk_value_usd: { label: "Perk Value", unit: "USD" },
  discount_percent: { label: "Discount", unit: "%" },
  free_months: { label: "Free Months" },
  eligible_user_types: { label: "Eligible User Types" },
  partner_required: { label: "Partner Required" },
  activation_method: { label: "Activation Method" },
  expiry_months: { label: "Expiry", unit: "months" },
  stacking_allowed: { label: "Stacking Allowed" },

  // ===== OSS =====
  stars: { label: "Stars" },
  license: { label: "License" },
  language: { label: "Language" },
  last_commit_date: { label: "Last Commit" },
  demo_url: { label: "Demo URL" },
  self_hosted_only: { label: "Self-Hosted Only" },
};

/** Title-Case fallback for unmapped keys. Mirrors the inline helper that
 * used to live in ProviderDetail. Kept here so both `formatLabel` and
 * any other consumer use the same fallback shape. */
export function titleCaseKey(k: string): string {
  return k
    .replace(/_/g, " ")
    .replace(/\b([a-z])/g, (_, c: string) => c.toUpperCase())
    .replace(/\bEc2\b/, "EC2")
    .replace(/\bGcp\b/, "GCP")
    .replace(/\bAws\b/, "AWS")
    .replace(/\bGpu\b/, "GPU")
    .replace(/\bCpu\b/, "CPU")
    .replace(/\bRam\b/, "RAM")
    .replace(/\bSsd\b/, "SSD")
    .replace(/\bUrl\b/, "URL")
    .replace(/\bApi\b/, "API")
    .replace(/\bSso\b/, "SSO")
    .replace(/\bMfa\b/, "MFA")
    .replace(/\bDns\b/, "DNS")
    .replace(/\bTld\b/, "TLD")
    .replace(/\bIot\b/, "IoT");
}

/** Resolve label for a canonical or ad-hoc limits key. */
export function formatLimitLabel(k: string): string {
  return LIMIT_FIELD_META[k]?.label ?? titleCaseKey(k);
}

/** Format a primitive value for display. Booleans render as Yes / No.
 * Numbers get comma-grouping. The unit (when registered for the key)
 * is appended with a single space. */
export function formatLimitValue(key: string, value: unknown): string {
  const meta = LIMIT_FIELD_META[key];
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    const num = value.toLocaleString();
    return meta?.unit ? `${num} ${meta.unit}` : num;
  }
  if (typeof value === "string") {
    // Don't double-append a unit if the value already ends with it.
    if (meta?.unit && /\d/.test(value) && !value.toLowerCase().includes(meta.unit.toLowerCase())) {
      return `${value} ${meta.unit}`;
    }
    return value;
  }
  return String(value);
}
