"use client";

import { useEffect, useState } from "react";
import { categoryLabel } from "@/lib/catalog/labels";
import type { ProviderDetailResponse } from "@/lib/types";

/** Fetches `/api/providers?id=<id>` client-side to show related offers
 * from the same vendor + a version-history count. Renders nothing while
 * loading or on failure — this is supplementary context, not blocking. */
export function RelatedOffers({ providerId }: { providerId: string }) {
  const [detail, setDetail] = useState<ProviderDetailResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setDetail(null);
    setFailed(false);
    const ctrl = new AbortController();
    fetch(`/api/providers?id=${encodeURIComponent(providerId)}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: ProviderDetailResponse) => setDetail(data))
      .catch(() => setFailed(true));
    return () => ctrl.abort();
  }, [providerId]);

  if (failed) return null;
  if (!detail) {
    return (
      <p className="text-xs text-fg-subtle" role="status" aria-live="polite">
        Loading related offers…
      </p>
    );
  }
  if (detail.related.length === 0 && detail.history.length === 0) return null;

  return (
    <section className="flex flex-col gap-2">
      <h3 className="font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
        Related &amp; history
      </h3>
      {detail.history.length > 0 ? (
        <p className="text-xs text-fg-subtle">
          {detail.history.length} recorded version{detail.history.length === 1 ? "" : "s"} in history.
        </p>
      ) : null}
      {detail.related.length > 0 ? (
        <ul className="flex flex-col gap-1.5">
          {detail.related.map((r) => (
            <li key={r.provider_id} className="flex items-center gap-2 text-sm text-fg-muted">
              <span className="font-medium text-fg">{r.name}</span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-fg-subtle">
                {categoryLabel(r.category)}
              </span>
              <span className="text-fg-subtle">·</span>
              <span className="font-mono text-xs">{r.offer_type}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
