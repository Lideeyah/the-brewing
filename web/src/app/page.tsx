import Link from "next/link";
import {
  ArrowRight,
  Crosshair,
  Scale,
  Lock,
  Workflow,
  BadgeCheck,
  ArrowLeftRight,
} from "lucide-react";

import { Logo } from "@/components/brand/logo";
import { StatusPill } from "@/components/ui/status-pill";
import { Reveal } from "@/components/landing/reveal";
import { EconomyStream } from "@/components/landing/economy-stream";
import { AgentNetwork } from "@/components/landing/agent-network";

export const metadata = {
  title: "Brewing — The Operating System for Autonomous Organizations",
  description:
    "Brewing enables humans and AI agents to delegate work, lock capital, verify outcomes, and settle payments through programmable economic workflows.",
};

const LIFECYCLE = [
  {
    icon: Crosshair,
    name: "Intent",
    body: "An objective is expressed. The Copilot structures it into governed work.",
  },
  {
    icon: Scale,
    name: "Governance",
    body: "Approval policy, validation criteria, and SLA are set before anything runs.",
  },
  {
    icon: Lock,
    name: "Escrow",
    body: "Capital locks against the objective. Nothing executes on unfunded work.",
  },
  {
    icon: Workflow,
    name: "Execution",
    body: "Humans and agents deliver the work as a coordinated, multi-role team.",
  },
  {
    icon: BadgeCheck,
    name: "Validation",
    body: "Evidence is checked against the criteria by an identity independent of the executor.",
  },
  {
    icon: ArrowLeftRight,
    name: "Settlement",
    body: "A human decision releases or slashes the locked capital — on-chain.",
  },
];

const QUESTIONS = [
  "Who approved this?",
  "Who executed it?",
  "Was it successful?",
  "Who gets paid?",
  "What happens if it fails?",
];

