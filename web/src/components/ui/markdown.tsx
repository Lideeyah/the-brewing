import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders Markdown with brand-matched, restrained styling. Tailwind v4 resets
 * element defaults, so each element is styled explicitly (no typography plugin).
 * Used for produced deliverables so results read cleanly instead of showing raw
 * `##` / `**` syntax.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-[13px] leading-relaxed text-secondary">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => (
            <h1 className="mb-2 mt-4 text-[17px] font-semibold tracking-tight text-foreground first:mt-0" {...p} />
          ),
          h2: (p) => (
            <h2 className="mb-2 mt-4 text-[15px] font-semibold tracking-tight text-foreground first:mt-0" {...p} />
          ),
          h3: (p) => (
            <h3 className="mb-1.5 mt-3 text-[13px] font-semibold uppercase tracking-wider text-muted first:mt-0" {...p} />
          ),
          p: (p) => <p className="mb-3 last:mb-0" {...p} />,
          ul: (p) => <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0" {...p} />,
          ol: (p) => <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0" {...p} />,
          li: (p) => <li className="leading-relaxed" {...p} />,
          strong: (p) => <strong className="font-semibold text-foreground" {...p} />,
          em: (p) => <em className="italic" {...p} />,
          a: (p) => <a className="text-accent underline underline-offset-2" {...p} />,
          code: (p) => (
            <code className="rounded bg-background px-1 py-0.5 font-operational text-[12px] text-foreground" {...p} />
          ),
          blockquote: (p) => (
            <blockquote className="my-3 border-l-2 border-border-strong pl-3 text-muted" {...p} />
          ),
          hr: () => <hr className="my-4 border-border" />,
          table: (p) => (
            <div className="my-3 overflow-x-auto">
              <table className="w-full border-collapse text-[12px]" {...p} />
            </div>
          ),
          th: (p) => (
            <th className="border border-border bg-surface px-2.5 py-1.5 text-left font-medium text-foreground" {...p} />
          ),
          td: (p) => <td className="border border-border px-2.5 py-1.5 align-top" {...p} />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
