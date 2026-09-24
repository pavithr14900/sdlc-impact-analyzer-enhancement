import { FileCode2, Info, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import type { AnalysisStatus, Evidence } from "./types";

export function Card({ icon, title, subtitle, action, children, className = "" }: { icon: ReactNode; title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`li-card ${className}`}>
    <header className="li-card-heading">
      <span className="li-heading-icon">{icon}</span>
      <div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>
      {action && <div className="li-heading-action">{action}</div>}
    </header>
    {children}
  </section>;
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="li-empty"><Info size={22} /><p>{children}</p></div>;
}

const STATUS_LABELS: Record<AnalysisStatus, string> = { NOT_STARTED: "Not started", SCANNING: "Scanning", INDEXING: "Indexing", ANALYZING: "Analyzing", COMPLETED: "Completed", FAILED: "Failed" };
export function StatusBadge({ status }: { status: AnalysisStatus }) {
  return <span className={`li-status li-status-${status.toLowerCase()}`}>
    {!["COMPLETED", "FAILED", "NOT_STARTED"].includes(status) && <LoaderCircle size={12} className="li-spin" />}
    {STATUS_LABELS[status] || status}
  </span>;
}

export function EvidencePanel({ evidence = [] }: { evidence?: Evidence[] }) {
  if (!evidence.length) return null;
  return <details className="li-evidence">
    <summary><FileCode2 size={14} /> Source evidence ({evidence.length})</summary>
    <ul>
      {evidence.map((item, index) => <li key={`${item.repository}:${item.file}:${item.lineStart}:${index}`}>
        <strong>{item.repository}</strong>
        <code>
          {item.file}
          {item.lineStart ? `:${item.lineStart}${item.lineEnd && item.lineEnd !== item.lineStart ? `–${item.lineEnd}` : ""}` : ""}
        </code>
        {item.symbol && <span>{item.symbol}</span>}
        {item.evidenceType && <small>{item.evidenceType.toLowerCase()}</small>}
        {item.snippet && <pre>{item.snippet}</pre>}
      </li>)}
    </ul>
  </details>;
}
