/**
 * Server-side helpers for calling the FastAPI backend.
 * Server-only: reads process.env — never import from a Client Component.
 */
import { backendAuthHeader } from "@/lib/admin";

export type QueryValue = string | number | boolean | null | undefined | string[];

export type BackendResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; detail: string };

/** Backend base URL: BACKEND_URL, else BACKEND_HOST (Render host), else localhost. */
export function resolveBackendUrl(): string {
  const explicit = process.env.BACKEND_URL?.trim();
  if (explicit) return explicit.replace(/\/+$/, "");

  const rawHost = process.env.BACKEND_HOST?.trim();
  if (rawHost) {
    const cleaned = rawHost.replace(/^https?:\/\//, "").replace(/\/+$/, "");
    // A bare Render service name has no dot; Render serves it at <name>.onrender.com.
    const fullHost = cleaned.includes(".") ? cleaned : `${cleaned}.onrender.com`;
    return `https://${fullHost}`;
  }
  return "http://localhost:8000";
}

/** Build a backend URL; array values become repeated query params. */
export function backendUrl(path: string, query: Record<string, QueryValue> = {}): string {
  const url = new URL(path, resolveBackendUrl());
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === "") continue;
    const values = Array.isArray(value) ? value : [String(value)];
    for (const item of values) url.searchParams.append(key, item);
  }
  return url.toString();
}

/** GET JSON from the backend without throwing; `revalidateSeconds: 0` disables caching. */
export async function backendGet<T>(
  path: string,
  query: Record<string, QueryValue> = {},
  revalidateSeconds = 0,
): Promise<BackendResult<T>> {
  try {
    const headers = backendAuthHeader();
    const init: RequestInit & { next?: { revalidate: number } } =
      revalidateSeconds > 0
        ? { next: { revalidate: revalidateSeconds }, headers }
        : { cache: "no-store", headers };
    const res = await fetch(backendUrl(path, query), init);
    if (!res.ok) return { ok: false, status: res.status, detail: await errorDetail(res) };
    return { ok: true, data: (await res.json()) as T };
  } catch (error) {
    return { ok: false, status: 0, detail: `Backend unreachable: ${String(error)}` };
  }
}

async function errorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}
