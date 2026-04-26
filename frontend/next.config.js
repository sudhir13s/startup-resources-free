/** @type {import('next').NextConfig} */
//
// IMPORTANT: do NOT use the `env:` block to expose backend env vars.
// `next.config.js#env` is INLINED AT BUILD TIME — it freezes whatever
// value was set during `next build`, including the localhost fallback,
// and Server Components then read that frozen string instead of the
// runtime env. We use Server Components (page.tsx, route handlers)
// which already have direct access to `process.env` at request time.
// `resolveBackendUrl()` in lib/utils.ts reads BACKEND_URL / BACKEND_HOST
// fresh on every server boot, so Render env-var changes take effect on
// the next deploy without rebuilding the container.
//
// `NEXT_PUBLIC_*` vars stay readable on the client without an `env:`
// block — Next.js inlines those automatically by prefix convention.
const nextConfig = {
  reactStrictMode: true,
  // No `output:` field — Render runs `npm run start` (= `next start`),
  // which does NOT support `output: "standalone"` (would print a
  // warning + bypass standalone artifacts). Drop it; default output
  // is correct for `next start`.
};

module.exports = nextConfig;
