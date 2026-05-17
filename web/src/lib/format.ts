export function pct(value: unknown): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return '';
  return `${Math.round(Math.max(0, Math.min(1, n)) * 100)}%`;
}
