export function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 45) return "now";
  if (diff < 3600) return `${Math.round(diff / 60)}m`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h`;
  if (diff < 7 * 86400) return `${Math.round(diff / 86400)}d`;
  return new Date(iso).toLocaleDateString();
}

export function dateTime(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : "never";
}
