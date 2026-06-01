/**
 * Agent-economy network: three participants — Humans, Agents, Organizations —
 * bound together through a central coordination hub by three flows: Objectives,
 * Capital, Reputation. Restrained SVG, animated edges via globals.css.
 */

const C_BORDER = "var(--color-border-strong)";
const C_ACCENT = "var(--color-accent)";
const C_SURFACE = "var(--color-elevated)";
const C_FG = "var(--color-foreground)";
const C_SEC = "var(--color-secondary)";
const C_MUTED = "var(--color-muted)";

function Node({
  x,
  y,
  label,
  r = 30,
}: {
  x: number;
  y: number;
  label: string;
  r?: number;
}) {
  return (
    <g>
      <circle
        cx={x}
        cy={y}
        r={r}
        style={{ fill: C_SURFACE, stroke: C_BORDER }}
        strokeWidth={1}
      />
      <circle
        cx={x}
        cy={y}
        r={4}
        className="node-pulse"
        style={{ fill: C_ACCENT }}
      />
      <text
        x={x}
        y={y + r + 22}
        textAnchor="middle"
        style={{
          fill: C_FG,
          fontSize: 14,
          fontWeight: 600,
          letterSpacing: "-0.01em",
        }}
      >
        {label}
      </text>
    </g>
  );
}

export function AgentNetwork() {
  // viewBox space; scales fluidly to container width.
  const hub = { x: 400, y: 200 };
  const humans = { x: 110, y: 120 };
  const orgs = { x: 690, y: 120 };
  const agents = { x: 400, y: 330 };

  const edge = (a: { x: number; y: number }) =>
    `M ${a.x} ${a.y} L ${hub.x} ${hub.y}`;

  return (
    <svg
      viewBox="0 0 800 400"
      className="h-auto w-full"
      role="img"
      aria-label="Humans, agents, and organizations connected through a coordination hub by objectives, capital, and reputation."
    >
      {/* Edges (drawn first, under nodes) */}
      <g style={{ stroke: C_BORDER }} strokeWidth={1} fill="none">
        <path d={edge(humans)} />
        <path d={edge(orgs)} />
        <path d={edge(agents)} />
      </g>
      {/* Energy traveling along each edge */}
      <g style={{ stroke: C_ACCENT }} strokeWidth={1.5} fill="none" opacity={0.7}>
        <path className="flow-line" d={edge(humans)} />
        <path
          className="flow-line"
          style={{ animationDelay: "-7s" }}
          d={edge(orgs)}
        />
        <path
          className="flow-line"
          style={{ animationDelay: "-14s" }}
          d={edge(agents)}
        />
      </g>

      {/* Central hub */}
      <circle
        cx={hub.x}
        cy={hub.y}
        r={46}
        style={{ fill: C_SURFACE, stroke: C_BORDER }}
        strokeWidth={1}
      />
      <circle
        cx={hub.x}
        cy={hub.y}
        r={46}
        className="node-pulse"
        style={{ fill: "none", stroke: C_ACCENT }}
        strokeWidth={1}
        opacity={0.5}
      />
      <text
        x={hub.x}
        y={hub.y - 4}
        textAnchor="middle"
        style={{
          fill: C_SEC,
          fontSize: 10,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
        }}
        fontFamily="var(--font-mono)"
      >
        Coordination
      </text>
      <text
        x={hub.x}
        y={hub.y + 12}
        textAnchor="middle"
        style={{
          fill: C_FG,
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        Objective
      </text>

      {/* Participant nodes */}
      <Node x={humans.x} y={humans.y} label="Humans" />
      <Node x={orgs.x} y={orgs.y} label="Organizations" />
      <Node x={agents.x} y={agents.y} label="Agents" />

      {/* Flow labels along the edges */}
      <text
        x={(humans.x + hub.x) / 2 - 6}
        y={(humans.y + hub.y) / 2 - 8}
        textAnchor="middle"
        style={{ fill: C_MUTED, fontSize: 11, letterSpacing: "0.04em" }}
        fontFamily="var(--font-mono)"
      >
        Objectives
      </text>
      <text
        x={(orgs.x + hub.x) / 2 + 6}
        y={(orgs.y + hub.y) / 2 - 8}
        textAnchor="middle"
        style={{ fill: C_MUTED, fontSize: 11, letterSpacing: "0.04em" }}
        fontFamily="var(--font-mono)"
      >
        Capital
      </text>
      <text
        x={(agents.x + hub.x) / 2 + 52}
        y={(agents.y + hub.y) / 2 + 4}
        textAnchor="middle"
        style={{ fill: C_MUTED, fontSize: 11, letterSpacing: "0.04em" }}
        fontFamily="var(--font-mono)"
      >
        Reputation
      </text>
    </svg>
  );
}
