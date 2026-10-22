import { Card } from "./Card";

export function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card bodyClassName="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-800 dark:text-slate-100">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-400">{hint}</div>}
    </Card>
  );
}
