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
