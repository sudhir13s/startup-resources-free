import { Badge } from "@/components/ui/badge";
import type { OutcomeStatus, RunStatus } from "@/lib/types";

const RUN_STATUS_META: Record<RunStatus, { label: string; variant: "success" | "warning" | "danger" | "default" }> = {
  running: { label: "Running", variant: "default" },
  succeeded: { label: "Succeeded", variant: "success" },
  partial: { label: "Partial", variant: "warning" },
  failed: { label: "Failed", variant: "danger" },
};

const OUTCOME_STATUS_META: Record<OutcomeStatus, { label: string; variant: "success" | "warning" | "danger" | "default" | "muted" }> = {
  unchanged: { label: "Unchanged", variant: "muted" },
  updated: { label: "Updated", variant: "success" },
  new: { label: "New", variant: "default" },
  "queued-verify": { label: "Queued for verify", variant: "warning" },
  skipped: { label: "Skipped", variant: "muted" },
  failed: { label: "Failed", variant: "danger" },
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const meta = RUN_STATUS_META[status];
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}

export function OutcomeStatusBadge({ status }: { status: OutcomeStatus }) {
  const meta = OUTCOME_STATUS_META[status];
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}
