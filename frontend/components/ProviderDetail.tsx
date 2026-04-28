"use client";

import { ExternalLink, ArrowRight } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  CATEGORY_LABELS,
  TIER_LABELS,
  relativeTime,
  type Provider,
} from "@/lib/utils";
import { cn } from "@/lib/utils";

const CONFIDENCE_DOT: Record<Provider["parse_confidence"], string> = {
  high: "bg-ok",
  medium: "bg-warn",
  low: "bg-bad",
};

const CONFIDENCE_LABEL: Record<Provider["parse_confidence"], string> = {
  high: "High confidence",
  medium: "Medium confidence — verify yourself",
  low: "Low confidence — please verify the source",
};

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-bg-tile px-3 py-2">
      <span className="font-mono text-[9px] font-semibold uppercase tracking-wider text-fg-subtle">
        {label}
      </span>
      <span className="text-sm font-medium leading-snug text-fg break-words">
        {value}
      </span>
    </div>
  );
}

/** Pretty-print a limits-key (e.g. "ec2_instance_hours_per_month") so the
 * UI reads naturally without forcing the data shape to be perfect. */
function prettyKey(k: string): string {
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
    .replace(/\bApi\b/, "API");
}

/** Render a single limits-value: number → comma-formatted, bool → Yes/No,
 * string → as-is, array → bullet list, object → nested. */
function LimitsValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-fg-subtle">—</span>;
  }
  if (typeof value === "boolean") {
    return (
      <span className={value ? "text-ok" : "text-bad"}>
        {value ? "Yes" : "No"}
      </span>
    );
  }
  if (typeof value === "number") {
    return <span className="font-mono">{value.toLocaleString()}</span>;
  }
  if (typeof value === "string") {
    return <span>{value}</span>;
  }
  if (Array.isArray(value)) {
    return (
      <ul className="flex flex-col gap-0.5 text-fg-muted">
        {value.map((v, i) => (
          <li key={i} className="text-xs">
            • {typeof v === "string" || typeof v === "number" ? v : JSON.stringify(v)}
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    return <LimitsView limits={value as Record<string, unknown>} nested />;
  }
  return <span>{String(value)}</span>;
}

/** Render a limits dict as a key-value grid. Recursive when values are
 * objects (e.g. AWS Activate has per-service breakdowns). */
function LimitsView({
  limits,
  nested = false,
}: {
  limits: Record<string, unknown>;
  nested?: boolean;
}) {
  const entries = Object.entries(limits);
  if (entries.length === 0) return null;
  return (
    <dl
      className={cn(
        "flex flex-col gap-1.5 text-sm",
        nested ? "ml-2 mt-1 border-l-2 border-border pl-3" : "rounded-md border border-border bg-bg-tile p-3",
      )}
    >
      {entries.map(([k, v]) => (
        <div
          key={k}
          className="grid grid-cols-[max-content_1fr] items-baseline gap-x-3"
        >
          <dt className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
            {prettyKey(k)}
          </dt>
          <dd className="text-sm break-words text-fg">
            <LimitsValue value={v} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[max-content_1fr] items-baseline gap-x-4 gap-y-0">
      <dt className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
        {label}
      </dt>
      <dd className="text-sm text-fg break-words">{children}</dd>
    </div>
  );
}

/** Derive likely-useful URLs from the source URL's domain. These are
 * COMMON PATHS used by most SaaS / cloud / fund sites — they may 404 on
 * any specific provider, so we flag them as "common path" in the UI. */
function deriveHelperLinks(
  provider: Provider,
): { label: string; href: string }[] {
  let origin = "";
  try {
    origin = new URL(provider.source_url).origin;
  } catch {
    return [];
  }

  const isFund =
    provider.category === "grant" ||
    provider.category === "grants" ||
    provider.category === "accelerator" ||
    provider.category === "accelerators" ||
    provider.category === "startup-credit" ||
    provider.category === "startup-credits" ||
    provider.category === "perk" ||
    provider.category === "perks";

  if (isFund) {
    return [
      { label: "Apply", href: `${origin}/apply` },
      { label: "Eligibility / FAQ", href: `${origin}/faq` },
      { label: "Deadlines", href: `${origin}/deadlines` },
      { label: "Past winners / portfolio", href: `${origin}/portfolio` },
    ];
  }

  return [
    { label: "Pricing", href: `${origin}/pricing` },
    { label: "Sign up", href: `${origin}/signup` },
    { label: "Docs", href: `${origin}/docs` },
    { label: "Free tier details", href: `${origin}/free` },
    { label: "Status / uptime", href: `${origin.replace(/^https?:\/\//, "https://status.")}` },
  ];
}

/** Inline anchor — small, accent-colored, opens in new tab. */
function L({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-baseline gap-0.5 text-accent underline decoration-dotted underline-offset-2 hover:text-accent hover:decoration-solid"
    >
      {children}
      <ExternalLink className="h-3 w-3 self-center" />
    </a>
  );
}

/** Apply-steps generator. Returns rich JSX nodes (not strings) so each
 * step can embed inline links to the source URL + derived helper paths.
 * The branches are heuristic per category + offer_type — backend can
 * override per record once the schema carries explicit `apply_steps`. */
function buildSteps(provider: Provider): React.ReactNode[] {
  const cat = provider.category;
  const offer = provider.offer_type;
  const src = provider.source_url;

  let origin = "";
  try {
    origin = new URL(src).origin;
  } catch {
    origin = src;
  }

  if (cat === "grant" || cat === "grants") {
    return [
      <>
        Open the program page at <L href={src}>{provider.name}</L> and read the
        full eligibility section. Most grants restrict by stage (idea / MVP /
        revenue), sector (deep-tech / fintech / climate / women-led),
        geography, and registration form (DPIIT-recognized for India,
        501(c)(3) for US, etc.). Disqualifying yourself early saves months.
      </>,
      <>
        Note the application deadline + any rolling-vs-batched cadence. Some
        grants run continuous intake; others have 1–2 windows / year. Add the
        deadline to your calendar with a 4-week buffer for proposal writing.
      </>,
      <>
        Prepare the written proposal: <strong>problem statement</strong>,
        proposed <strong>solution + technical novelty</strong>,{" "}
        <strong>traction so far</strong> (revenue / users / pilots),{" "}
        <strong>milestones with timeline</strong>, and a{" "}
        <strong>budget breakdown</strong> (salaries, compute, market research,
        regulatory). Most grants reject proposals that don&apos;t tie funds to
        specific milestones.
      </>,
      <>
        Gather supporting docs: incorporation certificate, founders&apos; ID
        proofs, prior funding letters (if any), patents / publications, MoUs
        with research institutions, PoC code on GitHub. Keep them as
        named-PDFs in a single folder.
      </>,
      <>
        Submit the application via the program portal at <L href={src}>the
        program page</L>. Many grants use an external portal (e.g. Submittable,
        Startup India dashboard, MeitY portal) — sign up to that portal at
        least 48 hours before the deadline; portal logins fail at peak.
      </>,
      <>
        After submission expect 3–6 months silence. Some programs run an
        interview / pitch round before final selection. Use the wait time to
        build traction — most grants prefer founders who don&apos;t need them.
      </>,
      <>
        On approval you&apos;ll sign a milestone agreement. Funds are
        disbursed in tranches (typically 30% / 40% / 30%) against milestone
        evidence. Keep a tight log of expenses; most programs require
        utilization certificates and may audit.
      </>,
    ];
  }

  if (cat === "accelerator" || cat === "accelerators") {
    return [
      <>
        Check the application window at <L href={src}>{provider.name}</L>.
        Most run 1–2 batches per year (W and S in YC&apos;s case) with hard
        deadlines and rolling-but-prefer-early intake.
      </>,
      <>
        Watch sample applications + accepted-founder interviews if the program
        publishes them. The {origin}/blog and {origin}/founder-stories paths
        often have these. They reveal what the partners actually optimize for.
      </>,
      <>
        Prepare a <strong>60-second video pitch</strong> (founders on camera,
        no slides — just talk to the lens) +{" "}
        <strong>10-slide deck</strong> (problem, solution, market, traction,
        team, business model, ask, milestones, competition, why-you).
      </>,
      <>
        Submit the application form. Most accelerators ask for: company URL +
        demo, code repo (GitHub), pitch video, founder LinkedIn profiles,
        equity split, current cap table, prior funding, key customer
        references / letters of intent.
      </>,
      <>
        Pass through interview rounds — typically 1–3 calls. Round 1: partner
        screen (15–30 min, why you / why now). Round 2: technical or
        market deep-dive (30–60 min). Round 3 (if any): final round with
        program leadership. Practice answering &quot;what&apos;s the riskiest
        thing in your business?&quot;.
      </>,
      <>
        On selection you&apos;ll receive an offer letter. Read carefully:{" "}
        <strong>equity</strong> (typically 5–10% for $100–500k or
        SAFE), <strong>cash vs credits</strong> mix, <strong>program duration</strong>{" "}
        (12–13 weeks typical, full-time required), <strong>relocation</strong>{" "}
        (some require on-site).
      </>,
      <>
        Block your calendar for the full program duration. Demo Day at the end
        is the biggest investor-pitching moment of your life so far —
        treat the program as a 13-week sprint.
      </>,
    ];
  }

  if (cat === "startup-credit" || cat === "startup-credits") {
    return [
      <>
        Confirm eligibility at <L href={src}>{provider.name}</L>. Most credit
        programs require: company age (typically &lt; 5–10 years),{" "}
        funding stage (pre-seed to Series B), domicile (some are US-only),
        and either a referral or accredited-investor relationship (AWS
        Activate Portfolio needs a partner; GCP for Startups needs an
        accelerator / VC).
      </>,
      <>
        Sign up for the vendor&apos;s main account first if you don&apos;t
        already have one (e.g. AWS root account, GCP Console, Azure
        subscription, Notion workspace). The credit application binds to that
        account ID.
      </>,
      <>
        Visit the founder portal at <L href={src}>the program page</L> and
        start the application. You&apos;ll provide: company name + URL, founders&apos;
        identities, incorporation country, headcount, current funding stage,
        primary product description, expected monthly spend, what
        you&apos;re building.
      </>,
      <>
        Provide proof: incorporation certificate, founders&apos; government
        IDs, sometimes investor email or accelerator membership letter. Some
        programs ask for a brief technical-architecture write-up (1
        paragraph).
      </>,
      <>
        Wait for approval. Self-serve programs (AWS Activate Founders, GCP
        Start) approve within hours. Portfolio-tier programs (AWS Portfolio,
        GCP Scale, Azure Imagine) take 5–15 business days.
      </>,
      <>
        Once approved, credits apply automatically to your billing account.{" "}
        <strong>Set spending alerts</strong> at $100, $500, $1k, etc. — many
        founders blow through credits in 60 days because they don&apos;t
        budget. <strong>Tag every resource</strong> with a project label so
        post-credit cost-attribution works.
      </>,
      <>
        Mark the credit expiry on your calendar with a 60-day reminder. Most
        credits expire 12–24 months after grant and don&apos;t roll over.
        Plan migration / commitment-discount renewals before expiry.
      </>,
    ];
  }

  if (cat === "perk" || cat === "perks") {
    return [
      <>
        Open the partner page at <L href={src}>{provider.name}</L> and verify
        eligibility. Most perks gate by funded-startup status, accelerator
        membership, or .edu email. Have proof ready (cap table, accelerator
        letter, university email).
      </>,
      <>
        If the perk is delivered through a partner portal (AWS Activate
        Partners, HubSpot for Startups, Notion for Startups, etc.) you
        usually log into your existing partner account to see the perk
        catalog.
      </>,
      <>
        Click the activation link. Some perks auto-apply (Notion Plus credit
        applied to workspace); others require entering a referral code at
        checkout.
      </>,
      <>
        Activation latency: instant for self-serve perks, 24–72 hours for
        partner-vetted perks. Watch for the activation email — it goes to
        the email on the founder account, not the corporate alias.
      </>,
      <>
        Use the perk before its expiry. Most perks are time-limited (3, 6, or
        12 months). Some require active usage (don&apos;t go dormant) to
        retain.
      </>,
    ];
  }

  if (offer === "free-credits") {
    return [
      <>
        Visit <L href={src}>the credits application page</L> and start the
        form. Most credit programs ask for company info, expected use case,
        and team size.
      </>,
      <>
        Provide proof of incorporation if required. Some programs accept
        sole-proprietor / DBA; others want LLC / Pvt Ltd / C-Corp. Keep
        scanned PDFs ready.
      </>,
      <>
        A credit card may be required for verification only (no charge
        during the credit period). Use a virtual card if you want to ringfence
        risk.
      </>,
      <>
        Wait for approval — instant to several weeks depending on the
        provider. Premium tiers (e.g. enterprise credits) are gated and
        slower.
      </>,
      <>
        Once approved, credits apply to your billing account automatically.
        Set a billing alert at 50% / 80% / 100% of the credit. Watch
        the expiry — most credits expire 12–24 months after grant and
        don&apos;t roll over.
      </>,
    ];
  }

  if (offer === "free-trial") {
    return [
      <>
        Sign up at <L href={src}>{provider.name}</L> — usually email +
        password or OAuth (GitHub / Google).
      </>,
      <>
        Add a payment method. The card is held but not charged during the
        trial. Trials are typically 14–30 days; some are 7-day &quot;sandbox&quot;
        trials with limited capacity.
      </>,
      <>
        Use the service. <strong>Decide within the first 48 hours</strong>{" "}
        whether the product fits — most trial users defer the decision and
        forget to cancel.
      </>,
      <>
        Set a calendar reminder 48 hours before trial-end. Auto-conversion to
        paid is the default — cancel from the billing dashboard if you
        don&apos;t want to continue.
      </>,
      <>
        After cancellation, your data is typically retained for 30–90
        days before deletion. Export anything you need (SQL dump, S3 bucket,
        config) before the retention window expires.
      </>,
    ];
  }

  if (offer === "free-quota" || offer === "always-free") {
    return [
      <>
        Sign up at <L href={src}>{provider.name}</L>. Most providers accept
        email or GitHub / Google OAuth. Use a long-lived email — recovering
        a lost root account is painful.
      </>,
      <>
        Verify email if asked. Some providers also verify phone number to
        prevent free-tier abuse — have a number ready.
      </>,
      <>
        Create a project / workspace / API key from the provider&apos;s
        dashboard. <strong>Name it clearly</strong> (e.g.{" "}
        <code className="font-mono text-xs">myapp-prod</code>) so post-creation
        you can identify it from billing logs.
      </>,
      <>
        Read the free-tier limits from the source URL. Free quotas are
        usually denominated in: requests / month, GB egress, vCPU hours,
        token count, or build minutes. Map your expected workload to the
        limit.
      </>,
      <>
        Wire the API key / endpoint into your application. Most providers
        also offer SDK packages (npm / pip / go-mod) — prefer the SDK over
        raw HTTP for retry / auth handling.
      </>,
      <>
        Watch your usage dashboard daily for the first week. Some providers
        throttle silently when limits are hit (slow responses, no error);
        others fail loudly. You want to know which mode the provider uses
        BEFORE you ship.
      </>,
      <>
        Set a billing alert if the provider has paid tiers — accidentally
        crossing into paid usage is the most common cause of unexpected
        cloud bills.
      </>,
    ];
  }

  if (offer === "oss") {
    return [
      <>
        Open <L href={src}>the project page</L> — most are GitHub repos,
        Hugging Face spaces / models, or self-hosted documentation sites.
      </>,
      <>
        Read the LICENSE file. Common: MIT / Apache 2.0 (permissive — fine
        for commercial), GPL / AGPL (copyleft — your code may need to be
        open too if linked), BSL / SSPL (source-available, restricted
        commercial use).
      </>,
      <>
        Check the README for install instructions, requirements (CUDA /
        Python / Node version), and any model weights / dataset downloads
        needed.
      </>,
      <>
        Clone, fork, or `pip install` / `npm install` depending on the
        project type. For Hugging Face models: `transformers` library
        with the model ID is usually enough.
      </>,
      <>
        Pin the version. Use a git commit hash (not a branch name) or
        package version (not a range like `^1.0.0`) so a future upstream
        change can&apos;t break your build.
      </>,
      <>
        Watch the issue tracker + releases. Most active projects ship
        breaking changes in major versions (semver). Subscribe to Releases
        on GitHub.
      </>,
    ];
  }

  return [
    <>
      Visit <L href={src}>{provider.name}</L> and read the offer page in
      full.
    </>,
    <>
      Note the eligibility, quotas, and any rate / time limits applicable
      to your use case.
    </>,
    <>
      Sign up. Most providers require email verification.
    </>,
    <>
      Confirm activation in the provider&apos;s dashboard before relying on
      the resource in production.
    </>,
  ];
}

export function ProviderDetail({
  provider,
  open,
  onOpenChange,
}: {
  provider: Provider | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!provider) return null;
  const initial = provider.name.charAt(0).toUpperCase();
  const steps = buildSteps(provider);
  const helperLinks = deriveHelperLinks(provider);
  const isFund =
    provider.category === "grant" ||
    provider.category === "grants" ||
    provider.category === "accelerator" ||
    provider.category === "accelerators" ||
    provider.category === "startup-credit" ||
    provider.category === "startup-credits" ||
    provider.category === "perk" ||
    provider.category === "perks";

  let domain = "";
  try {
    domain = new URL(provider.source_url).hostname.replace(/^www\./, "");
  } catch {
    domain = provider.source_url;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        side="center"
        aria-describedby={`detail-${provider.id}`}
        className="max-w-screen-2xl w-[92vw] h-[88vh] max-h-[88vh] overflow-y-auto rounded-xl"
      >
        <DialogHeader className="border-b border-border pb-4">
          <div className="flex items-start gap-4">
            <div
              className={cn(
                "flex h-14 w-14 shrink-0 items-center justify-center rounded-md border font-mono text-xl font-semibold",
                isFund
                  ? "border-warn/40 bg-warn/10 text-warn"
                  : "border-border bg-bg-tile text-fg-muted"
              )}
            >
              {initial}
            </div>
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2 flex-wrap">
                <DialogTitle className="text-xl">{provider.name}</DialogTitle>
                <Badge variant="muted" className="capitalize">
                  {CATEGORY_LABELS[provider.category] ?? provider.category}
                </Badge>
                <Badge variant="outline" className="font-mono">
                  {provider.offer_type}
                </Badge>
                {provider.india_accessible ? (
                  <Badge variant="india">📍 Works in India</Badge>
                ) : null}
                <span className="font-mono text-[10px] text-fg-subtle">
                  {domain}
                </span>
              </div>
              <DialogDescription
                id={`detail-${provider.id}`}
                className="text-base leading-snug text-fg"
              >
                {provider.headline}
              </DialogDescription>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {provider.use_case_tiers.map((t) => (
                  <Badge key={t} variant="success" className="font-mono">
                    Fits {TIER_LABELS[t]}
                  </Badge>
                ))}
                <Badge variant="muted" className="capitalize">
                  {provider.geo_priority.replace(/-/g, " ")}
                </Badge>
              </div>
            </div>
          </div>
        </DialogHeader>

        <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
          {/* LEFT column — facts */}
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-3 gap-2">
              <StatTile label="Free quota" value={provider.quota_summary} />
              <StatTile label="Duration" value={provider.duration_summary} />
              <StatTile label="Region" value={provider.region_summary} />
            </div>

            <section className="rounded-md border border-border bg-bg-tile p-4">
              <h3 className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                Free-tier summary
              </h3>
              <p className="text-sm leading-relaxed text-fg-muted">
                {provider.free_tier_summary}
              </p>
            </section>

            <section className="flex flex-col gap-2">
              <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                Eligibility
              </h3>
              <p className="text-sm leading-relaxed text-fg-muted">
                {provider.eligibility_summary}
              </p>
            </section>

            {provider.limits && Object.keys(provider.limits).length > 0 ? (
              <section className="flex flex-col gap-2">
                <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                  Detailed limits + offerings
                </h3>
                <LimitsView limits={provider.limits} />
              </section>
            ) : null}

            {provider.restrictions ? (
              <section className="flex flex-col gap-2">
                <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                  Restrictions
                </h3>
                <p className="text-sm leading-relaxed text-fg-muted">
                  {provider.restrictions}
                </p>
              </section>
            ) : null}

            {provider.tier_fit_rationale ? (
              <section className="flex flex-col gap-2">
                <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                  Why this tier fit
                </h3>
                <p className="text-sm leading-relaxed text-fg-muted">
                  {provider.tier_fit_rationale}
                </p>
              </section>
            ) : null}

            <section className="flex flex-col gap-2">
              <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                Provider info
              </h3>
              <dl className="flex flex-col gap-2">
                <Row label="Offer type">
                  <span className="font-mono text-xs">{provider.offer_type}</span>
                </Row>
                <Row label="Category">
                  {CATEGORY_LABELS[provider.category] ?? provider.category}
                </Row>
                {provider.subcategory ? (
                  <Row label="Subcategory">{provider.subcategory}</Row>
                ) : null}
                {provider.access_method ? (
                  <Row label="Access method">
                    <span className="font-mono text-xs">
                      {provider.access_method}
                    </span>
                  </Row>
                ) : null}
                {provider.credit_amount != null ? (
                  <Row label="Credit amount">
                    <span className="font-mono text-xs">
                      {provider.currency ?? "USD"}{" "}
                      {provider.credit_amount.toLocaleString()}
                    </span>
                  </Row>
                ) : null}
                {provider.credit_duration_days != null ? (
                  <Row label="Credit duration">
                    {provider.credit_duration_days} days
                  </Row>
                ) : null}
                <Row label="Geo priority">
                  <span className="capitalize">
                    {provider.geo_priority.replace(/-/g, " ")}
                  </span>
                </Row>
                <Row label="India accessible">
                  {provider.india_accessible ? "Yes" : "No"}
                </Row>
                <Row label="Confidence">
                  <span className="inline-flex items-center gap-2">
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full",
                        CONFIDENCE_DOT[provider.parse_confidence],
                      )}
                      aria-hidden="true"
                    />
                    {CONFIDENCE_LABEL[provider.parse_confidence]}
                  </span>
                </Row>
                <Row label="Last verified">
                  {relativeTime(provider.last_verified_at)} ·{" "}
                  <span className="font-mono text-xs text-fg-subtle">
                    {provider.last_verified_at}
                  </span>
                </Row>
                <Row label="Record id">
                  <span className="font-mono text-[10px] text-fg-subtle">
                    {provider.id}
                  </span>
                </Row>
                {provider.notes ? <Row label="Notes">{provider.notes}</Row> : null}
              </dl>
            </section>

            <section className="flex flex-col gap-2 rounded-md border border-border bg-bg-base p-4">
              <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                Useful links
              </h3>
              <div className="flex flex-col gap-2">
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle shrink-0">
                    Source
                  </span>
                  <a
                    href={provider.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all text-sm text-accent hover:underline"
                  >
                    {provider.source_url}
                  </a>
                </div>
                {helperLinks.length > 0 ? (
                  <>
                    <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
                      Common paths on {domain} (may not exist — verify)
                    </div>
                    <ul className="flex flex-wrap gap-2">
                      {helperLinks.map((l) => (
                        <li key={l.href}>
                          <a
                            href={l.href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-md border border-border bg-bg-tile px-2.5 py-1 text-xs font-medium text-fg-muted hover:bg-bg-surface hover:text-fg"
                          >
                            {l.label}
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </div>
            </section>
          </div>

          {/* RIGHT column — apply steps */}
          <div className="flex flex-col gap-4">
            <section className="flex flex-col gap-3 rounded-md border border-border bg-bg-tile p-5">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                  How to {isFund ? "apply" : "claim"} — step-by-step
                </h3>
                <a
                  href={provider.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(
                    "inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors shrink-0",
                    isFund
                      ? "border border-warn/40 bg-warn/10 text-warn hover:bg-warn/15"
                      : "border border-accent/40 bg-accent/10 text-accent hover:bg-accent/15",
                  )}
                >
                  {isFund ? "Apply now" : "Open source"}
                  <ArrowRight className="h-3.5 w-3.5" />
                </a>
              </div>
              <ol className="flex flex-col gap-4">
                {steps.map((step, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-3 text-sm leading-relaxed text-fg"
                  >
                    <span
                      className={cn(
                        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-semibold",
                        isFund
                          ? "bg-warn/15 text-warn"
                          : "bg-accent/15 text-accent",
                      )}
                    >
                      {idx + 1}
                    </span>
                    <span className="text-fg-muted">{step}</span>
                  </li>
                ))}
              </ol>
              <p className="mt-2 text-[11px] italic leading-snug text-fg-subtle">
                These are typical steps based on the offer type. Always verify
                exact eligibility, deadlines, and required documents on{" "}
                <L href={provider.source_url}>the source page</L> — programs
                change frequently.
              </p>
            </section>

            <section className="flex flex-col gap-2 rounded-md border border-border bg-bg-base p-4">
              <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                What you&apos;ll need
              </h3>
              <ul className="flex flex-col gap-1.5 text-sm text-fg-muted">
                {isFund ? (
                  <>
                    <li>• Incorporation certificate / company registration</li>
                    <li>• Founder identity proof (passport / national ID)</li>
                    <li>
                      • Pitch deck (10 slides) + 60-sec founder video where
                      requested
                    </li>
                    <li>
                      • Bank account in the company&apos;s name (for fund
                      disbursement)
                    </li>
                    <li>• Cap table + most recent funding letter (if any)</li>
                    <li>
                      • Sometimes: investor / accelerator referral, technical
                      write-up, prior PoCs / publications, customer letters of
                      intent
                    </li>
                  </>
                ) : (
                  <>
                    <li>• Email address (preferably company / founder email)</li>
                    <li>• GitHub or Google OAuth for sign-up shortcuts</li>
                    <li>
                      • Phone number (some providers verify phone to prevent
                      free-tier abuse)
                    </li>
                    <li>
                      • Payment method on file (for trials only — held, not
                      charged)
                    </li>
                    <li>
                      • Sometimes: domain ownership proof, .edu email,
                      accelerator membership, investor referral
                    </li>
                  </>
                )}
              </ul>
            </section>

            <section className="flex flex-col gap-2 rounded-md border border-border bg-bg-base p-4">
              <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                Common pitfalls
              </h3>
              <ul className="flex flex-col gap-1.5 text-sm text-fg-muted">
                {isFund ? (
                  <>
                    <li>
                      • Missing the deadline by a few hours — portal logins
                      fail at peak; always submit 24+ hours early
                    </li>
                    <li>
                      • Not tying funds to specific milestones in the
                      proposal — generic asks get rejected
                    </li>
                    <li>
                      • Poor expense bookkeeping post-approval — most programs
                      audit and require utilization certificates
                    </li>
                  </>
                ) : (
                  <>
                    <li>
                      • Forgetting to set spending alerts — credit overruns
                      become real bills overnight
                    </li>
                    <li>
                      • Not noting credit / trial expiry — auto-conversion to
                      paid is the default
                    </li>
                    <li>
                      • Hard-coding API keys in client code instead of env vars —
                      free tiers do get rate-limited per-key
                    </li>
                  </>
                )}
              </ul>
            </section>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
