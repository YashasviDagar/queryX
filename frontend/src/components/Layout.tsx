import { useState, type ReactNode } from "react";
import { NAV_ITEMS } from "../lib/nav";
import { cn } from "../lib/format";
import { useTheme } from "../store/ThemeProvider";
import { useQuery } from "../store/QueryProvider";
import { Badge } from "./Badge";

const ICONS: Record<string, ReactNode> = {
  editor: <path d="M4 5h16v14H4zM8 9l2 3-2 3" />,
  tokens: <path d="M4 6h16M4 12h10M4 18h7" />,
  ast: <path d="M12 3v6M12 9l-6 6M12 9l6 6M6 15v6M18 15v6" />,
  ir: <path d="M12 3v5M12 8l-5 5M12 8l5 5M7 13v5M17 13v5M4 20h6M14 20h6" />,
  plans: <path d="M4 4h7v7H4zM13 4h7v7h-7zM8 13v7h8v-7" />,
  bytecode: <path d="M8 6l-5 6 5 6M16 6l5 6-5 6M14 4l-4 16" />,
};

function NavIcon({ id }: { id: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      {ICONS[id] ?? <circle cx="12" cy="12" r="3" />}
    </svg>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-600 font-mono text-sm font-bold text-white">
        Q
      </span>
      <div>
        <div className="text-sm font-semibold leading-tight">queryX</div>
        <div className="text-[11px] text-slate-500 dark:text-slate-400">
          Explainable SQL Optimizer
        </div>
      </div>
    </div>
  );
}

function NavList({
  active,
  onSelect,
}: {
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <nav className="space-y-0.5">
      {NAV_ITEMS.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onSelect(item.id)}
          title={item.hint}
          className={cn(
            "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors",
            active === item.id
              ? "bg-blue-50 font-medium text-blue-700 dark:bg-blue-500/15 dark:text-blue-300"
              : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800/60",
          )}
        >
          <NavIcon id={item.id} />
          {item.label}
          {item.isNew && (
            <span className="ml-auto rounded bg-blue-500 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white dark:text-slate-950">
              New
            </span>
          )}
        </button>
      ))}
    </nav>
  );
}

export function Layout({
  active,
  onNavigate,
  children,
}: {
  active: string;
  onNavigate: (id: string) => void;
  children: ReactNode;
}) {
  const { theme, toggle } = useTheme();
  const { run, loading, result } = useQuery();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleNavigate = (id: string) => {
    onNavigate(id);
    setMenuOpen(false);
  };

  return (
    <div className="flex min-h-screen bg-slate-100 text-slate-900 dark:bg-surface dark:text-slate-100">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-4 dark:border-slate-800 dark:bg-slate-950/60 md:flex">
        <div className="px-2 pb-4">
          <Brand />
        </div>
        <div className="flex-1">
          <NavList active={active} onSelect={onNavigate} />
        </div>
        <div className="px-2 pt-4 text-[11px] text-slate-400 dark:text-slate-500">
          {result?.metrics?.totalMs !== undefined && (
            <div>last compile: {result.metrics.totalMs} ms</div>
          )}
          <div className="mt-1">compiler pipeline v1.0</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMenuOpen((value) => !value)}
              aria-label="Toggle navigation"
              aria-expanded={menuOpen}
              className="rounded-md border border-slate-300 p-1.5 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 md:hidden"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.8}
                strokeLinecap="round"
                className="h-4 w-4"
              >
                {menuOpen ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
              </svg>
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold">
                {NAV_ITEMS.find((item) => item.id === active)?.label ?? "queryX"}
              </h1>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                {NAV_ITEMS.find((item) => item.id === active)?.hint}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {result?.success && (
              <Badge tone="green">
                {result.metrics?.candidateCount ?? 0} plans
              </Badge>
            )}
            {result && !result.success && <Badge tone="red">errors</Badge>}
            <button
              type="button"
              onClick={toggle}
              className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {theme === "dark" ? "Light" : "Dark"}
            </button>
            <button
              type="button"
              onClick={() => run()}
              disabled={loading}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Running…" : "Run & Optimize"}
            </button>
          </div>
        </header>

        {menuOpen && (
          <div className="border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950/80 md:hidden">
            <div className="mb-3">
              <Brand />
            </div>
            <NavList active={active} onSelect={handleNavigate} />
          </div>
        )}

        <main className="min-w-0 flex-1 p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
