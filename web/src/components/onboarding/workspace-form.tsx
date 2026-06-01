"use client";

import { useState } from "react";
import { useFormStatus } from "react-dom";
import { ArrowRight, Loader2 } from "lucide-react";

import { updateWorkspace } from "@/lib/actions";

const OPERATIONAL_TYPES = [
  "Business / enterprise operations",
  "Research / analysis",
  "Software / engineering",
  "Marketing / growth",
  "Operations / logistics",
  "Other",
];

function Toggle({
  name,
  label,
  sub,
  defaultChecked,
}: {
  name: string;
  label: string;
  sub: string;
  defaultChecked: boolean;
}) {
  const [on, setOn] = useState(defaultChecked);
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-border bg-background px-3.5 py-3">
      <span>
        <span className="block text-[12.5px] font-medium text-foreground">
          {label}
        </span>
        <span className="mt-0.5 block text-[11px] text-muted">{sub}</span>
      </span>
      {/* Hidden checkbox carries the value; the pill is the visual control. */}
      <input
        type="checkbox"
        name={name}
        checked={on}
        onChange={(e) => setOn(e.target.checked)}
        className="sr-only"
      />
      <span
        className={`relative h-[19px] w-[34px] shrink-0 rounded-full transition-colors ${
          on ? "bg-success" : "bg-border-strong"
        }`}
      >
        <span
          className={`absolute top-[2px] h-[15px] w-[15px] rounded-full bg-white transition-all ${
            on ? "left-[17px]" : "left-[2px]"
          }`}
        />
      </span>
    </label>
  );
}

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex w-full items-center justify-center gap-2 rounded-lg bg-foreground px-4 py-2.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
    >
      {pending ? (
        <Loader2 size={15} className="animate-spin" />
      ) : (
        <>
          Continue to treasury <ArrowRight size={15} />
        </>
      )}
    </button>
  );
}

export function WorkspaceForm({
  defaultName,
  defaultOrg,
  defaultType,
  requireAuditor,
  humanAuthoritative,
}: {
  defaultName: string;
  defaultOrg: string;
  defaultType: string;
  requireAuditor: boolean;
  humanAuthoritative: boolean;
}) {
  return (
    <form action={updateWorkspace} className="space-y-4">
      <div>
        <label className="mb-1.5 block text-[11px] font-semibold text-secondary">
          Organization name
        </label>
        <input
          name="org_name"
          required
          defaultValue={defaultOrg}
          placeholder="Acme Intelligence Ltd."
          className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
        />
      </div>

      <div>
        <label className="mb-1.5 block text-[11px] font-semibold text-secondary">
          Workspace name
        </label>
        <input
          name="name"
          required
          defaultValue={defaultName}
          placeholder="Acme Operations"
          className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
        />
      </div>

      <div>
        <label className="mb-1.5 block text-[11px] font-semibold text-secondary">
          Operational type
        </label>
        <select
          name="operational_type"
          defaultValue={defaultType || OPERATIONAL_TYPES[0]}
          className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-[13px] text-foreground focus:border-border-strong focus:outline-none"
        >
          {OPERATIONAL_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <label className="block text-[11px] font-semibold text-secondary">
          Governance defaults
        </label>
        <Toggle
          name="governance_require_auditor"
          label="Require auditor approval before settlement"
          sub="Independent validation gates every payout"
          defaultChecked={requireAuditor}
        />
        <Toggle
          name="governance_human_authoritative"
          label="Human-authoritative governance decision"
          sub="A person issues the binding release / slash"
          defaultChecked={humanAuthoritative}
        />
      </div>

      <SubmitButton />
    </form>
  );
}
