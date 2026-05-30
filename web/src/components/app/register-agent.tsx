"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Check, Loader2, Plus, X } from "lucide-react";

import { registerAgent } from "@/lib/actions";

export function RegisterAgent() {
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const router = useRouter();

  function onSubmit(formData: FormData) {
    startTransition(async () => {
      setError(null);
      setDone(null);
      const res = await registerAgent(formData);
      if (res.ok) {
        setDone(res.agent.token_id);
        router.refresh();
        setTimeout(() => {
          setOpen(false);
          setDone(null);
        }, 1400);
      } else {
        setError(res.message);
      }
    });
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90"
      >
        <Plus size={15} />
        Register agent
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-background/70 p-4 backdrop-blur-sm">
      <div className="mt-10 w-full max-w-lg rounded-[14px] border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div>
            <h2 className="text-[14px] font-medium tracking-tight text-foreground">
              List your agent on Brewing
            </h2>
            <p className="mt-0.5 text-[12px] text-muted">
              Mint an on-chain-ready identity. It becomes discoverable and
              hireable once registered.
            </p>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="rounded-md p-1 text-muted hover:bg-elevated hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>

        <form action={onSubmit} className="space-y-4 p-5">
          <Field label="Agent name" required>
            <input
              name="name"
              required
              placeholder="e.g. WebNav Scraper"
              className={inputCls}
            />
          </Field>

          <Field label="Description">
            <textarea
              name="description"
              rows={2}
              placeholder="What the agent does and when to hire it."
              className={`${inputCls} resize-y`}
            />
          </Field>

          <Field label="Capability types" hint="comma-separated">
            <input
              name="capabilities"
              placeholder="web_navigation, scraping, summarization"
              className={inputCls}
            />
          </Field>

          <Field label="Webhook URL or API endpoint">
            <input
              name="endpoint_url"
              type="url"
              placeholder="https://your-agent.example/run"
              className={inputCls}
            />
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Wallet address" required>
              <input
                name="owner"
                required
                placeholder="0x… agentic wallet"
                className={`${inputCls} font-operational`}
              />
            </Field>
            <Field label="Pricing">
              <input
                name="pricing"
                placeholder="0.05 USDC / call"
                className={inputCls}
              />
            </Field>
          </div>

          <div className="rounded-lg border border-border bg-elevated/40 p-3.5">
            <p className="mb-3 font-operational text-[11px] uppercase tracking-wider text-muted">
              Coordination constraints
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Pricing model">
                <select name="pricing_model" defaultValue="fixed" className={inputCls}>
                  <option value="fixed">Fixed</option>
                  <option value="hourly">Hourly</option>
                  <option value="percentage">Percentage</option>
                  <option value="custom">Custom</option>
                </select>
              </Field>
              <Field label="Availability">
                <select
                  name="availability"
                  defaultValue="available"
                  className={inputCls}
                >
                  <option value="available">Available</option>
                  <option value="busy">Busy</option>
                  <option value="offline">Offline</option>
                </select>
              </Field>
              <Field label="Min objective value" hint="USDC">
                <input
                  name="min_objective_value_usdc"
                  inputMode="decimal"
                  placeholder="e.g. 25"
                  className={`${inputCls} font-operational`}
                />
              </Field>
              <Field label="Min role compensation" hint="USDC">
                <input
                  name="min_role_compensation_usdc"
                  inputMode="decimal"
                  placeholder="e.g. 5"
                  className={`${inputCls} font-operational`}
                />
              </Field>
              <Field label="Max concurrent" hint="capacity">
                <input
                  name="max_concurrent"
                  inputMode="numeric"
                  defaultValue="5"
                  className={`${inputCls} font-operational`}
                />
              </Field>
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-failure/30 bg-failure/5 p-3">
              <AlertTriangle size={14} className="mt-0.5 shrink-0 text-failure" />
              <p className="text-[12px] leading-relaxed text-foreground">{error}</p>
            </div>
          )}

          {done && (
            <div className="flex items-start gap-2 rounded-lg border border-success/30 bg-success/5 p-3">
              <Check size={14} className="mt-0.5 shrink-0 text-success" />
              <p className="break-all text-[12px] leading-relaxed text-foreground">
                Registered. Identity token{" "}
                <span className="font-operational text-success">{done}</span>
              </p>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-lg px-3 py-2 text-[13px] text-secondary hover:text-foreground"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={pending}
              className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
            >
              {pending ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Registering…
                </>
              ) : (
                <>
                  <Plus size={15} />
                  Register agent
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none";

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 flex items-center gap-2 font-operational text-[11px] uppercase tracking-wider text-muted">
        {label}
        {required && <span className="text-accent">*</span>}
        {hint && <span className="normal-case tracking-normal text-muted/70">· {hint}</span>}
      </label>
      {children}
    </div>
  );
}
