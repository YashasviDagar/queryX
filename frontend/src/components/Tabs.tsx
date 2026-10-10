import { cn } from "../lib/format";

export interface TabItem {
  id: string;
  label: string;
  count?: number;
}

export function Tabs({
  items,
  active,
  onChange,
  className,
}: {
  items: TabItem[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800", className)}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          className={cn(
            "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors",
            active === item.id
              ? "border-blue-500 text-blue-600 dark:text-blue-400"
              : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200",
          )}
        >
          {item.label}
          {item.count !== undefined && (
            <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
              {item.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
