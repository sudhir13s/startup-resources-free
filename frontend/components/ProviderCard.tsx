"use client";

import { useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TIER_LABELS, relativeTime, type Provider } from "@/lib/utils";
import { cn } from "@/lib/utils";

const CATEGORY_LABELS: Record<string, string> = {
  cloud: "Cloud / Hosting",
  gpu: "GPU / Compute",
  "ai-api": "AI API",
  database: "Database",
  storage: "Storage",
  observability: "Observability",
  "startup-credit": "Startup Credit",
  grant: "Grant",
  accelerator: "Accelerator",
  oss: "Open Source",
};

const CONFIDENCE_DOT: Record<Provider["parse_confidence"], string> = {
  high: "bg-emerald-400",
  medium: "bg-amber-400",
  low: "bg-rose-400",
};

const CONFIDENCE_LABEL: Record<Provider["parse_confidence"], string> = {
  high: "Verified high-confidence",
  medium: "Medium confidence — verify yourself",
  low: "Low confidence — please verify the source",
};

export function ProviderCard({ provider }: { provider: Provider }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <CardTitle>{provider.name}</CardTitle>
            <span
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                CONFIDENCE_DOT[provider.parse_confidence]
              )}
              aria-label={CONFIDENCE_LABEL[provider.parse_confidence]}
              title={CONFIDENCE_LABEL[provider.parse_confidence]}
            />
          </div>
          <CardDescription>{provider.headline}</CardDescription>
        </div>
        <Badge variant="muted">
          {CATEGORY_LABELS[provider.category] ?? provider.category}
        </Badge>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        <p className="text-sm leading-relaxed text-white/80">
          {provider.free_tier_summary}
        </p>

        <div className="flex flex-wrap gap-1.5">
          {provider.use_case_tiers.map((t) => (
            <Badge key={t} variant="default" className="font-mono">
              {TIER_LABELS[t]}
            </Badge>
          ))}
          {provider.india_accessible ? (
            <Badge variant="india" aria-label="Works in India">
              Works in India
            </Badge>
          ) : null}
        </div>

        {expanded ? (
          <div className="rounded-md border border-bg-subtle bg-bg-base/60 p-3 text-xs text-white/70">
            <dl className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-wide text-white/40">
                  Geo priority
                </dt>
                <dd>{provider.geo_priority}</dd>
              </div>
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-wide text-white/40">
                  Parse confidence
                </dt>
                <dd>{provider.parse_confidence}</dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="font-mono text-[10px] uppercase tracking-wide text-white/40">
                  Source
                </dt>
                <dd>
                  <a
                    href={provider.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all text-accent hover:underline"
                  >
                    {provider.source_url}
                  </a>
                </dd>
              </div>
              {provider.notes ? (
                <div className="sm:col-span-2">
                  <dt className="font-mono text-[10px] uppercase tracking-wide text-white/40">
                    Notes
                  </dt>
                  <dd>{provider.notes}</dd>
                </div>
              ) : null}
            </dl>
          </div>
        ) : null}
      </CardContent>

      <CardFooter>
        <span className="font-mono text-[10px] text-white/40">
          Verified {relativeTime(provider.last_verified_at)}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-controls={`provider-${provider.id}-detail`}
          >
            <ChevronDown
              className={cn(
                "h-4 w-4 transition-transform",
                expanded ? "rotate-180" : ""
              )}
            />
            {expanded ? "Less" : "More"}
          </Button>
          <Button asChild variant="ghost" size="sm">
            <a
              href={provider.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="h-4 w-4" />
              Visit
            </a>
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
