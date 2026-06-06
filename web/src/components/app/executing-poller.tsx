"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * While an objective is EXECUTING, deliverables are generated in a background
 * task on the API. Refresh the route on an interval so the page advances to
 * UNDER_AUDIT (with results) on its own, without the operator reloading.
 */
export function ExecutingPoller({ active }: { active: boolean }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => router.refresh(), 4000);
    return () => clearInterval(id);
  }, [active, router]);
  return null;
}
