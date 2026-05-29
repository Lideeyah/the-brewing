"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";

import { structureObjective } from "@/lib/actions";

export function StructureButton({ objectiveId }: { objectiveId: string }) {
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  return (
    <button
      disabled={pending}
      onClick={() =>
        startTransition(async () => {
          await structureObjective(objectiveId);
          router.refresh();
        })
      }
      className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
    >
      {pending ? (
        <>
          <Loader2 size={15} className="animate-spin" />
          Structuring…
        </>
      ) : (
        <>
          <Sparkles size={15} />
          Structure with Copilot
        </>
      )}
    </button>
  );
}
