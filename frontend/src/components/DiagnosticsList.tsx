import type { CompilerDiagnostic } from "../types";
import { Badge } from "./Badge";

const STAGE_TONES: Record<string, "blue" | "amber" | "purple" | "red"> = {
  lexer: "blue",
  parser: "amber",
  semantic: "purple",
};

export function DiagnosticsList({
  diagnostics,
  title = "Diagnostics",
}: {
  diagnostics: CompilerDiagnostic[];
  title?: string;
}) {
  if (!diagnostics.length) return null;
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {title} ({diagnostics.length})
      </h3>
      <ul className="space-y-2">
        {diagnostics.map((diagnostic, index) => (
          <li
            key={`${diagnostic.code}-${index}`}
            className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm dark:border-red-500/30 dark:bg-red-500/10"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="red">{diagnostic.code}</Badge>
              <Badge tone={STAGE_TONES[diagnostic.stage] ?? "slate"}>{diagnostic.stage}</Badge>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                line {diagnostic.line}, column {diagnostic.column}
              </span>
            </div>
            <p className="mt-2 text-red-800 dark:text-red-200">{diagnostic.message}</p>
            {diagnostic.suggestion && (
              <p className="mt-1 text-xs text-red-700/80 dark:text-red-300/80">
                Suggestion: {diagnostic.suggestion}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
