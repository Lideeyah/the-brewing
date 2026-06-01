import Link from "next/link";
import {
  ArrowRight,
  Workflow,
  ShieldCheck,
  CheckSquare,
  DollarSign,
} from "lucide-react";

import { OnboardingStepper } from "@/components/onboarding/stepper";

const CARDS = [
  {
    icon: Workflow,
    title: "Coordinate",
    body: "Express intent. The Copilot structures the workflow, SLA & settlement.",
  },
  {
    icon: ShieldCheck,
    title: "Escrow",
    body: "Capital locks per objective before any execution begins.",
  },
  {
    icon: CheckSquare,
    title: "Validate",
    body: "An identity independent of the executor checks evidence.",
  },
  {
    icon: DollarSign,
    title: "Settle",
    body: "A human decision releases or slashes — recorded on-chain.",
  },
];

// Ungated by design: orientation is a one-time intro shown right after the
// treasury is activated. The onboarding gate is already satisfied here.
export default function OnboardingOrientationPage() {
  return (
    <>
      <OnboardingStepper current={4} />
      <div className="rounded-[16px] border border-border bg-surface p-6">
        <h1 className="text-[18px] font-semibold tracking-tight text-foreground">
          How coordination works here
        </h1>
        <p className="mt-1.5 text-[13px] leading-relaxed text-secondary">
          One loop governs every objective: intent becomes governed execution,
          capital is escrowed, validated independently, then settled or slashed.
        </p>

        <div className="mt-5 grid grid-cols-2 gap-3">
          {CARDS.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-xl border border-border bg-background p-3.5"
            >
              <div className="mb-2.5 grid h-7 w-7 place-items-center rounded-lg border border-border-strong bg-elevated text-accent">
                <Icon size={14} />
              </div>
              <div className="text-[12.5px] font-semibold text-foreground">
                {title}
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-muted">
                {body}
              </p>
            </div>
          ))}
        </div>

        <Link
          href="/dashboard"
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-foreground px-4 py-2.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90"
        >
          Enter Mission Control <ArrowRight size={15} />
        </Link>
        <p className="mt-2.5 text-center text-[11px] text-muted">
          Orientation is a one-time intro — you won&apos;t see it again.
        </p>
      </div>
    </>
  );
}
