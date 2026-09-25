import { ExternalLink } from "lucide-react";
import { hostnameOf } from "@/lib/utils";
import { accessMethodLabel } from "@/lib/catalog/labels";
import type { Eligibility, Link as ProviderLink } from "@/lib/types";

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
      {children}
    </h3>
  );
}

/** Eligibility — summary sentence + regions + user types. */
export function EligibilitySection({
  summary,
  eligibility,
  accessMethod,
}: {
  summary: string;
  eligibility: Eligibility;
  accessMethod: string;
}) {
  return (
    <section className="flex flex-col gap-2">
      <SectionHeading>Eligibility</SectionHeading>
      <p className="text-sm leading-relaxed text-fg-muted">{summary}</p>
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-fg-subtle">
        <span>
          <span className="font-medium text-fg-muted">Regions:</span> {eligibility.regions.join(", ")}
        </span>
        {eligibility.user_types.length > 0 ? (
          <span>
            <span className="font-medium text-fg-muted">User types:</span>{" "}
            {eligibility.user_types.join(", ")}
          </span>
        ) : null}
        <span>
          <span className="font-medium text-fg-muted">Access:</span> {accessMethodLabel(accessMethod)}
        </span>
      </div>
    </section>
  );
}

/** "How to claim" — numbered, data-driven steps. No generic fallback:
 * hidden entirely when the record has no claim_steps. */
export function ClaimStepsSection({ steps }: { steps: string[] }) {
  if (steps.length === 0) return null;
  return (
    <section className="flex flex-col gap-3 rounded-md border border-border bg-bg-tile p-5">
      <SectionHeading>How to claim</SectionHeading>
      <ol className="flex flex-col gap-3">
        {steps.map((step, i) => (
          <li key={i} className="flex items-start gap-3 text-sm leading-relaxed text-fg">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/15 font-mono text-[11px] font-semibold text-accent">
              {i + 1}
            </span>
            <span className="text-fg-muted">{step}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Links & sources — record.links first, then source_urls (hostnames
 * shown), all opening in a new tab with rel="noopener noreferrer". */
export function LinksSection({ links, sourceUrls }: { links: ProviderLink[]; sourceUrls: string[] }) {
  if (links.length === 0 && sourceUrls.length === 0) return null;
  return (
    <section className="flex flex-col gap-2 rounded-md border border-border bg-bg-base p-4">
      <SectionHeading>Links &amp; sources</SectionHeading>
      <ul className="flex flex-col gap-1.5">
        {links.map((l, i) => (
          <li key={`link-${i}`}>
            <a
              href={l.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
            >
              {l.label}
              <ExternalLink className="h-3 w-3" />
            </a>
          </li>
        ))}
        {sourceUrls.map((url, i) => (
          <li key={`source-${i}`}>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-accent"
            >
              {hostnameOf(url)}
              <ExternalLink className="h-3 w-3" />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
