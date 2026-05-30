import {
  AlertTriangle,
  ArrowDownRight,
  CheckCircle2,
  Circle,
  FileText,
  Fingerprint,
  Link2,
  Link2Off,
} from "lucide-react";

import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import type { EvidenceTrail as EvidenceTrailType } from "@/lib/types";

type Tone = "success" | "pending" | "failure" | "neutral" | "active";

const QUALITY_TONE: Record<string, Tone> = {
  strong: "success",
  weak: "pending",
  contradictory: "failure",
  missing: "neutral",
  unknown: "neutral",
};

/**
 * Evidence audit trail — the legible chain from raw execution output to
 * settlement. The top rail walks the five stages (output → normalized evidence
 * → independent validation → settlement authorization → settlement); below it,
 * each piece of evidence is shown with its oracle classification, the success
 * criteria it grounds, and any validator flag. The evidence hash is the
 * cryptographic anchor proving the agent was authorized against the exact
 * evidence that was validated — surfaced here, not buried.
 */
export function EvidenceTrail({ trail }: { trail: EvidenceTrailType }) {
  if (!trail || trail.items.length === 0) return null;

  return (
    <Panel className="mt-4">
      <PanelHeader
        title="Evidence audit trail"
        meta={`${trail.criteria_satisfied}/${trail.criteria_total} criteria grounded`}
      />
      <PanelBody className="space-y-5">
        <p className="flex items-start gap-1.5 text-[12px] leading-relaxed text-muted">
          <FileText size={13} className="mt-0.5 shrink-0 text-accent" />
          Every settlement is traceable to the evidence behind it. This walks the
          full chain — execution output, normalized evidence, independent
          validation, settlement authorization, settlement — and binds it all to
          one evidence hash.
        </p>

        {/* Cryptographic anchor */}
        {trail.evidence_hash && (
          <div
            className={`flex flex-wrap items-center gap-2 rounded-lg border p-3 ${
              trail.hash_consistent
                ? "border-success/30 bg-success/5"
                : "border-border bg-elevated"
            }`}
          >
            {trail.hash_consistent ? (
              <Link2 size={14} className="text-success" />
            ) : (
              <Link2Off size={14} className="text-muted" />
            )}
            <span className="text-[12px] font-medium text-foreground">
              {trail.hash_consistent
                ? "Validated evidence matches authorized evidence"
                : "Evidence anchor"}
            </span>
            <span className="flex items-center gap-1 break-all font-operational text-[11px] text-muted">
              <Fingerprint size={11} className="shrink-0" />
              {trail.evidence_hash}
            </span>
          </div>
        )}

        {/* Stage rail */}
        <div className="space-y-0">
          {trail.stages.map((s, i) => (
            <div key={s.key} className="flex gap-3.5">
              <div className="flex flex-col items-center">
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border ${
                    s.complete
                      ? "border-success/40 bg-success/10 text-success"
                      : "border-border bg-elevated text-muted"
                  }`}
                >
                  {s.complete ? (
                    <CheckCircle2 size={13} />
                  ) : (
                    <Circle size={11} />
                  )}
                </span>
                {i < trail.stages.length - 1 && (
                  <span className="my-1 w-px flex-1 bg-border" />
                )}
              </div>
              <div
                className={`min-w-0 flex-1 ${
                  i < trail.stages.length - 1 ? "pb-3" : ""
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[13px] font-medium text-foreground">
                    {s.label}
                  </span>
                  {!s.complete && (
                    <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                      pending
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-[11px] text-muted">{s.detail}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Per-evidence detail */}
        <div className="space-y-2 border-t border-border pt-4">
          <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
            Evidence ledger
          </p>
          {trail.items.map((e) => (
            <div
              key={e.step_index}
              className="rounded-lg border border-border bg-background p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                      step {e.step_index + 1}
                    </span>
                    <span className="text-[13px] font-medium text-foreground">
                      {e.step_title}
                    </span>
                    <span className="rounded border border-border bg-elevated px-1.5 py-0.5 font-operational text-[10px] text-secondary">
                      {e.output_kind.replace(/_/g, " ")}
                    </span>
                    <StatusPill
                      tone={QUALITY_TONE[e.quality] ?? "neutral"}
                      dot={false}
                    >
                      {e.quality} evidence
                    </StatusPill>
                    {(e.has_errors || e.validation_flagged) && (
                      <span className="flex items-center gap-1 text-[11px] text-failure">
                        <AlertTriangle size={11} />
                        {e.validation_flagged
                          ? "validator flagged"
                          : "error markers"}
                      </span>
                    )}
                  </div>

                  {e.snippet && (
                    <p className="mt-1.5 line-clamp-3 text-[12px] leading-relaxed text-secondary">
                      {e.snippet}
                    </p>
                  )}

                  {e.supports_criteria.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {e.supports_criteria.map((c, ci) => (
                        <p
                          key={ci}
                          className="flex items-start gap-1.5 text-[11px] text-muted"
                        >
                          <ArrowDownRight
                            size={11}
                            className="mt-0.5 shrink-0 text-accent"
                          />
                          <span>
                            grounds criterion:{" "}
                            <span className="text-secondary">{c}</span>
                          </span>
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </PanelBody>
    </Panel>
  );
}
