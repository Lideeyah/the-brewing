import "server-only";

import { cookies } from "next/headers";

const API = process.env.BREWING_API_URL ?? "http://localhost:8000";
const ADMIN_SECRET = process.env.ADMIN_SECRET ?? "";
export const ADMIN_COOKIE = "brewing_admin";

/** True when the current request carries a valid admin session cookie. */
export async function isAdminAuthed(): Promise<boolean> {
  if (!ADMIN_SECRET) return false;
  const jar = await cookies();
  return jar.get(ADMIN_COOKIE)?.value === ADMIN_SECRET;
}

/** Check a submitted password against the configured admin secret. */
export function adminPasswordValid(password: string): boolean {
  return !!ADMIN_SECRET && password === ADMIN_SECRET;
}

/** Fetch from the admin API using the shared secret (no product session). */
export async function adminApiGet<T>(path: string): Promise<T | null> {
  if (!ADMIN_SECRET) return null;
  try {
    const res = await fetch(`${API}${path}`, {
      headers: { "X-Admin-Secret": ADMIN_SECRET },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** POST to the admin API using the shared secret. Returns {ok, data|error}. */
export async function adminApiPost<T>(
  path: string,
  body: unknown,
): Promise<{ ok: true; data: T } | { ok: false; error: string }> {
  if (!ADMIN_SECRET) return { ok: false, error: "Admin not configured." };
  try {
    const res = await fetch(`${API}${path}`, {
      method: "POST",
      headers: {
        "X-Admin-Secret": ADMIN_SECRET,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = (json as { detail?: unknown }).detail;
      return { ok: false, error: typeof detail === "string" ? detail : "Request failed." };
    }
    return { ok: true, data: json as T };
  } catch {
    return { ok: false, error: "Network error." };
  }
}
