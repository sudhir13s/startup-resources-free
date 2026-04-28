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

/** Heuristic apply-steps based on category + offer_type. The schema does not
 * yet carry an explicit `apply_steps` field; this branches on the data we
 * have so the user sees actionable guidance. Backend can override per record
 * later. */
function applySteps(provider: Provider): string[] {
  const cat = provider.category;
  const offer = provider.offer_type;

  if (cat === "grant" || cat === "grants") {
    return [
      "Read the eligibility section carefully — most grants require a specific stage, sector, or geography.",
      "Prepare a written proposal: problem, solution, traction so far, milestones, budget breakdown.",
      "Gather supporting docs (incorporation, founders' IDs, prior funding letters if any, technical write-up).",
      "Submit the application at the source URL. Many grants have an application window — check the deadline.",
      "Expect 3–6 months for decision. Some grants run interview / pitch rounds before final selection.",
      "If approved, you'll sign a milestone agreement. Funds are disbursed in tranches against milestones, with periodic reporting.",
    ];
  }

  if (cat === "accelerator" || cat === "accelerators") {
    return [
      "Check the application window at the source URL — most accelerators run 1–2 batches per year with hard deadlines.",
      "Prepare a 60-second video pitch + a deck (problem, solution, team, traction, ask).",
      "Submit the application form. Some accelerators ask for code samples, customer references, or a working demo.",
      "Pass through interview rounds — typically 1–3 calls with partners and / or alumni.",
      "If selected, you'll get an offer letter outlining equity (if any), cash / credit terms, and program duration.",
      "Batch starts on a fixed date — block 3 months for the program (most are 12–13 weeks, full-time commitment).",
    ];
  }

  if (cat === "startup-credit" || cat === "startup-credits") {
    return [
      "Confirm your startup meets the program's bar (age limit, funding stage, investor portfolio, geography).",
      "Sign up for the vendor's main account first if you don't already have one.",
      "Apply through the founder / startup portal at the source URL — answer the company-info questionnaire honestly.",
      "Provide proof of incorporation + founder identity. Some programs require an investor / accelerator referral code.",
      "Wait for approval — usually 5–10 business days. Some programs (AWS Activate Founders, GCP Start) approve within hours.",
      "Once approved, credits are applied to your billing account automatically. Monitor the expiry date — credits don't roll over.",
    ];
  }

  if (cat === "perk" || cat === "perks") {
    return [
      "Verify you meet eligibility — most perks require a funded startup, .edu email, or accelerator portfolio status.",
      "Have proof ready (cap table, accelerator membership letter, or .edu email).",
      "Apply via the partner portal at the source URL.",
      "Activation is usually instant or within 24 hours.",
      "Use the perk before its expiry — most perks are time-limited (12 months typical).",
    ];
  }

  if (offer === "free-credits") {
    return [
      "Visit the source URL and start the credit application form.",
      "Provide company / project info (incorporation, team size, what you'll build).",
      "Some programs require a credit card or proof of incorporation; have these ready.",
      "Wait for approval — varies from instant to several weeks depending on the provider.",
      "Once approved, credits are applied to your billing account. Monitor expiry — most credits expire 12–24 months after grant.",
    ];
  }

  if (offer === "free-trial") {
    return [
      "Sign up at the source URL — usually requires email + password.",
      "Add a payment method. You won't be charged during the trial, but the card is held for post-trial billing.",
      "Use the service during the trial window (typically 14–30 days).",
      "Set a calendar reminder to cancel before the trial ends if you don't intend to continue — auto-conversion is the default.",
      "After cancellation, your data may be retained for 30–90 days before deletion.",
    ];
  }

  if (offer === "free-quota" || offer === "always-free") {
    return [
      "Sign up at the source URL — most providers accept email + GitHub / Google OAuth.",
      "Verify email if required.",
      "Create a project / API key from the dashboard.",
      "Start using the free quota — most providers track usage in real time.",
      "Watch your quota dashboard. Some providers throttle silently when limits are hit; others fail loudly.",
    ];
  }

  if (offer === "oss") {
    return [
      "Visit the source URL — most are GitHub repos, Hugging Face spaces, or model weights.",
      "Read the LICENSE file — OSS licenses vary (MIT, Apache 2.0, GPL, AGPL — pick what fits your use).",
      "Clone, fork, or download depending on the project type.",
      "Follow the project's README for setup. Most OSS projects have an issue tracker for help.",
    ];
  }

  return [
    "Visit the source URL.",
    "Read the terms, eligibility, and any rate / quota limits.",
    "Sign up — most providers require email verification.",
    "Confirm activation in the provider's dashboard before relying on the resource.",
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
  const steps = applySteps(provider);
  const isFund =
    provider.category === "grant" ||
    provider.category === "grants" ||
    provider.category === "accelerator" ||
    provider.category === "accelerators" ||
    provider.category === "startup-credit" ||
    provider.category === "startup-credits" ||
    provider.category === "perk" ||
    provider.category === "perks";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        side="center"
        aria-describedby={`detail-${provider.id}`}
        // Big modal: spans most of the screen, centered. Esc + X close.
        // Overrides the small max-w-lg base in the Dialog primitive
        // (tailwind-merge resolves max-w-screen-2xl as the winning util).
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

            <section className="flex flex-col gap-2">
              <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                Provider info
              </h3>
              <dl className="flex flex-col gap-2">
                <Row label="Offer type">
                  <span className="font-mono text-xs">{provider.offer_type}</span>
                </Row>
                <Row label="Geo priority">
                  <span className="capitalize">
                    {provider.geo_priority.replace(/-/g, " ")}
                  </span>
                </Row>
                <Row label="Confidence">
                  <span className="inline-flex items-center gap-2">
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full",
                        CONFIDENCE_DOT[provider.parse_confidence]
                      )}
                      aria-hidden="true"
                    />
                    {CONFIDENCE_LABEL[provider.parse_confidence]}
                  </span>
                </Row>
                <Row label="Verified">
                  {relativeTime(provider.last_verified_at)}
                </Row>
                <Row label="Source">
                  <a
                    href={provider.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 break-all text-accent hover:underline"
                  >
                    {provider.source_url}
                    <ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                </Row>
                {provider.notes ? <Row label="Notes">{provider.notes}</Row> : null}
              </dl>
            </section>
          </div>

          {/* RIGHT column — apply steps */}
          <div className="flex flex-col gap-4">
            <section className="flex flex-col gap-3 rounded-md border border-border bg-bg-tile p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                  How to {isFund ? "apply" : "claim"} — typical steps
                </h3>
                <a
                  href={provider.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(
                    "inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                    isFund
                      ? "border border-warn/40 bg-warn/10 text-warn hover:bg-warn/15"
                      : "border border-accent/40 bg-accent/10 text-accent hover:bg-accent/15"
                  )}
                >
                  {isFund ? "Apply now" : "Open source"}
                  <ArrowRight className="h-3.5 w-3.5" />
                </a>
              </div>
              <ol className="flex flex-col gap-3">
                {steps.map((step, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-3 text-sm leading-snug text-fg"
                  >
                    <span
                      className={cn(
                        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-semibold",
                        isFund
                          ? "bg-warn/15 text-warn"
                          : "bg-accent/15 text-accent"
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
                the exact process on the source page — programs change their
                eligibility, deadlines, and required documents frequently.
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
                    <li>• Pitch deck or written proposal</li>
                    <li>• Bank account in the company&apos;s name (for disbursement)</li>
                    <li>
                      • Sometimes: investor / accelerator referral, prior funding letters,
                      technical write-up
                    </li>
                  </>
                ) : (
                  <>
                    <li>• Email address (preferably company / founder email)</li>
                    <li>• GitHub or Google OAuth for sign-up shortcuts</li>
                    <li>• Payment method on file (for trials only — not charged)</li>
                    <li>
                      • Sometimes: domain ownership proof, .edu email, accelerator
                      membership
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
