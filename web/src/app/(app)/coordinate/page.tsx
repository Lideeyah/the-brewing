import { Sparkles } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { CoordinateForm } from "@/components/app/coordinate-form";

const LIFECYCLE = [
  { step: "Intent", note: "You express the operational need" },
  { step: "Governance", note: "Copilot structures rules & SLA" },
  { step: "Escrow", note: "Budget locked in USDC" },
  { step: "Execution", note: "Work orchestrated toward the objective" },
  { step: "Validation", note: "Audited against criteria" },
  { step: "Settlement", note: "Released or slashed by governance" },
];

export default function CoordinatePage() {
  return (
    <>
      <Topbar title="Coordinate" breadcrumb="brewing / coordinate" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Panel>
              <PanelHeader
                title="New objective"
                action={
                  <span className="flex items-center gap-1.5 font-operational text-[11px] text-accent">
                    <Sparkles size={13} /> Coordination Copilot
                  </span>
                }
              />
              <PanelBody>
                <CoordinateForm />
              </PanelBody>
            </Panel>
          </div>

          <Panel>
            <PanelHeader title="Lifecycle" meta="governed" />
            <PanelBody className="space-y-3.5">
              {LIFECYCLE.map((l, i) => (
                <div key={l.step} className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border-strong font-operational text-[10px] text-accent">
                    {i + 1}
                  </span>
                  <div>
                    <div className="text-[13px] text-foreground">{l.step}</div>
                    <div className="text-[12px] text-muted">{l.note}</div>
                  </div>
                </div>
              ))}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  );
}
