/**
 * Agent-economy network: three participants — Humans, Agents, Organizations —
 * bound together through a central coordination hub by three flows: Objectives,
 * Capital, Reputation. Restrained SVG; edges curve gently into the hub, energy
 * travels along them (globals.css), and the hub carries a slow coordination ring.
 */

const C_BORDER = "var(--color-border-strong)";
const C_ACCENT = "var(--color-accent)";
const C_FG = "var(--color-foreground)";
const C_SEC = "var(--color-secondary)";
const C_BG = "var(--color-background)";

type P = { x: number; y: number };

const sub = (a: P, b: P): P => ({ x: b.x - a.x, y: b.y - a.y });
const norm = (d: P): P => {
  const l = Math.hypot(d.x, d.y) || 1;
  return { x: d.x / l, y: d.y / l };
};

/**
 * Build a gentle quadratic connector that starts/ends on the circle borders
 * (so it never pokes inside a node) and bows by `bend` perpendicular units.
 * Returns the path plus the curve midpoint for placing a flow chip.
 */
function connector(a: P, ra: number, b: P, rb: number, bend: number) {
  const dir = norm(sub(a, b));
  const start = { x: a.x + dir.x * ra, y: a.y + dir.y * ra };
  const end = { x: b.x - dir.x * rb, y: b.y - dir.y * rb };
  const mid = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
  const perp = { x: -dir.y, y: dir.x };
  const ctrl = { x: mid.x + perp.x * bend, y: mid.y + perp.y * bend };
  const d = `M ${start.x} ${start.y} Q ${ctrl.x} ${ctrl.y} ${end.x} ${end.y}`;
  // Quadratic point at t = 0.5.
  const at = {
    x: 0.25 * start.x + 0.5 * ctrl.x + 0.25 * end.x,
    y: 0.25 * start.y + 0.5 * ctrl.y + 0.25 * end.y,
  };
  return { d, at };
}

