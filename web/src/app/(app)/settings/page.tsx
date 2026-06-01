import { User as UserIcon, Building2 } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { SignOutButton } from "@/components/app/sign-out-button";
import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";

function prettyNetwork(value?: string | null): string {
  if (value === "SOL-DEVNET") return "Solana Devnet";
  if (value === "SOL") return "Solana";
  return value ?? "—";
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
        {label}
      </p>
      <p
        className={`mt-0.5 break-all text-[13px] text-foreground ${
          mono ? "font-operational" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}

export default async function SettingsPage() {
  let me: Me | null = null;
  try {
    me = await apiGet<Me>("/auth/me");
  } catch {
    me = null;
  }

  return (
    <>
      <Topbar title="Settings" breadcrumb="brewing / settings" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-4">
          <div>
            <h2 className="text-[18px] font-semibold tracking-tight text-foreground">
              Settings
            </h2>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-secondary">
              Your identity and workspace, as the API sees them. The backend is
              the source of truth for authorization — these values are read live
              from your session.
            </p>
          </div>

          {!me ? (
            <Panel>
              <PanelBody>
                <p className="text-[13px] text-muted">
                  Could not load your profile. Try refreshing the page.
                </p>
              </PanelBody>
            </Panel>
          ) : (
            <>
              {/* Identity */}
              <Panel>
                <PanelHeader title="Identity" meta="this session" />
                <PanelBody className="space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent/15 text-accent">
                      <UserIcon size={16} />
                    </span>
                    <div className="min-w-0">
                      <div className="text-[14px] font-medium text-foreground">
                        {me.user.name || "Operator"}
                      </div>
                      <div className="font-operational text-[11px] text-muted">
                        {me.user.email}
                      </div>
                    </div>
                    <div className="ml-auto">
                      <StatusPill tone="active">{me.role}</StatusPill>
                    </div>
                  </div>
                </PanelBody>
              </Panel>

              {/* Workspace */}
              <Panel>
                <PanelHeader title="Workspace" meta="default" />
                <PanelBody className="space-y-4">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-elevated text-secondary">
                      <Building2 size={16} />
                    </span>
                    <div className="min-w-0">
                      <div className="text-[14px] font-medium text-foreground">
                        {me.workspace.name}
                      </div>
                      {me.workspace.org_name && (
                        <div className="text-[11px] text-muted">
                          {me.workspace.org_name}
                        </div>
                      )}
                    </div>
                    <div className="ml-auto">
                      <StatusPill tone="neutral">
                        {me.workspace.subscription_tier}
                      </StatusPill>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 border-t border-border pt-4 sm:grid-cols-2">
                    {me.workspace.operational_type && (
                      <Field
                        label="Operational type"
                        value={me.workspace.operational_type}
                      />
                    )}
                    <Field
                      label="Settlement network"
                      value={prettyNetwork(me.workspace.treasury_blockchain)}
                    />
                    {me.workspace.treasury_address && (
                      <div className="sm:col-span-2">
                        <Field
                          label="Treasury address"
                          value={me.workspace.treasury_address}
                          mono
                        />
                      </div>
                    )}
                  </div>
                </PanelBody>
              </Panel>

              {/* Session */}
              <Panel>
                <PanelHeader title="Session" />
                <PanelBody className="flex items-center justify-between gap-4">
                  <p className="text-[12px] text-muted">
                    End this session on this device.
                  </p>
                  <SignOutButton />
                </PanelBody>
              </Panel>
            </>
          )}
        </div>
      </div>
    </>
  );
}
