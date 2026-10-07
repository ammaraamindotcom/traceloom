import type { ReactNode } from "react";
import { formatEvent } from "../lib/format";

export function SectionLabel({ children }: { children: ReactNode }) { return <p className="section-label">{children}</p>; }
export function EmptyState({ title, children }: { title: string; children: ReactNode }) { return <div className="empty-state"><strong>{title}</strong><p>{children}</p></div>; }
export function SeverityBadge({ severity }: { severity: string }) { return <span className={`badge severity-${severity.toLowerCase()}`}>{formatEvent(severity)}</span>; }
export function LoadingBlock({ children = "Loading security data…" }: { children?: ReactNode }) { return <div className="loading-block" aria-live="polite">{children}</div>; }
export function SignalList({ signals }: { signals: { type: string; description: string; severity: string; evidence?: Record<string, unknown> }[] }) { if (!signals.length) return <EmptyState title="No deterministic signals">No anomalous signals were detected for the current activity set.</EmptyState>; return <ul className="signal-list">{signals.map(signal => <li key={signal.type}><div><strong>{formatEvent(signal.type)}</strong><SeverityBadge severity={signal.severity} /></div><p>{signal.description}</p>{signal.evidence && <details><summary>Evidence</summary><code>{JSON.stringify(signal.evidence, null, 2)}</code></details>}</li>)}</ul>; }
