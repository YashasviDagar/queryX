import type { ReactNode } from "react";
import { cn } from "../lib/format";

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Card({ title, subtitle, actions, children, className, bodyClassName }: CardProps) {
  return (
    <section
      className={cn(
        "rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900/60",
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
          <div>
            {title && (
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</h2>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}
