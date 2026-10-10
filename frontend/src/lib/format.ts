export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatCost(value: number | null | undefined): string {
  return formatNumber(value, 2);
}

export function formatBytes(value: number | null | undefined): string {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}
