import { redirect } from "next/navigation";

import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { FeeWallet } from "@/components/admin/fee-wallet";
import { Disputes } from "@/components/admin/disputes";
import { adminLogout } from "@/lib/admin-actions";
import { adminApiGet, isAdminAuthed } from "@/lib/admin-server";
import type { AdminDispute, AdminOverview, FeedbackItem } from "@/lib/types";

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <Panel className="bg-surface">
      <PanelBody className="p-4">
        <div className="font-operational text-[24px] leading-none tracking-tight text-foreground">
          {value}
        </div>
        <div className="mt-2 text-[12px] text-secondary">{label}</div>
        {hint && <div className="mt-0.5 text-[10px] text-muted">{hint}</div>}
      </PanelBody>
    </Panel>
  );
}

export default async function AdminPage() {
  if (!(await isAdminAuthed())) redirect("/admin/login");

  const [ov, feedbackRaw, disputesRaw] = await Promise.all([
    adminApiGet<AdminOverview>("/admin/overview"),
    adminApiGet<FeedbackItem[]>("/admin/feedback"),
    adminApiGet<AdminDispute[]>("/admin/disputes"),
  ]);
  const feedback = feedbackRaw ?? [];
  const disputes = disputesRaw ?? [];

  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <header className="mb-6 flex items-center justify-between border-b border-border pb-4">
        <div>
          <p className="font-operational text-[11px] uppercase tracking-[0.2em] text-muted">
            Brewing
          </p>
          <h1 className="text-[18px] font-semibold tracking-tight text-foreground">
            Admin · Platform
          </h1>
        </div>
        <form action={adminLogout}>
          <button
            type="submit"
            className="rounded-lg border border-border px-3 py-1.5 text-[12px] text-secondary hover:bg-elevated hover:text-foreground"
          >
            Sign out
          </button>
        </form>
      </header>

      {!ov ? (
        <p className="text-[13px] text-muted">Could not load platform metrics.</p>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Metric label="Users" value={ov.users_total} hint={`+${ov.users_new_30d} in 30d`} />
            <Metric label="Workspaces" value={ov.workspaces_total} />
            <Metric label="Objectives" value={ov.objectives_total} />
            <Metric label="Registered agents" value={ov.agents_total} />
            <Metric
              label="Value settled"
              value={`${ov.settled_usdc_total} USDC`}
              hint={`${ov.settlements_count} settlements`}
            />
            <Metric label="Platform revenue" value={`${ov.fees_usdc_total} USDC`} hint="fees collected" />
          </div>

          {/* Platform revenue wallet — address, balance, withdraw */}
          <Panel>
            <PanelHeader
              title="Platform revenue wallet"
              meta="fees collected here · withdraw to any address"
            />
            <FeeWallet
              address={ov.platform_fee_wallet_address}
              balance={ov.platform_fee_balance_usdc}
            />
          </Panel>

          {/* Dispute arbitration — held escrow awaiting a neutral ruling */}
          <Panel>
            <PanelHeader
              title="Disputes"
              meta={
                disputes.length === 0
                  ? "none open"
                  : `${disputes.length} held · arbiter ruling required`
              }
            />
            <Disputes disputes={disputes} />
          </Panel>

          <Panel>
            <PanelHeader title="Objectives by status" meta="lifecycle distribution" />
            <PanelBody className="flex flex-wrap gap-2">
              {Object.entries(ov.objectives_by_status).map(([k, v]) => (
                <div
                  key={k}
                  className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2"
                >
                  <span className="font-operational text-[16px] text-foreground">{v}</span>
                  <span className="text-[12px] text-secondary">{k.replace(/_/g, " ")}</span>
                </div>
              ))}
            </PanelBody>
          </Panel>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Panel>
              <PanelHeader title="Recent settlements" meta="newest first" />
              {ov.recent_settlements.length === 0 ? (
                <PanelBody><p className="text-[12px] text-muted">None yet.</p></PanelBody>
              ) : (
                <div className="divide-y divide-border">
                  {ov.recent_settlements.map((s, i) => (
                    <div key={i} className="flex items-center gap-3 px-5 py-3">
                      <StatusPill tone={s.status === "settled" ? "success" : "failure"}>
                        {s.status}
                      </StatusPill>
                      <span className="min-w-0 flex-1 truncate font-operational text-[12px] text-secondary">
                        {s.amount_usdc} USDC
                      </span>
                      <span className="font-operational text-[11px] text-muted">fee {s.fee_usdc}</span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel>
              <PanelHeader title="Recent objectives" meta="newest first" />
              {ov.recent_objectives.length === 0 ? (
                <PanelBody><p className="text-[12px] text-muted">None yet.</p></PanelBody>
              ) : (
                <div className="divide-y divide-border">
                  {ov.recent_objectives.map((o) => (
                    <div key={o.id} className="flex items-center gap-3 px-5 py-3">
                      <span className="min-w-0 flex-1 truncate text-[13px] text-foreground">
                        {o.title}
                      </span>
                      {o.workspace && (
                        <span className="font-operational text-[10px] text-muted">{o.workspace}</span>
                      )}
                      <StatusPill tone={o.status === "settled" ? "success" : "neutral"}>
                        {o.status.replace(/_/g, " ")}
                      </StatusPill>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>

          <Panel>
            <PanelHeader
              title="User feedback"
              meta={`${feedback.length} submission${feedback.length === 1 ? "" : "s"}`}
            />
            {feedback.length === 0 ? (
              <PanelBody>
                <p className="text-[12px] text-muted">No feedback yet.</p>
              </PanelBody>
            ) : (
              <div className="divide-y divide-border">
                {feedback.map((f) => (
                  <div key={f.id} className="px-5 py-3.5">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <span className="font-operational text-[10px] uppercase tracking-wider text-accent">
                        {f.category}
                      </span>
                      <span className="text-[12px] text-foreground">
                        {f.name ?? f.email ?? "Anonymous"}
                      </span>
                      <StatusPill tone={f.status === "open" ? "pending" : "success"}>
                        {f.status}
                      </StatusPill>
                    </div>
                    <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-secondary">
                      {f.message}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}
