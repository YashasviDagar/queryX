import type { ReactNode } from "react";
import { cn } from "../lib/format";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render?: (row: T, index: number) => ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowKey?: (row: T, index: number) => string | number;
  empty?: ReactNode;
  className?: string;
  rowClassName?: (row: T, index: number) => string | undefined;
}

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  empty,
  className,
  rowClassName,
}: DataTableProps<T>) {
  if (!rows.length) {
    return <div className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">{empty ?? "No data"}</div>;
  }
  return (
    <div className={cn("overflow-auto", className)}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left dark:border-slate-800">
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  "whitespace-nowrap px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400",
                  column.align === "right" && "text-right",
                  column.align === "center" && "text-center",
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={getRowKey ? getRowKey(row, index) : index}
              className={cn(
                "border-b border-slate-100 last:border-0 hover:bg-slate-50 dark:border-slate-800/60 dark:hover:bg-slate-800/30",
                rowClassName?.(row, index),
              )}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn(
                    "px-3 py-2 align-top text-slate-700 dark:text-slate-200",
                    column.align === "right" && "text-right tabular-nums",
                    column.align === "center" && "text-center",
                    column.className,
                  )}
                >
                  {column.render
                    ? column.render(row, index)
                    : ((row as Record<string, unknown>)[column.key] as ReactNode)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
