import type { KeyboardEvent } from "react";

export function SqlEditor({
  value,
  onChange,
  onRun,
}: {
  value: string;
  onChange: (value: string) => void;
  onRun: () => void;
}) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      onRun();
    }
    if (event.key === "Tab") {
      event.preventDefault();
      const target = event.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const next = `${value.slice(0, start)}  ${value.slice(end)}`;
      onChange(next);
      requestAnimationFrame(() => {
        target.selectionStart = target.selectionEnd = start + 2;
      });
    }
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-300 bg-slate-50 dark:border-slate-700 dark:bg-slate-950">
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        spellCheck={false}
        rows={9}
        className="w-full resize-y bg-transparent p-3 font-mono text-sm leading-relaxed text-slate-800 outline-none placeholder:text-slate-400 dark:text-slate-100"
        placeholder="SELECT ... FROM ..."
      />
      <div className="flex items-center justify-between border-t border-slate-200 px-3 py-1.5 text-[11px] text-slate-400 dark:border-slate-800">
        <span>Ctrl/Cmd + Enter to run</span>
        <span>{value.length} chars</span>
      </div>
    </div>
  );
}
