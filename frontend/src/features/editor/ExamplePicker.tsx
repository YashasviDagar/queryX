import type { ExampleQuery } from "../../types";
import { cn } from "../../lib/format";

export function ExamplePicker({
  examples,
  onSelect,
  activeId,
}: {
  examples: ExampleQuery[];
  onSelect: (example: ExampleQuery) => void;
  activeId?: string;
}) {
  if (!examples.length) return null;
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {examples.map((example) => (
        <button
          key={example.id}
          type="button"
          onClick={() => onSelect(example)}
          className={cn(
            "rounded-lg border p-3 text-left transition-colors",
            activeId === example.id
              ? "border-blue-400 bg-blue-50 dark:border-blue-500/50 dark:bg-blue-500/10"
              : "border-slate-200 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-800 dark:hover:border-slate-700 dark:hover:bg-slate-800/40",
          )}
        >
          <div className="text-sm font-medium text-slate-800 dark:text-slate-100">
            {example.title}
          </div>
          <div className="mt-0.5 line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
            {example.description}
          </div>
        </button>
      ))}
    </div>
  );
}
