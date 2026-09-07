import { Link } from "@tanstack/react-router";
import { MessageSquareQuote } from "lucide-react";
import type { ReactNode } from "react";

const NAV = [
  { to: "/", label: "Review queue" },
  { to: "/import", label: "Add reviews" },
  { to: "/settings", label: "Business profile" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-border/70 bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-4">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="gradient-warm flex size-9 items-center justify-center rounded-xl text-primary-foreground shadow-[var(--shadow-card)]">
              <MessageSquareQuote className="size-4.5" />
            </span>
            <span className="font-display text-lg font-semibold tracking-tight">
              Reputation Manager
            </span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            {NAV.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                activeOptions={{ exact: item.to === "/" }}
                className="rounded-lg px-3 py-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                activeProps={{ className: "bg-secondary text-foreground font-medium" }}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 pb-20 pt-8">{children}</main>
    </div>
  );
}