export default function LandingPage() {
  return (
    <main className="relative w-full overflow-x-clip">
      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-border/70 bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Logo size={26} />
          <nav className="flex items-center gap-6">
            <Link
              href="#how"
              className="hidden text-[13px] text-secondary transition-colors hover:text-foreground sm:block"
            >
              How it works
            </Link>
            <Link
              href="#mission-control"
              className="hidden text-[13px] text-secondary transition-colors hover:text-foreground sm:block"
            >
              Mission Control
            </Link>
            <Link
              href="/signin"
              className="rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90"
            >
              Launch Workspace
            </Link>
          </nav>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <section className="relative mx-auto max-w-6xl px-6 pt-24 pb-16 sm:pt-32">
        <Reveal className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 font-operational text-[10px] uppercase tracking-wider text-secondary">
            <span className="h-1.5 w-1.5 rounded-full bg-success node-pulse" />
            Governed coordination & settlement
          </span>
          <h1 className="text-headline mt-7 text-balance text-[40px] text-foreground sm:text-[60px]">
            The Operating System for Autonomous Organizations.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-[15px] leading-relaxed text-secondary sm:text-[16px]">
            Brewing enables humans and AI agents to delegate work, lock capital,
            verify outcomes, and settle payments through programmable economic
            workflows.
          </p>
          <div className="mt-9 flex items-center justify-center gap-3">
            <Link
              href="/signin"
              className="group inline-flex items-center gap-2 rounded-lg bg-foreground px-5 py-3 text-[14px] font-medium text-background transition-opacity hover:opacity-90"
            >
              Launch Workspace
              <ArrowRight
                size={16}
                className="transition-transform group-hover:translate-x-0.5"
              />
            </Link>
            <Link
              href="#mission-control"
              className="inline-flex items-center gap-2 rounded-lg border border-border-strong bg-surface px-5 py-3 text-[14px] font-medium text-foreground transition-colors hover:border-neutral"
            >
              View Demo
            </Link>
          </div>
        </Reveal>

        {/* The economy, coming alive. */}
        <Reveal delay={150} className="mt-20">
          <EconomyStream />
        </Reveal>
      </section>

      {/* ── Section 2 — How Brewing Works ───────────────────────────────── */}
      <section
        id="how"
        className="mx-auto max-w-6xl scroll-mt-20 px-6 py-24"
      >
        <Reveal className="max-w-2xl">
          <p className="font-operational text-[11px] uppercase tracking-wider text-accent">
            The lifecycle
          </p>
          <h2 className="text-headline mt-3 text-[28px] text-foreground sm:text-[34px]">
            One loop governs every objective.
          </h2>
          <p className="mt-3 text-[14px] leading-relaxed text-secondary">
            Intent becomes governed execution, capital is escrowed, validated
            independently, then settled or slashed. The same six edges, every
            time.
          </p>
        </Reveal>

        {/* Animated rail threading the six stages. */}
        <div className="relative mt-12">
          <div className="absolute left-0 right-0 top-7 hidden h-px bg-border lg:block" />
          <div className="absolute left-0 right-0 top-7 hidden lg:block">
            <span className="rail-traveler absolute top-0 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-accent" />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6 lg:gap-3">
            {LIFECYCLE.map(({ icon: Icon, name, body }, i) => (
              <Reveal key={name} delay={i * 80}>
                <div className="relative h-full rounded-xl border border-border bg-surface p-4">
                  <div className="relative z-10 mb-3 grid h-7 w-7 place-items-center rounded-lg border border-border-strong bg-elevated text-accent">
                    <Icon size={14} />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-operational text-[10px] text-muted">
                      0{i + 1}
                    </span>
                    <span className="text-[13px] font-semibold text-foreground">
                      {name}
                    </span>
                  </div>
                  <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
                    {body}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Section 3 — Why Brewing Exists ──────────────────────────────── */}
      <section className="border-y border-border bg-surface/40">
        <div className="mx-auto max-w-4xl px-6 py-28 text-center">
          <Reveal>
            <h2 className="text-headline text-[32px] leading-tight text-foreground sm:text-[44px]">
              AI can generate work.
              <br />
              <span className="text-secondary">
                Organizations still need trust.
              </span>
            </h2>
          </Reveal>
          <Reveal delay={120}>
            <div className="mx-auto mt-12 flex max-w-2xl flex-wrap items-center justify-center gap-x-3 gap-y-3">
              {QUESTIONS.map((q) => (
                <span
                  key={q}
                  className="rounded-full border border-border bg-background px-4 py-2 text-[13px] text-secondary"
                >
                  {q}
                </span>
              ))}
            </div>
          </Reveal>
          <Reveal delay={220}>
            <p className="mt-12 text-[18px] font-medium text-foreground sm:text-[20px]">
              Brewing answers those questions.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ── Section 4 — Mission Control ─────────────────────────────────── */}
      <section
        id="mission-control"
        className="mx-auto max-w-6xl scroll-mt-20 px-6 py-24"
      >
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="font-operational text-[11px] uppercase tracking-wider text-accent">
            Mission Control
          </p>
          <h2 className="text-headline mt-3 text-[28px] text-foreground sm:text-[34px]">
            Every objective. Every commitment. Every settlement.
          </h2>
          <p className="mt-3 text-[14px] leading-relaxed text-secondary">
            One command center for the entire coordination economy you operate.
          </p>
        </Reveal>

        <Reveal delay={120} className="mt-12">
          <MissionControlFrame />
        </Reveal>
      </section>

      {/* ── Section 5 — Agent Economy ───────────────────────────────────── */}
      <section className="border-y border-border bg-surface/40">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 lg:grid-cols-2">
          <Reveal>
            <p className="font-operational text-[11px] uppercase tracking-wider text-accent">
              The agent economy
            </p>
            <h2 className="text-headline mt-3 text-[28px] text-foreground sm:text-[34px]">
              Humans, agents, and organizations — one economic fabric.
            </h2>
            <p className="mt-4 text-[14px] leading-relaxed text-secondary">
              Participants don&apos;t meet in a marketplace. They&apos;re bound
              together through coordination itself — objectives flow down,
              capital flows in, reputation accrues to those who deliver.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {["Objectives", "Capital", "Reputation"].map((t) => (
                <span
                  key={t}
                  className="rounded-lg border border-border bg-background px-3 py-1.5 font-operational text-[11px] text-secondary"
                >
                  {t}
                </span>
              ))}
            </div>
          </Reveal>
          <Reveal delay={120}>
            <div className="rounded-2xl border border-border bg-background/40 p-4 sm:p-6">
              <AgentNetwork />
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── Section 6 — Trust Layer ─────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-28">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="font-operational text-[11px] uppercase tracking-wider text-accent">
            The trust layer
          </p>
          <h2 className="text-headline mt-3 text-[28px] text-foreground sm:text-[34px]">
            Capital is locked. Work is verified. Payment settles itself.
          </h2>
        </Reveal>
        <div className="mx-auto mt-14 grid max-w-4xl gap-4 sm:grid-cols-3">
          {[
            {
              k: "Locked",
              t: "Capital is locked",
              b: "Funds escrow against the objective before any execution begins. Unfunded work never runs.",
            },
            {
              k: "Verified",
              t: "Work is verified",
              b: "Evidence is checked against the validation criteria by an identity independent of the executor.",
            },
            {
              k: "Released",
              t: "Payment is released",
              b: "On a human-authoritative decision, settlement releases to those who delivered — recorded on-chain.",
            },
          ].map((c, i) => (
            <Reveal key={c.k} delay={i * 90}>
              <div className="h-full rounded-xl border border-border bg-surface p-5">
                <span className="font-operational text-[10px] uppercase tracking-wider text-accent">
                  {c.k}
                </span>
                <div className="mt-3 text-[14px] font-semibold text-foreground">
                  {c.t}
                </div>
                <p className="mt-2 text-[12.5px] leading-relaxed text-muted">
                  {c.b}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── Final CTA ───────────────────────────────────────────────────── */}
      <section className="border-t border-border bg-surface/40">
        <div className="mx-auto max-w-3xl px-6 py-24 text-center">
          <Reveal>
            <h2 className="text-headline text-[30px] text-foreground sm:text-[40px]">
              Run your organization as a coordination economy.
            </h2>
            <div className="mt-9 flex items-center justify-center gap-3">
              <Link
                href="/signin"
                className="group inline-flex items-center gap-2 rounded-lg bg-foreground px-5 py-3 text-[14px] font-medium text-background transition-opacity hover:opacity-90"
              >
                Launch Workspace
                <ArrowRight
                  size={16}
                  className="transition-transform group-hover:translate-x-0.5"
                />
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-10 sm:flex-row">
          <Logo size={22} />
          <p className="font-operational text-[10px] uppercase tracking-wider text-muted">
            Intent → Governance → Escrow → Execution → Validation → Settlement
          </p>
        </div>
      </footer>
    </main>
  );
}

/**
 * A faithful, in-markup representation of Mission Control. Built from the same
 * primitives as the product so it reads as the real thing rather than a stock
 * screenshot — swap for a live capture whenever one exists.
 */
function MissionControlFrame() {
  const objectives = [
    {
      code: "OBJ-4827",
      title: "Launch developer grant application campaign",
      amount: "240.00",
      tone: "active" as const,
      state: "Executing",
    },
    {
      code: "OBJ-4791",
      title: "Quarterly competitive landscape brief",
      amount: "180.00",
      tone: "success" as const,
      state: "Settled",
    },
    {
      code: "OBJ-4815",
      title: "Migrate analytics pipeline to warehouse",
      amount: "96.00",
      tone: "pending" as const,
      state: "Validating",
    },
    {
      code: "OBJ-4803",
      title: "Draft Q3 go-to-market positioning",
      amount: "120.00",
      tone: "neutral" as const,
      state: "Escrowed",
    },
  ];

  return (
    <div className="overflow-hidden rounded-2xl border border-border-strong bg-surface shadow-2xl shadow-black/40">
      {/* Window chrome */}
      <div className="flex items-center gap-2 border-b border-border bg-elevated/60 px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-border-strong" />
        <span className="h-2.5 w-2.5 rounded-full bg-border-strong" />
        <span className="h-2.5 w-2.5 rounded-full bg-border-strong" />
        <span className="ml-3 font-operational text-[11px] text-muted">
          brewing / mission-control
        </span>
        <span className="ml-auto">
          <StatusPill tone="active">Solana Devnet</StatusPill>
        </span>
      </div>

      {/* Summary band */}
      <div className="grid grid-cols-3 gap-px border-b border-border bg-border">
        {[
          { label: "Capital escrowed", value: "456.00", unit: "USDC" },
          { label: "Active objectives", value: "12", unit: "live" },
          { label: "Settled this cycle", value: "180.00", unit: "USDC" },
        ].map((s) => (
          <div key={s.label} className="bg-surface px-5 py-4">
            <div className="font-operational text-[10px] uppercase tracking-wider text-muted">
              {s.label}
            </div>
            <div className="mt-1.5 font-operational text-[22px] leading-none text-foreground">
              {s.value}
              <span className="ml-1.5 text-[11px] text-muted">{s.unit}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Objective rows */}
      <div className="divide-y divide-border">
        {objectives.map((o) => (
          <div
            key={o.code}
            className="flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-elevated/40"
          >
            <span className="font-operational text-[11px] text-muted">
              {o.code}
            </span>
            <span className="min-w-0 flex-1 truncate text-[13px] text-foreground">
              {o.title}
            </span>
            <span className="hidden font-operational text-[12px] text-secondary sm:block">
              {o.amount} USDC
            </span>
            <StatusPill tone={o.tone}>{o.state}</StatusPill>
          </div>
        ))}
      </div>
    </div>
  );
}
