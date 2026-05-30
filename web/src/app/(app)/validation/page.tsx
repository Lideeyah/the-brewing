import { Fingerprint, ShieldCheck, Verified } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { apiGet } from "@/lib/api";
import type { Validator, ValidationRecord } from "@/lib/types";
import { objRef, formatTime } from "@/lib/objective-ui";

function recMeta(rec: string): {
  tone: "success" | "pending" | "failure" | "neutral";
  label: string;
} {
  switch (rec) {
    case "approved":
      return { tone: "success", label: "Approved" };
    case "approved_with_conditions":
      return { tone: "pending", label: "With conditions" };
    case "rejected":
      return { tone: "failure", label: "Rejected" };
    default:
      return { tone: "neutral", label: rec };
  }
}

export default async function ValidationPage() {
  let validators: Validator[] = [];
  let records: ValidationRecord[] = [];
  try {
    [validators, records] = await Promise.all([
      apiGet<Validator[]>("/validation/validators"),
      apiGet<ValidationRecord[]>("/validation/records"),
    ]);
  } catch {
    validators = [];
    records = [];
  }

  return (
    <>
      <Topbar title="Validation" breadcrumb="brewing / validation registry" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div>
            <h2 className="text-[18px] font-semibold tracking-tight text-foreground">
              Validation Registry
            </h2>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-secondary">
              Independent validators verify execution evidence and stake their
              own accuracy on the call. Execution never validates itself — every
              recommendation is bound to a hash of the exact evidence reviewed
              and reconciled against the authoritative governance decision.
            </p>
          </div>

          {/* Validators */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {validators.map((v) => (
              <ValidatorCard key={v.id} validator={v} />
            ))}
          </div>

          {/* Recent validation outcomes */}
          <Panel>
            <PanelHeader
              title="Recent validations"
              meta="evidence-bound · executor-independent"
            />
            <PanelBody className="p-0">
              {records.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-12 text-center">
                  <Verified size={22} className="text-accent" />
                  <p className="text-[13px] text-foreground">
                    No validations recorded yet
                  </p>
                  <p className="max-w-md text-[12px] text-muted">
                    Run an objective through evaluation and an independent
                    validator will record its evidence-bound recommendation here.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {records.map((r) => (
                    <li key={r.id} className="px-5 py-3.5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <StatusPill tone={recMeta(r.recommendation).tone}>
                              {recMeta(r.recommendation).label}
                            </StatusPill>
                            <span className="text-[13px] text-foreground">
                              {r.validator?.name ?? "Validator"}
                            </span>
                            <span className="font-operational text-[11px] text-muted">
                              {Math.round(r.confidence * 100)}% confidence
                            </span>
                            {r.outcome != null && (
                              <StatusPill
                                tone={r.upheld ? "success" : "failure"}
                                dot={false}
                              >
                                {r.upheld ? "upheld" : "overturned"}
                              </StatusPill>
                            )}
                          </div>
                          <div className="mt-1 flex items-center gap-1.5 text-muted">
                            <Fingerprint size={11} className="shrink-0" />
                            <span className="truncate font-operational text-[11px]">
                              {r.evidence_hash}
                            </span>
                          </div>
                        </div>
                        <div className="shrink-0 text-right">
                          <a
                            href={`/objectives/${r.objective_id}`}
                            className="font-operational text-[11px] text-accent hover:underline"
                          >
                            {objRef(r.objective_id)}
                          </a>
                          <div className="mt-0.5 text-[10px] text-muted">
                            {formatTime(r.created_at)}
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  );
}

function ValidatorCard({ validator }: { validator: Validator }) {
  const reconciled = validator.upheld_count + validator.overturned_count;
  return (
    <Panel>
      <PanelBody className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="shrink-0 text-accent" />
            <span className="text-[14px] font-medium text-foreground">
              {validator.name}
            </span>
          </div>
          {validator.independent && (
            <StatusPill tone="active" dot={false}>
              independent
            </StatusPill>
          )}
        </div>

        {validator.description && (
          <p className="text-[12px] leading-relaxed text-secondary">
            {validator.description}
          </p>
        )}

        <div className="grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
          <Stat
            label="Accuracy"
            value={
              validator.accuracy != null
                ? `${(validator.accuracy * 100).toFixed(0)}%`
                : "—"
            }
          />
          <Stat label="Validations" value={String(validator.validations_count)} />
          <Stat
            label="Reconciled"
            value={reconciled > 0 ? String(reconciled) : "—"}
          />
        </div>

        <div className="flex items-center justify-between border-t border-border pt-3 text-[11px] text-muted">
          <span className="font-operational">{validator.kind}</span>
          <span className="font-operational">
            μ-confidence {(validator.mean_confidence * 100).toFixed(0)}%
          </span>
        </div>
      </PanelBody>
    </Panel>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-operational text-[15px] text-foreground">{value}</div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wider text-muted">
        {label}
      </div>
    </div>
  );
}
