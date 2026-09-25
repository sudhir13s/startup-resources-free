"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

/** True only for a same-site relative path ("/resources", "/runs/abc?x=1") —
 * rejects absolute ("https://evil.example") and protocol-relative ("//evil.example")
 * targets so `next` can never redirect off-site. */
function isSafeNextPath(next: string): boolean {
  return next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\");
}

export function LoginForm({ next }: { next: string }) {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const destination = isSafeNextPath(next) ? next : "/resources";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: string } | null;
        setError(body?.detail ?? "Login failed");
        return;
      }
      router.push(destination);
      router.refresh();
    } catch {
      setError("Network error — try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-fg-muted">Username</span>
        <input
          type="text"
          name="username"
          autoComplete="username"
          autoFocus
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="h-10 rounded-md border border-border-strong bg-bg-base px-3 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-accent"
        />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-fg-muted">Password</span>
        <input
          type="password"
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="h-10 rounded-md border border-border-strong bg-bg-base px-3 text-sm text-fg outline-none focus-visible:ring-2 focus-visible:ring-accent"
        />
      </label>
      {error ? (
        <p role="alert" className="text-xs text-bad">
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={submitting || !username || !password} className="mt-1">
        {submitting ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
