import type { ReactNode } from "react";
import { cn } from "../lib/format";

export function Loading({ label = "Processing…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-slate-500 dark:text-slate-400">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-blue-500 dark:border-slate-700 dark:border-t-blue-400" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-slate-300 py-16 text-center dark:border-slate-700",
        className,
      )}
    >
      <p className="text-sm font-medium text-slate-700 dark:text-slate-200">{title}</p>
      {description && (
        <p className="max-w-md text-xs text-slate-500 dark:text-slate-400">{description}</p>
      )}
      {action}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-300">
      {message}
    </div>
  );
}
