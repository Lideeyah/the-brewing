/**
 * The "economy coming alive" strip: continuous streams of economic events
 * flowing across the screen like air-traffic control or a market tape.
 * Pure CSS motion (see globals.css) so it renders on the server with no JS.
 */

type Tone = "neutral" | "accent" | "pending" | "success" | "failure";

type Event = {
  label: string;
  code: string;
  amount?: string;
  tone: Tone;
};

const DOT: Record<Tone, string> = {
  neutral: "bg-neutral",
  accent: "bg-accent",
  pending: "bg-pending",
  success: "bg-success",
  failure: "bg-failure",
};

// Representative lifecycle traffic. Not live data — a curated tape that reads
// like a real coordination economy in motion.
const ROW_A: Event[] = [
  { label: "Objective Created", code: "OBJ-4827", tone: "neutral" },
  { label: "Funding Locked", code: "OBJ-4827", amount: "240 USDC", tone: "pending" },
  { label: "Agent Assigned", code: "OBJ-4815", tone: "accent" },
  { label: "Validation Passed", code: "OBJ-4791", tone: "success" },
  { label: "Settlement Released", code: "OBJ-4791", amount: "180 USDC", tone: "success" },
  { label: "Evidence Submitted", code: "OBJ-4803", tone: "neutral" },
  { label: "Escrow Confirmed", code: "OBJ-4815", amount: "96 USDC", tone: "accent" },
  { label: "Objective Created", code: "OBJ-4830", tone: "neutral" },
];

const ROW_B: Event[] = [
  { label: "Validation Passed", code: "OBJ-4762", tone: "success" },
  { label: "Settlement Released", code: "OBJ-4762", amount: "60 USDC", tone: "success" },
  { label: "Funding Locked", code: "OBJ-4818", amount: "30 USDC", tone: "pending" },
  { label: "Settlement Slashed", code: "OBJ-4744", amount: "—", tone: "failure" },
  { label: "Agent Assigned", code: "OBJ-4822", tone: "accent" },
  { label: "Evidence Submitted", code: "OBJ-4818", tone: "neutral" },
  { label: "Validation Passed", code: "OBJ-4811", tone: "success" },
  { label: "Escrow Confirmed", code: "OBJ-4822", amount: "120 USDC", tone: "accent" },
];

function Ticket({ ev }: { ev: Event }) {
  return (
    <div className="mx-1.5 flex shrink-0 items-center gap-2.5 rounded-lg border border-border bg-surface/70 px-3.5 py-2">
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT[ev.tone]} node-pulse`} />
      <span className="whitespace-nowrap text-[12px] font-medium text-secondary">
        {ev.label}
      </span>
      <span className="whitespace-nowrap font-operational text-[10.5px] text-muted">
        {ev.code}
      </span>
      {ev.amount ? (
        <span className="whitespace-nowrap font-operational text-[10.5px] text-foreground/80">
          {ev.amount}
        </span>
      ) : null}
    </div>
  );
}

function Row({
  events,
  direction,
  durationSec,
}: {
  events: Event[];
  direction: "left" | "right";
  durationSec: number;
}) {
  // Duplicate the sequence so the -50% translate loops seamlessly.
  const doubled = [...events, ...events];
  return (
    <div className="stream-mask overflow-hidden py-1">
      <div
        className={`stream-track ${
          direction === "left" ? "stream-track-left" : "stream-track-right"
        }`}
        style={{ animationDuration: `${durationSec}s` }}
      >
        {doubled.map((ev, i) => (
          <Ticket key={`${ev.code}-${ev.label}-${i}`} ev={ev} />
        ))}
      </div>
    </div>
  );
}

export function EconomyStream() {
  return (
    <div
      aria-hidden
      className="flex flex-col gap-2 [mask-composite:intersect]"
    >
      <Row events={ROW_A} direction="left" durationSec={60} />
      <Row events={ROW_B} direction="right" durationSec={48} />
    </div>
  );
}
