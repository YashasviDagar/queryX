import { Badge } from "../../components/Badge";
import { DataTable, type Column } from "../../components/DataTable";
import { formatBytes, formatCost, formatNumber } from "../../lib/format";
import type { CostComparisonRow } from "../../types";

const COLUMNS: Column<CostComparisonRow>[] = [
  {
    key: "name",
    header: "Plan",
    render: (row) => (
      <span className="flex items-center gap-2">
        <span className="font-medium">{row.name}</span>
        {row.selected && <Badge tone="green">selected</Badge>}
      </span>
    ),
  },
  { key: "joinAlgorithm", header: "Join" },
  {
    key: "estimatedCost",
    header: "Cost",
    align: "right",
    render: (row) => formatCost(row.estimatedCost),
  },
  {
    key: "estimatedRows",
    header: "Rows",
    align: "right",
    render: (row) => formatNumber(row.estimatedRows),
  },
  {
    key: "estimatedMemory",
    header: "Memory",
    align: "right",
    render: (row) => formatBytes(row.estimatedMemory),
  },
  {
    key: "estimatedOperations",
    header: "Operations",
    align: "right",
    render: (row) => formatNumber(row.estimatedOperations),
  },
];

export function CostComparison({ rows }: { rows: CostComparisonRow[] }) {
  return (
    <DataTable
      columns={COLUMNS}
      rows={rows}
      getRowKey={(row) => row.id}
      rowClassName={(row) => (row.selected ? "bg-emerald-50 dark:bg-emerald-500/10" : undefined)}
    />
  );
}
