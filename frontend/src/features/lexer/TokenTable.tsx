import { useState } from "react";
import { DataTable, type Column } from "../../components/DataTable";
import { Badge } from "../../components/Badge";
import { Tabs } from "../../components/Tabs";
import type { Token } from "../../types";

const CATEGORY_TONES: Record<string, "blue" | "green" | "amber" | "purple" | "slate" | "red"> = {
  keyword: "blue",
  identifier: "green",
  literal: "amber",
  operator: "purple",
  comparison: "purple",
  punctuation: "slate",
  eof: "red",
};

export function TokenTable({ tokens }: { tokens: Token[] }) {
  const categories = Array.from(new Set(tokens.map((t) => t.category ?? "other")));
  const [filter, setFilter] = useState<string>("all");

  const filtered = filter === "all" ? tokens : tokens.filter((t) => (t.category ?? "other") === filter);

  const columns: Column<Token>[] = [
    {
      key: "index",
      header: "#",
      align: "right",
      render: (_row, index) => <span className="text-slate-400">{index + 1}</span>,
    },
    {
      key: "type",
      header: "Token type",
      render: (row) => <span className="font-mono text-xs font-semibold">{row.type}</span>,
    },
    {
      key: "lexeme",
      header: "Lexeme",
      render: (row) => (
        <span className="font-mono text-xs text-slate-700 dark:text-slate-200">
          {row.lexeme === "" ? <em className="text-slate-400">end of input</em> : row.lexeme}
        </span>
      ),
    },
    {
      key: "category",
      header: "Category",
      render: (row) => (
        <Badge tone={CATEGORY_TONES[row.category ?? "other"] ?? "slate"}>{row.category}</Badge>
      ),
    },
    { key: "line", header: "Line", align: "right" },
    { key: "column", header: "Column", align: "right" },
  ];

  return (
    <div className="space-y-3">
      <Tabs
        items={[
          { id: "all", label: "All", count: tokens.length },
          ...categories.map((category) => ({
            id: category,
            label: category,
            count: tokens.filter((t) => (t.category ?? "other") === category).length,
          })),
        ]}
        active={filter}
        onChange={setFilter}
      />
      <DataTable
        columns={columns}
        rows={filtered}
        getRowKey={(_row, index) => index}
        className="max-h-[560px]"
      />
    </div>
  );
}
