"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Candidate } from "@/lib/types";

/**
 * Approve/reject actions require only a valid site-login session —
 * `middleware.ts` already gates every `/api/*` request. A 401 here means
 * the session expired between page load and this click, so we send the
 * user back to `/login` rather than showing an inline login dialog.
 */
export function CandidateCard({
  candidate,
  onResolved,
}: {
  candidate: Candidate;
  onResolved: (id: string, status: Candidate["status"]) => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAction(action: "approve" | "reject") {
    setBusy(action);
    setError(null);
    try {
      const res = await fetch(`/api/admin/candidates/${candidate.candidate_id}/${action}`, {
        method: "POST",
      });
      if (res.status === 401) {
        router.push(`/login?next=${encodeURIComponent("/candidates")}`);
        return;
      }
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: string } | null;
        setError(body?.detail ?? `Failed to ${action}`);
        return;
      }
      onResolved(candidate.candidate_id, action === "approve" ? "approved" : "rejected");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <a
          href={candidate.url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-fg hover:text-accent hover:underline"
        >
          {candidate.title || candidate.domain}
        </a>
        <span className="font-mono text-[10px] text-fg-subtle">{candidate.domain}</span>
      </div>
      <p className="text-xs text-fg-muted">{candidate.snippet}</p>
      <div className="flex flex-wrap items-center gap-1.5">
        {candidate.category_guess ? (
          <Badge variant="outline">{candidate.category_guess}</Badge>
        ) : null}
        <Badge variant="muted" className="font-mono">
          score {candidate.score.toFixed(2)}
        </Badge>
        <Badge variant="muted">via {candidate.found_via}</Badge>
      </div>
      <p className="text-xs text-fg-subtle">{candidate.reason}</p>

      {candidate.status === "pending" ? (
        <div className="mt-1 flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={() => void handleAction("approve")}
            disabled={busy !== null}
          >
            {busy === "approve" ? "Approving…" : "Approve"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void handleAction("reject")}
            disabled={busy !== null}
          >
            {busy === "reject" ? "Rejecting…" : "Reject"}
          </Button>
        </div>
      ) : (
        <Badge variant={candidate.status === "approved" ? "success" : "danger"} className="w-fit">
          {candidate.status}
        </Badge>
      )}
      {error ? <p className="text-xs text-bad">{error}</p> : null}
    </div>
  );
}
