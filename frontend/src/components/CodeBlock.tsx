import { cn } from "../lib/format";

export function CodeBlock({
  code,
  className,
  maxHeight = "max-h-96",
}: {
  code: string;
  className?: string;
  maxHeight?: string;
}) {
  return (
    <pre
      className={cn(
        "overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs leading-relaxed text-slate-800 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-200",
        maxHeight,
        className,
      )}
    >
      {code}
    </pre>
  );
}
