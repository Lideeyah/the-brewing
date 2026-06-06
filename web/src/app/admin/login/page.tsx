import { redirect } from "next/navigation";

import { adminLogin } from "@/lib/admin-actions";
import { isAdminAuthed } from "@/lib/admin-server";

export default async function AdminLoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  if (await isAdminAuthed()) redirect("/admin");
  const { error } = await searchParams;

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <p className="font-operational text-[11px] uppercase tracking-[0.2em] text-muted">
            Brewing
          </p>
          <h1 className="mt-1 text-[18px] font-semibold tracking-tight text-foreground">
            Admin console
          </h1>
          <p className="mt-1 text-[12px] text-muted">
            Operator access only. Separate from the product.
          </p>
        </div>
        <form
          action={adminLogin}
          className="space-y-3 rounded-xl border border-border bg-surface p-5"
        >
          <div>
            <label className="mb-1.5 block font-operational text-[11px] uppercase tracking-wider text-muted">
              Admin password
            </label>
            <input
              name="password"
              type="password"
              required
              autoFocus
              className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-[13px] text-foreground focus:border-border-strong focus:outline-none"
            />
          </div>
          {error && (
            <p className="text-[12px] text-failure">Incorrect admin password.</p>
          )}
          <button
            type="submit"
            className="w-full rounded-lg bg-foreground px-4 py-2.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90"
          >
            Enter
          </button>
        </form>
      </div>
    </div>
  );
}
