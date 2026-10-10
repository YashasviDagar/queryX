import type { ReactNode } from "react";
import { cn } from "../lib/format";

type Tone = "default" | "blue" | "green" | "amber" | "red" | "purple" | "slate";

const TONES: Record<Tone, string> = {
  default: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  blue: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  green: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  amber: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
  red: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  purple: "bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
  slate: "bg-slate-200 text-slate-700 dark:bg-slate-700/50 dark:text-slate-200",
};

export function Badge({
  children,
  tone = "default",
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function opTone(op: string): Tone {
  const normalized = op.toLowerCase();
  if (normalized.includes("scan")) return "blue";
  if (normalized.includes("join")) return "purple";
  if (normalized.includes("filter")) return "amber";
  if (normalized.includes("distinct")) return "green";
  if (normalized.includes("aggregate") || normalized.includes("group")) return "green";
  if (normalized.includes("sort") || normalized.includes("limit")) return "slate";
  return "default";
}
