import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatNumber } from "../../lib/format";
import type { CostComparisonRow } from "../../types";

export function RowsChart({ rows }: { rows: CostComparisonRow[] }) {
  const data = rows.map((row) => ({
    name: row.name,
    rows: row.estimatedRows,
    selected: row.selected,
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" opacity={0.2} />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#a3a3a3" />
          <YAxis
            tick={{ fontSize: 12 }}
            stroke="#a3a3a3"
            tickFormatter={(value: number) => formatNumber(value)}
          />
          <Tooltip
            formatter={(value: number) => [formatNumber(value), "estimated rows"]}
            contentStyle={{
              background: "#0a0a0a",
              border: "1px solid #262626",
              borderRadius: 8,
              fontSize: 12,
              color: "#e5e5e5",
            }}
          />
          <Bar dataKey="rows" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.selected ? "#10b981" : "#8b5cf6"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
