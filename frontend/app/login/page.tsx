import type { Metadata } from "next";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Sign in",
};

export const dynamic = "force-dynamic";

export default function LoginPage({
  searchParams,
}: {
  searchParams?: { next?: string };
}) {
  const next = searchParams?.next ?? "/resources";

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-base px-4 text-fg">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-md bg-accent text-lg font-bold text-accent-fg">
            R
          </div>
          <div className="flex flex-col gap-1">
            <h1 className="text-lg font-semibold tracking-tight text-fg">
              Sign in to ResourceOS
            </h1>
            <p className="text-sm text-fg-muted">
              Free-tier resources for founders, ranked by project stage.
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-bg-surface p-6 shadow-sm">
          <LoginForm next={next} />
        </div>
      </div>
    </div>
  );
}
