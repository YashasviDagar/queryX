import { useState } from "react";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { DataTable, type Column } from "../components/DataTable";
import { EmptyState, ErrorState } from "../components/States";
import { Tabs } from "../components/Tabs";
import { Stat } from "../components/Stat";
import { cn, formatCost, formatNumber, formatPercent } from "../lib/format";
import { useQuery } from "../store/QueryProvider";
import type { BytecodeLine, PlanCheck } from "../types";

const OP_CLASSES: Array<[RegExp, string]> = [
  [/^(SCAN_OPEN|INDEX_OPEN|NEXT|RESTORE)$/, "text-blue-600 dark:text-blue-400"],
  [/^JUMP/, "text-amber-600 dark:text-amber-400"],
  [/^(HT_|BUF_|MERGE_|AGG_|DISTINCT_|LIMIT_|FLAG_|BIND_)/, "text-violet-600 dark:text-violet-400"],
  [/^(EMIT|MAKE_ROW|HALT)$/, "text-emerald-600 dark:text-emerald-400"],
];

function opClass(op: string): string {
  return OP_CLASSES.find(([pattern]) => pattern.test(op))?.[1] ?? "text-slate-700 dark:text-slate-200";
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "number" && !Number.isInteger(value)) return value.toFixed(2);
  return String(value);
}

const STATUS_TONE = { match: "green", mismatch: "red", skipped: "slate", error: "red" } as const;