function Node({ x, y, label, r = 31 }: { x: number; y: number; label: string; r?: number }) {
  return (
    <g>
      {/* soft halo */}
      <circle cx={x} cy={y} r={r + 9} fill="url(#node-halo)" opacity={0.6} />
      <circle
        cx={x}
        cy={y}
        r={r}
        fill="url(#node-fill)"
        style={{ stroke: C_BORDER }}
        strokeWidth={1}
      />
      <circle cx={x} cy={y} r={4.5} className="node-pulse" style={{ fill: C_ACCENT }} filter="url(#soft-glow)" />
      <text
        x={x}
        y={y + r + 24}
        textAnchor="middle"
        style={{ fill: C_FG, fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em" }}
      >
        {label}
      </text>
    </g>
  );
}

function FlowChip({ at, label }: { at: P; label: string }) {
  const w = label.length * 6.7 + 20;
  return (
    <g>
      <rect
        x={at.x - w / 2}
        y={at.y - 11}
        width={w}
        height={22}
        rx={6}
        style={{ fill: C_BG, stroke: C_BORDER }}
        strokeWidth={1}
      />
      <text
        x={at.x}
        y={at.y}
        textAnchor="middle"
        dominantBaseline="central"
        style={{ fill: C_SEC, fontSize: 11, letterSpacing: "0.06em" }}
        fontFamily="var(--font-mono)"
      >
        {label}
      </text>
    </g>
  );
}

export function AgentNetwork() {
  // viewBox space; scales fluidly to container width.
  const hub: P = { x: 400, y: 205 };
  const R_HUB = 50;
  const R_NODE = 31;
  const humans: P = { x: 150, y: 120 };
  const orgs: P = { x: 650, y: 120 };
  const agents: P = { x: 400, y: 360 };

  // Top edges bow gently upward (away from the hub's gravity); the vertical one stays straight.
  const eHumans = connector(humans, R_NODE, hub, R_HUB, -30);
  const eOrgs = connector(orgs, R_NODE, hub, R_HUB, 30);
  const eAgents = connector(agents, R_NODE, hub, R_HUB, 0);
  const edges = [eHumans, eOrgs, eAgents];

  return (
    <svg
      viewBox="0 0 800 440"
      className="h-auto w-full"
      role="img"
      aria-label="Humans, agents, and organizations connected through a coordination hub by objectives, capital, and reputation."
    >
      <defs>
        <radialGradient id="hub-fill" cx="50%" cy="40%" r="70%">
          <stop offset="0%" stopColor="#1b2436" />
          <stop offset="100%" stopColor="#0c1320" />
        </radialGradient>
        <radialGradient id="node-fill" cx="50%" cy="38%" r="75%">
          <stop offset="0%" stopColor="#161f30" />
          <stop offset="100%" stopColor="#0b1119" />
        </radialGradient>
        <radialGradient id="node-halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={C_ACCENT} stopOpacity={0.18} />
          <stop offset="100%" stopColor={C_ACCENT} stopOpacity={0} />
        </radialGradient>
        <linearGradient id="edge-stroke" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={C_BORDER} stopOpacity={0.4} />
          <stop offset="50%" stopColor={C_ACCENT} stopOpacity={0.9} />
          <stop offset="100%" stopColor={C_BORDER} stopOpacity={0.4} />
        </linearGradient>
        <filter id="soft-glow" x="-120%" y="-120%" width="340%" height="340%">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Edges — base track, wide glow, then the traveling energy. */}
      <g fill="none">
        {edges.map((e, i) => (
          <path key={`base-${i}`} d={e.d} style={{ stroke: C_BORDER }} strokeWidth={1} opacity={0.55} />
        ))}
        {edges.map((e, i) => (
          <path
            key={`glow-${i}`}
            d={e.d}
            stroke="url(#edge-stroke)"
            strokeWidth={2.5}
            opacity={0.22}
            filter="url(#soft-glow)"
          />
        ))}
        {edges.map((e, i) => (
          <path
            key={`flow-${i}`}
            className="flow-line"
            d={e.d}
            style={{ stroke: C_ACCENT, animationDelay: `${i * -7}s` }}
            strokeWidth={1.5}
            strokeLinecap="round"
            opacity={0.85}
          />
        ))}
      </g>

      {/* Central hub */}
      <g>
        <circle cx={hub.x} cy={hub.y} r={R_HUB + 22} fill="url(#node-halo)" opacity={0.7} />
        {/* slow-rotating coordination ring */}
        <circle
          className="hub-ring"
          cx={hub.x}
          cy={hub.y}
          r={R_HUB + 9}
          fill="none"
          style={{ stroke: C_ACCENT }}
          strokeWidth={1}
          strokeDasharray="2 7"
          opacity={0.4}
        />
        <circle
          cx={hub.x}
          cy={hub.y}
          r={R_HUB}
          fill="url(#hub-fill)"
          style={{ stroke: C_BORDER }}
          strokeWidth={1}
        />
        {/* breathing accent ring */}
        <circle
          cx={hub.x}
          cy={hub.y}
          r={R_HUB}
          className="node-pulse"
          fill="none"
          style={{ stroke: C_ACCENT }}
          strokeWidth={1}
          opacity={0.55}
        />
        <text
          x={hub.x}
          y={hub.y - 6}
          textAnchor="middle"
          style={{ fill: C_SEC, fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase" }}
          fontFamily="var(--font-mono)"
        >
          Coordination
        </text>
        <text
          x={hub.x}
          y={hub.y + 12}
          textAnchor="middle"
          style={{ fill: C_FG, fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em" }}
        >
          Objective
        </text>
      </g>

      {/* Participant nodes */}
      <Node x={humans.x} y={humans.y} label="Humans" />
      <Node x={orgs.x} y={orgs.y} label="Organizations" />
      <Node x={agents.x} y={agents.y} label="Agents" />

      {/* Flow chips — sit on the curve midpoint and mask the line cleanly. */}
      <FlowChip at={eHumans.at} label="Objectives" />
      <FlowChip at={eOrgs.at} label="Capital" />
      <FlowChip at={eAgents.at} label="Reputation" />
    </svg>
  );
}
