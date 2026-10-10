import type { ReactNode } from "react";

export function Tooltip({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-xs text-white shadow-lg group-hover:block dark:bg-slate-700">
        {label}
      </span>
    </span>
  );
}