function BytecodeListing({ lines, changed }: { lines: BytecodeLine[]; changed?: Set<number> }) {
  return (
    <div className="max-h-[32rem] overflow-auto rounded-lg border border-slate-200 bg-slate-50 font-mono text-xs dark:border-slate-800 dark:bg-slate-950">
      <table className="w-full border-collapse">
        <tbody>
          {lines.map((line) => (
            <tr
              key={line.address}
              className={cn(
                "align-top",
                changed?.has(line.address)
                  ? "bg-amber-100 dark:bg-amber-500/15"
                  : "hover:bg-slate-100 dark:hover:bg-slate-800/40",
              )}
            >
              <td className="select-none px-3 py-0.5 text-slate-400">
                {String(line.address).padStart(4, "0")}
              </td>
              <td className={cn("px-2 py-0.5 font-semibold", opClass(line.op))}>{line.op}</td>
              <td className="whitespace-nowrap px-2 py-0.5 text-slate-700 dark:text-slate-200">{line.args}</td>
              <td className="px-2 py-0.5 text-slate-400">{line.comment && `; ${line.comment}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BytecodePage() {
  const { result } = useQuery();
  const [view, setView] = useState("optimized");
  const codegen = result?.codegen;

  if (!result || !codegen) {
    return (
      <EmptyState
        title="No bytecode yet"
        description="Run a valid query to compile the selected plan to bytecode and execute it on the VM."
      />
    );
  }
  if (!codegen.success) {
    return <ErrorState message={`Code generation failed: ${codegen.error ?? "unknown error"}`} />;
  }

  const execution = codegen.execution!;
  const peephole = codegen.peephole!;
  const unoptimized = codegen.unoptimizedExecution!;
  const checks = codegen.planChecks ?? [];
  const saved = unoptimized.instructionsExecuted - execution.instructionsExecuted;
  const savedPercent = unoptimized.instructionsExecuted ? (saved / unoptimized.instructionsExecuted) * 100 : 0;
  const verified = checks.filter((check) => check.status === "match").length;
  const mismatches = checks.filter((check) => check.status === "mismatch" || check.status === "error").length;
  const executedPlans = checks.filter((check) => check.status !== "skipped").length;
  const skipped = checks.length - executedPlans;
  const afterLines = codegen.bytecode ?? [];
  const beforeLines = codegen.unoptimizedBytecode ?? [];
  // Same length means jumps were retargeted in place, so lines can be compared address by address.
  const changed = new Set<number>();
  if (afterLines.length === beforeLines.length) {
    afterLines.forEach((line, index) => {
      const other = beforeLines[index];
      if (other.op !== line.op || other.args !== line.args) changed.add(line.address);
    });
  }
  const rewrites = peephole.examples;

  const resultColumns: Column<unknown[]>[] = execution.columns.map((name, index) => ({
    key: `${index}`,
    header: name,
    render: (row) => (
      <span className={cn(row[index] === null && "text-slate-400")}>{formatValue(row[index])}</span>
    ),
  }));

  const checkColumns: Column<PlanCheck>[] = [
    {
      key: "name",
      header: "Plan",
      render: (row) => (
        <span className="font-medium">
          {row.name}
          {row.selected && <Badge tone="green" className="ml-2">selected</Badge>}
        </span>
      ),
    },
    { key: "description", header: "Strategy", className: "text-slate-500 dark:text-slate-400" },
    { key: "estimatedCost", header: "Est. cost", align: "right", render: (row) => formatCost(row.estimatedCost) },
    {
      key: "instructionsExecuted",
      header: "VM instructions",
      align: "right",
      render: (row) => formatNumber(row.instructionsExecuted),
    },
    { key: "rowCount", header: "Rows", align: "right", render: (row) => formatNumber(row.rowCount) },
    {
      key: "status",
      header: "Result",
      render: (row) => (
        <Badge tone={STATUS_TONE[row.status]} className={row.reason ? "cursor-help" : undefined}>
          <span title={row.reason}>{row.status === "match" ? "same rows" : row.status}</span>
        </Badge>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Bytecode"
          value={`${peephole.instructionsAfter} instr`}
          hint={`${peephole.instructionsBefore} before peephole`}
        />
        <Stat
          label="Executed on VM"
          value={formatNumber(execution.instructionsExecuted)}
          hint={`${formatPercent(savedPercent)} fewer than unoptimized (${formatNumber(unoptimized.instructionsExecuted)})`}
        />
        <Stat
          label="Result rows"
          value={formatNumber(execution.rowCount)}
          hint={`${formatNumber(execution.elapsedMs, 2)} ms on the VM`}
        />
        <Stat
          label="Plans verified"
          value={`${verified} / ${executedPlans}`}
          hint={
            mismatches
              ? `${mismatches} disagree`
              : `all executed plans return the same rows${skipped ? `; ${skipped} too slow to run` : ""}`
          }
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card
          className="lg:col-span-3"
          title={`Generated bytecode for ${codegen.plan}`}
          subtitle="Produce/consume code generation: each operator becomes a loop, filters become jumps"
        >
          <div className="mb-3 grid gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm sm:grid-cols-2 dark:border-slate-800 dark:bg-slate-950">
            <div>
              <div className="text-xs uppercase tracking-wide text-slate-400">Code size</div>
              <div className="font-semibold tabular-nums">
                {peephole.instructionsBefore} → {peephole.instructionsAfter} instructions
              </div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-slate-400">Instructions run on the VM</div>
              <div className="font-semibold tabular-nums">
                {formatNumber(unoptimized.instructionsExecuted)} → {formatNumber(execution.instructionsExecuted)}{" "}
                <span className="text-emerald-600 dark:text-emerald-400">(−{formatPercent(savedPercent)})</span>
              </div>
            </div>
            <p className="text-xs text-slate-500 sm:col-span-2 dark:text-slate-400">
              Jump threading changes where a jump lands without deleting any instruction, so code size can stay the
              same while the VM runs fewer instructions.
              {changed.size > 0 && " Changed lines are highlighted in both listings."}
            </p>
          </div>
          <Tabs
            className="mb-3"
            items={[
              { id: "optimized", label: "After peephole" },
              { id: "raw", label: "Before peephole" },
              { id: "changes", label: "What changed", count: rewrites.length },
            ]}
            active={view}
            onChange={setView}
          />
          {view === "optimized" && <BytecodeListing lines={afterLines} changed={changed} />}
          {view === "raw" && <BytecodeListing lines={beforeLines} changed={changed} />}
          {view === "changes" &&
            (rewrites.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">
                No pattern matched: the generated code was already locally optimal.
              </p>
            ) : (
              <ol className="max-h-[32rem] space-y-2 overflow-auto">
                {rewrites.map((rewrite, index) => (
                  <li key={index} className="rounded-lg border border-slate-200 p-2 dark:border-slate-800">
                    <div className="mb-1.5 flex items-center gap-2 text-xs">
                      <span className="tabular-nums text-slate-400">{index + 1}.</span>
                      <Badge tone="blue">{rewrite.rule}</Badge>
                    </div>
                    <div className="grid gap-2 font-mono text-[11px] sm:grid-cols-2">
                      <pre className="overflow-auto rounded bg-red-50 p-2 text-red-800 dark:bg-red-500/10 dark:text-red-300">
                        {rewrite.before.join("\n")}
                      </pre>
                      <pre className="overflow-auto rounded bg-emerald-50 p-2 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">
                        {rewrite.after.join("\n")}
                      </pre>
                    </div>
                  </li>
                ))}
              </ol>
            ))}
          {!!codegen.notes?.length && (
            <ul className="mt-3 space-y-1 text-xs text-amber-700 dark:text-amber-300">
              {codegen.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <Card title="Peephole optimizer" subtitle="Local rewrites over the bytecode, repeated to a fixpoint">
            {peephole.rules.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                No pattern matched: the generated code was already locally optimal.
              </p>
            ) : (
              <ul className="space-y-3">
                {peephole.rules.map((rule) => (
                  <li key={rule.rule}>
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-800 dark:text-slate-100">
                      {rule.rule}
                      <Badge tone="blue">×{rule.applications}</Badge>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{rule.description}</p>
                  </li>
                ))}
              </ul>
            )}
            {rewrites.length > 0 && (
              <button
                type="button"
                onClick={() => setView("changes")}
                className="mt-4 text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
              >
                See all {rewrites.length} rewrites →
              </button>
            )}
          </Card>
        </div>
      </div>

      <Card
        title="Query result from the VM"
        subtitle={`Executed on generated sample data: ${(codegen.sampleData ?? [])
          .map((t) => `${t.table} ${formatNumber(t.sampleRows)}`)
          .join(", ")} rows`}
      >
        <DataTable columns={resultColumns} rows={execution.rows} empty="The query returned no rows." />
        {execution.truncated && (
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Showing the first {execution.rows.length} of {formatNumber(execution.rowCount)} rows.
          </p>
        )}
      </Card>

      <Card
        title="Every candidate plan, executed"
        subtitle="Differential testing: plans with different join orders, algorithms and access paths must return the same rows"
      >
        <DataTable
          columns={checkColumns}
          rows={checks}
          getRowKey={(row) => row.id}
          rowClassName={(row) => (row.selected ? "bg-emerald-50/60 dark:bg-emerald-500/5" : undefined)}
        />
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          The cost model charges for disk I/O, but the VM runs in memory, so the cheapest estimated plan is not
          always the one that executes the fewest instructions.
        </p>
      </Card>
    </div>
  );
}
