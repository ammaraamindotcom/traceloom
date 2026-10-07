import type { Activity } from "../api/activities";

export function formatEvent(value: string) { return value.replaceAll("_", " "); }
export function formatTime(value: string, includeDate = true) {
  return new Date(value).toLocaleString(undefined, includeDate ? { dateStyle: "medium", timeStyle: "short" } : { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
export function formatPercent(value: number) { return `${Math.round(value * 100)}%`; }
export function activityDetail(activity: Activity) {
  const metadata = activity.metadata;
  const resource = metadata.filename ?? metadata.repository ?? metadata.resource;
  const size = typeof metadata.size_mb === "number" ? ` · ${metadata.size_mb} MB` : "";
  const destination = typeof metadata.destination === "string" ? ` → ${metadata.destination}` : "";
  return resource ? `${String(resource)}${size}${destination}` : Object.keys(metadata).length ? "Metadata recorded" : "No additional metadata";
}
export function signalLabel(signal: string) { return formatEvent(signal); }
