/**
 * Backend auth header for calls to the FastAPI backend — server-only, Node
 * runtime (uses `node:crypto`; never import from a Client Component or
 * from Edge-runtime code such as `middleware.ts`).
 *
 * A single static key derived from `RESOURCEOS_PASSWORD` is sent as
 * `X-ResourceOS-Key` on every backend call. This mirrors `api/auth.py`
 * exactly: both sides compute
 * `hex HMAC-SHA256(key=RESOURCEOS_PASSWORD, msg="resourceos-api")`.
 * The raw password itself is never sent over the wire and never logged.
 */
import { createHmac } from "node:crypto";

const API_KEY_MESSAGE = "resourceos-api";

/** Reads RESOURCEOS_PASSWORD; null when unset (the backend is then unreachable). */
function getBackendPassword(): string | null {
  const password = process.env.RESOURCEOS_PASSWORD;
  return password && password.length > 0 ? password : null;
}

/** The `X-ResourceOS-Key` header every backend call must carry. Empty object
 * when `RESOURCEOS_PASSWORD` is unset, so a fetch with `...backendAuthHeader()`
 * just omits the header (the backend then answers 503). */
export function backendAuthHeader(): Record<string, string> {
  const password = getBackendPassword();
  if (!password) return {};
  const key = createHmac("sha256", password).update(API_KEY_MESSAGE).digest("hex");
  return { "X-ResourceOS-Key": key };
}

/** True when RESOURCEOS_PASSWORD is configured (the backend is reachable). */
export function isBackendConfigured(): boolean {
  return getBackendPassword() !== null;
}
