"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import {
  ADMIN_COOKIE,
  adminApiPost,
  adminPasswordValid,
} from "@/lib/admin-server";

const ADMIN_SECRET = process.env.ADMIN_SECRET ?? "";

export async function adminLogin(formData: FormData): Promise<void> {
  const password = (formData.get("password") as string | null)?.trim() ?? "";
  if (!adminPasswordValid(password)) {
    redirect("/admin/login?error=1");
  }
  const jar = await cookies();
  jar.set(ADMIN_COOKIE, ADMIN_SECRET, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/admin",
    maxAge: 60 * 60 * 8, // 8 hours
  });
  redirect("/admin");
}

export async function adminLogout(): Promise<void> {
  const jar = await cookies();
  jar.delete(ADMIN_COOKIE);
  redirect("/admin/login");
}

type WithdrawState =
  | { ok: true; message: string; explorer?: string }
  | { ok: false; message: string };

export async function withdrawFees(formData: FormData): Promise<WithdrawState> {
  const dest = (formData.get("destination_address") as string | null)?.trim() ?? "";
  const amount = (formData.get("amount_usdc") as string | null)?.trim() || undefined;
  if (!dest) return { ok: false, message: "Destination address is required." };
  const res = await adminApiPost<{
    ok: boolean;
    amount_usdc: string;
    explorer_url?: string | null;
    message?: string | null;
  }>("/admin/fee-wallet/withdraw", {
    destination_address: dest,
    amount_usdc: amount,
  });
  if (!res.ok) return { ok: false, message: res.error };
  if (!res.data.ok) return { ok: false, message: res.data.message ?? "Withdrawal failed." };
  revalidatePath("/admin");
  return {
    ok: true,
    message: `Withdrew ${res.data.amount_usdc} USDC.`,
    explorer: res.data.explorer_url ?? undefined,
  };
}
