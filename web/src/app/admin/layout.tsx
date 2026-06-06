import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Brewing — Admin",
  robots: { index: false, follow: false },
};

/**
 * Standalone admin shell — deliberately separate from the product. No product
 * sidebar, no product session; the admin area has its own password gate.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-background text-foreground">{children}</div>;
}
