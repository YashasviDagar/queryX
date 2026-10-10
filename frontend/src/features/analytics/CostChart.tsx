import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCost, formatNumber } from "../../lib/format";
import type { CostComparisonRow } from "../../types";

export function CostComparisonChart({ rows }: { rows: CostComparisonRow[] }) {
  const data = rows.map((row) => ({
    name: row.name,
    cost: row.estimatedCost,
    selected: row.selected,
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#94a3b8" />
          <YAxis
            tick={{ fontSize: 12 }}
            stroke="#94a3b8"
            tickFormatter={(value: number) => formatNumber(value)}
          />
          <Tooltip
            formatter={(value: number) => [formatCost(value), "estimated cost"]}
            contentStyle={{
              background: "#0f172a",
              border: "1px solid #334155",
              borderRadius: 8,
              fontSize: 12,
              color: "#e2e8f0",
            }}
          />
          <Bar dataKey="cost" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.selected ? "#10b981" : "#3b82f6"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
