import { useEffect, useState } from "react";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { DataTable, type Column } from "../components/DataTable";
import { EmptyState, ErrorState, Loading } from "../components/States";
import { api } from "../services/api";
import { formatNumber } from "../lib/format";
import type { ColumnStats, StatisticsResponse, TableStats } from "../types";

export function SchemaPage() {
  const [data, setData] = useState<StatisticsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .statistics()
      .then(setData)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Failed to load statistics"),
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading label="Loading statistics…" />;
  if (error) return <ErrorState message={error} />;
  if (!data || !data.tables.length) {
    return <EmptyState title="No statistics available" description="Configure statistics.yaml." />;
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {data.tables.map((table) => (
          <Card key={table.name} bodyClassName="p-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold">{table.name}</span>
              <Badge tone="blue">{formatNumber(table.rows)} rows</Badge>
            </div>
            <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              {table.columns.length} columns · {table.indexes.length} indexes
            </div>
          </Card>
        ))}
      </div>

      {data.tables.map((table) => (
        <TableCard key={table.name} table={table} />
      ))}

      <Card
        title="Cost model constants"
        subtitle="Transparent, configurable estimates — not real execution-time predictions"
      >
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(data.costConfig).map(([key, value]) => (
            <div
              key={key}
              className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-1.5 text-xs dark:border-slate-800"
            >
              <span className="font-mono text-slate-500 dark:text-slate-400">{key}</span>
              <span className="font-mono text-slate-800 dark:text-slate-100">{value}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function TableCard({ table }: { table: TableStats }) {
  const columns: Column<ColumnStats>[] = [
    {
      key: "name",
      header: "Column",
      render: (row) => <span className="font-mono text-xs">{row.name}</span>,
    },
    {
      key: "dataType",
      header: "Type",
      render: (row) => <Badge tone="slate">{row.dataType}</Badge>,
    },
    {
      key: "distinct",
      header: "Distinct",
      align: "right",
      render: (row) => formatNumber(row.distinct),
    },
    {
      key: "selectivity",
      header: "Equality selectivity",
      align: "right",
      render: (row) =>
        row.distinct > 0 ? `1 / ${formatNumber(row.distinct)}` : "—",
    },
    {
      key: "nullable",
      header: "Nullable",
      align: "center",
      render: (row) => (row.nullable ? "yes" : "no"),
    },
    {
      key: "indexed",
      header: "Indexed",
      align: "center",
      render: (row) =>
        row.indexed ? <Badge tone="green">indexed</Badge> : <span className="text-slate-400">—</span>,
    },
  ];

  return (
    <Card
      title={`${table.name}`}
      subtitle={`${formatNumber(table.rows)} rows`}
      actions={
        <div className="flex flex-wrap gap-1">
          {table.indexes.map((index) => (
            <Badge key={index.name} tone="purple">
              {index.name}
            </Badge>
          ))}
        </div>
      }
    >
      <DataTable columns={columns} rows={table.columns} getRowKey={(row) => row.name} />
    </Card>
  );
}
