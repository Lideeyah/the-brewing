import {
  Check,
  Fingerprint,
  Gavel,
  HelpCircle,
  Coins,
  ScrollText,
  X,
} from "lucide-react";

import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import type {
  CriterionResult,
  Settlement,
  SettlementAuthorization,
} from "@/lib/types";

type Tone = "success" | "pending" | "failure" | "neutral" | "active";

const VERDICT_META: Record<string, { tone: Tone; label: string }> = {
  approved: { tone: "success", label: "Satisfied by evidence" },
  approved_with_conditions: { tone: "pending", label: "Partly satisfied" },
  rejected: { tone: "failure", label: "Not satisfied" },
};

function satisfiedMeta(satisfied?: boolean | null): {
  tone: Tone;
  label: string;
  icon: typeof Check;
} {
  if (satisfied === true)
    return { tone: "success", label: "met", icon: Check };
  if (satisfied === false)
    return { tone: "failure", label: "not met", icon: X };
  return { tone: "neutral", label: "indeterminate", icon: HelpCircle };
}

/**
 * Settlement rationale — the panel that answers "why did this agent get paid?".
 *
 * It traces the deterministic chain the settlement decision rests on:
 * predefined success criteria → the specific recorded evidence that satisfies
 * each one → the evidence-derived verdict → the human decision → payment. Every
 * criterion names the evidence steps (and overlapping terms) that justify its
 * verdict, and the whole artifact is bound to the evidence hash the independent
 * validator reasoned over — so the answer is verifiable, not asserted.
 */
export function SettlementRationale({
  authorization,
  settlement,
}: {
  authorization: SettlementAuthorization;
  settlement?: Settlement | null;
}) {
  const verdict =
    VERDICT_META[authorization.evidence_verdict] ?? {
      tone: "neutral" as Tone,
      label: authorization.evidence_verdict,
    };
  const results = authorization.criteria_results ?? [];
  const paid =
    settlement?.status === "settled" || authorization.authorized === true;

  return (
    <Panel className="mt-4">
      <PanelHeader
        title="Why did this agent get paid?"
        meta="evidence-grounded settlement authorization"
      />
      <PanelBody className="space-y-4">
        {/* Headline: the evidence-derived verdict + roll-up */}
        <div className="rounded-lg border border-border bg-elevated p-3">
          <div className="flex flex-wrap items-center gap-2">
            <ScrollText size={14} className="text-accent" />
            <span className="text-[12px] text-muted">Evidence verdict</span>
            <StatusPill tone={verdict.tone}>{verdict.label}</StatusPill>
            <span className="font-operational text-[11px] text-muted">
              {authorization.criteria_satisfied}/{authorization.criteria_total}{" "}
              criteria satisfied
            </span>
          </div>
          {authorization.headline && (
            <p className="mt-2 text-[13px] leading-relaxed text-secondary">
              {authorization.headline}
            </p>
          )}
        </div>

        {/* Per-criterion: criterion → satisfying evidence */}
        {results.length > 0 ? (
          <ol className="space-y-3">
            {results.map((r) => (
              <CriterionRow key={r.key} result={r} />
            ))}
          </ol>
        ) : (
          <p className="text-[12px] text-muted">
            No success criteria were defined for this objective, so settlement
            could not be evidence-gated.
          </p>
        )}

        {/* Decision → payment, with the evidence-hash binding */}
        <div className="space-y-2.5 border-t border-border pt-3">
          <div className="flex items-center gap-2 text-[12px]">
            <Gavel size={13} className="shrink-0 text-muted" />
            <span className="text-muted">Human decision</span>
            <StatusPill
              tone={authorization.governance_approved ? "success" : "failure"}
            >
              {authorization.governance_approved ? "approved" : "rejected"}
            </StatusPill>
            {authorization.aligned_with_evidence === false && (
              <StatusPill tone="pending" dot={false}>
                overrides evidence
              </StatusPill>
            )}
            {authorization.aligned_with_evidence === true && (
              <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                aligned with evidence
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 text-[12px]">
            <Coins size={13} className="shrink-0 text-muted" />
            <span className="text-muted">Payment</span>
            <StatusPill tone={paid ? "success" : "neutral"}>
              {paid ? "authorized" : "not authorized"}
            </StatusPill>
            {settlement && (
              <span className="font-operational text-[11px] text-secondary">
                {settlement.amount_usdc} USDC
              </span>
            )}
          </div>

          <div className="flex items-start gap-2 pt-1">
            <Fingerprint size={13} className="mt-0.5 shrink-0 text-muted" />
            <div className="min-w-0">
              <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                Bound to evidence hash
              </p>
              <p className="mt-0.5 break-all font-operational text-[11px] text-secondary">
                {authorization.evidence_hash}
              </p>
            </div>
          </div>
        </div>

        <p className="border-t border-border pt-3 text-[11px] text-muted">
          Payment is authorized because recorded evidence satisfies predefined
          success criteria — each criterion above names the exact evidence that
          proves it, bound to the hash the independent validator reviewed.
          Validation is a first-class artifact here, not a status flip.
        </p>
      </PanelBody>
    </Panel>
  );
}

function CriterionRow({ result }: { result: CriterionResult }) {
  const meta = satisfiedMeta(result.satisfied);
  const Icon = meta.icon;
  return (
    <li className="rounded-lg border border-border p-3">
      <div className="flex gap-2.5">
        <span
          className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
            result.satisfied === true
              ? "bg-success/15 text-success"
              : result.satisfied === false
                ? "bg-failure/15 text-failure"
                : "bg-elevated text-muted"
          }`}
        >
          <Icon size={11} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] text-foreground">
              {result.description}
            </span>
            <StatusPill tone={meta.tone} dot={false}>
              {meta.label}
            </StatusPill>
            {result.required_evidence_kind && (
              <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                needs {result.required_evidence_kind.replace(/_/g, " ")}
              </span>
            )}
            <span className="font-operational text-[10px] text-muted">
              {Math.round(result.confidence * 100)}%
            </span>
          </div>

          {result.rationale && (
            <p className="mt-1 text-[12px] leading-relaxed text-muted">
              {result.rationale}
            </p>
          )}

          {result.basis.length > 0 && (
            <div className="mt-2 space-y-1.5">
              <p className="font-operational text-[10px] uppercase tracking-wider text-muted">
                Satisfying evidence
              </p>
              {result.basis.map((b, i) => (
                <div
                  key={i}
                  className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-secondary"
                >
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" />
                  <span className="truncate text-foreground">
                    {b.step_title ?? `Step ${(b.step_index ?? 0) + 1}`}
                  </span>
                  {b.output_kind && (
                    <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                      {b.output_kind}
                    </span>
                  )}
                  {b.matched_terms.length > 0 && (
                    <span className="flex flex-wrap gap-1">
                      {b.matched_terms.map((t) => (
                        <span
                          key={t}
                          className="rounded border border-border bg-elevated px-1.5 py-0.5 font-operational text-[10px] text-secondary"
                        >
                          {t}
                        </span>
                      ))}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </li>
  );
}
