"use client";

import { useFormStatus } from "react-dom";
import { ArrowRight, Loader2 } from "lucide-react";

import { activateOnboarding } from "@/lib/actions";

function ActivateButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex w-full items-center justify-center gap-2 rounded-lg bg-foreground px-4 py-2.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
    >
      {pending ? (
        <Loader2 size={15} className="animate-spin" />
      ) : (
        <>
          Activate treasury &amp; enter Brewing <ArrowRight size={15} />
        </>
      )}
    </button>
  );
}

export function ActivateForm() {
  return (
    <form action={activateOnboarding}>
      <ActivateButton />
    </form>
  );
}
