"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ADMIN_COOKIE, adminPasswordValid } from "@/lib/admin-server";

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
