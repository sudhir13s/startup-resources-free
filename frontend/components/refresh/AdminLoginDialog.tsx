"use client";

import { useState, type FormEvent } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

/** Passphrase dialog gating the refresh + candidate-review actions. */
export function AdminLoginDialog({
  open,
  onOpenChange,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}) {
  const [passphrase, setPassphrase] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ passphrase }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: string } | null;
        setError(body?.detail ?? "Login failed");
        return;
      }
      setPassphrase("");
      onOpenChange(false);
      onSuccess();
    } catch {
      setError("Network error — try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent side="center">
        <DialogHeader>
          <DialogTitle>Admin passphrase</DialogTitle>
          <DialogDescription>
            Refreshing data and reviewing discovered candidates requires the
            admin passphrase. It is verified server-side and never sent to
            the browser again.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-fg-muted">Passphrase</span>
            <input
              type="password"
              autoFocus
              required
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              className="h-9 rounded-md border border-border-strong bg-bg-base px-3 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
          </label>
          {error ? <p className="text-xs text-bad">{error}</p> : null}
          <Button type="submit" disabled={submitting || passphrase.length === 0}>
            {submitting ? "Verifying…" : "Continue"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
