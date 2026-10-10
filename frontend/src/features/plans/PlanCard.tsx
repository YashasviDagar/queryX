import { useState } from "react";
import { Badge } from "../../components/Badge";
import { Tooltip } from "../../components/Tooltip";
import { cn, formatBytes, formatCost, formatNumber } from "../../lib/format";
import type { CandidatePlan } from "../../types";
import { PlanTree } from "./PlanTree";

export function PlanCard({
  plan,
  rank,
  maxCost,
  defaultOpen = false,
}: {
  plan: CandidatePlan;
  rank: number;
  maxCost: number;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen || plan.selected);
  const barWidth = maxCost > 0 ? Math.max(4, (plan.estimatedCost / maxCost) * 100) : 0;

  return (
    <div
      className={cn(
        "rounded-xl border bg-white shadow-sm transition-colors dark:bg-slate-900/60",
        plan.selected
          ? "border-emerald-400 ring-1 ring-emerald-400/40 dark:border-emerald-500/60"
          : "border-slate-200 dark:border-slate-800",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold",
              plan.selected
                ? "bg-emerald-500 text-white"
                : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
            )}
          >
            {plan.name.replace("Plan ", "")}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">{plan.name}</span>
              {plan.selected && <Badge tone="green">Selected</Badge>}
              {rank === 0 && !plan.selected && <Badge tone="amber">Cheapest</Badge>}
              <Badge tone="slate">rank #{rank + 1}</Badge>
            </div>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{plan.description}</p>
          </div>
        </div>
        <div className="text-right">
          <Tooltip label="Educational cost estimate — not real execution time">
            <span className="font-mono text-lg font-semibold text-slate-800 dark:text-slate-100">
              {formatCost(plan.estimatedCost)}
            </span>
          </Tooltip>
          <div className="text-[11px] text-slate-400">estimated cost</div>
        </div>
      </div>

      <div className="px-4">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
          <div
            className={cn(
              "h-full rounded-full",
              plan.selected ? "bg-emerald-500" : "bg-blue-400",
            )}
            style={{ width: `${barWidth}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 px-4 py-3 text-xs">
        <div>
          <div className="text-slate-400">Est. rows</div>
          <div className="font-mono text-slate-700 dark:text-slate-200">
            {formatNumber(plan.estimatedRows)}
          </div>
        </div>
        <div>
          <div className="text-slate-400">Est. memory</div>
          <div className="font-mono text-slate-700 dark:text-slate-200">
            {formatBytes(plan.estimatedMemory)}
          </div>
        </div>
        <div>
          <div className="text-slate-400">Est. operations</div>
          <div className="font-mono text-slate-700 dark:text-slate-200">
            {formatNumber(plan.estimatedOperations)}
          </div>
        </div>
      </div>

      <div className="border-t border-slate-100 px-4 py-2 dark:border-slate-800">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          {open ? "Hide physical plan" : "Show physical plan"}
        </button>
      </div>

      {open && (
        <div className="px-4 pb-4">
          <PlanTree plan={plan.tree} height={360} />
        </div>
      )}
    </div>
  );
}
