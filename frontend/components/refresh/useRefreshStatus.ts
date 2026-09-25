"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { RefreshStatus } from "@/lib/types";

const ACTIVE_POLL_MS = 5_000;
const IDLE_POLL_MS = 60_000;

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(url, init);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

function countUpdated(status: RefreshStatus["active"]): number {
  if (!status) return 0;
  return status.outcomes.filter((o) => o.status === "updated" || o.status === "new").length;
}

/** Polls refresh status; drives the router refresh on run completion. Every
 * caller is already logged in — `middleware.ts` gates the whole site, so
 * there is no separate admin session to check here. */
export function useRefreshStatus() {
  const router = useRouter();
  const [status, setStatus] = useState<RefreshStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const wasActiveRef = useRef(false);

  const pollStatus = useCallback(async () => {
    const data = await fetchJson<RefreshStatus>("/api/status");
    if (data) setStatus(data);
    return data;
  }, []);

  useEffect(() => {
    void pollStatus();
  }, [pollStatus]);

  useEffect(() => {
    const active = status?.active != null;
    const interval = setInterval(() => void pollStatus(), active ? ACTIVE_POLL_MS : IDLE_POLL_MS);

    if (wasActiveRef.current && !active && status?.last) {
      const last = status.last;
      const updated = countUpdated(last);
      setMessage(
        `Refresh ${last.status} — ${last.outcomes.length} providers, ${updated} updated. ` +
          `See /runs/${last.run_id}`,
      );
      router.refresh();
    }
    wasActiveRef.current = active;

    return () => clearInterval(interval);
  }, [status, pollStatus, router]);

  return {
    status,
    pollStatus,
    message,
    setMessage,
    activeUpdatedCount: countUpdated(status?.active ?? null),
  };
}
