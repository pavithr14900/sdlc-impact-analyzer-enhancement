import { ArrowRight, ArrowRightLeft, BookOpen, Boxes, Braces, ChartNoAxesColumnIncreasing, ChevronRight, Clock3, Database, FileCode2, FileText, GitBranch, ListTree, LoaderCircle, MessageCircle, Network, Share2, Trash2, Workflow, Zap } from "lucide-react";
import type { ReactNode } from "react";
import { Card, EmptyState, StatusBadge } from "./shared";
import type { Analysis, AnalysisSummary, DetailView, Overview } from "./types";

const METRICS = [
  { key: "repositories", label: "Repositories", icon: GitBranch, color: "purple" },
  { key: "services", label: "Services", icon: Boxes, color: "blue" },
  { key: "classes", label: "Classes", icon: FileCode2, color: "green" },
  { key: "apis", label: "APIs", icon: Braces, color: "amber" },
  { key: "databaseTables", label: "Database Tables", icon: Database, color: "pink" },
  { key: "externalIntegrations", label: "External Integrations", icon: Share2, color: "pink" },
  { key: "scheduledJobs", label: "Scheduled Jobs", icon: Clock3, color: "blue" },
] as const;

export function ApplicationOverview({ overview, action }: { overview?: Overview | null; action?: ReactNode }) {
  return <Card
    icon={<ChartNoAxesColumnIncreasing size={21} />}
    title="Application Overview"
    subtitle="Components discovered across your codebases."
    action={action}>
    <div className="li-metrics">
      {METRICS.map(({ key, label, icon: Icon, color }) => <div className={`li-metric ${key === "scheduledJobs" ? "li-metric-jobs" : ""}`} key={key}>
        <span className={`li-metric-icon li-color-${color}`}><Icon size={23} /></span>
        <div><strong>{overview?.[key] == null ? "—" : overview[key].toLocaleString()}</strong><span>{label}</span></div>
      </div>)}
    </div>
    <p className="li-metric-caption">
      {overview ? "Source-derived counts." : "Analyze a repository to populate these metrics."}
    </p>
  </Card>;
}

export function ApplicationOverviewDetail({ analysis }: { analysis: Analysis }) {
  const insights = analysis.insights;
  const facts = analysis.facts || [];
  const byRepository = new Map<string, Record<string, number>>();
  for (const fact of facts) {
    const repository = fact.repository || "Unknown";
    const counts = byRepository.get(repository) || {};
    counts[fact.kind] = (counts[fact.kind] || 0) + 1;
    byRepository.set(repository, counts);
  }

  return <div className="li-detail-stack">

    <ApplicationOverview overview={analysis.overview} />

    <Card
      icon={<ChartNoAxesColumnIncreasing size={21} />}
      title="Executive Summary"
      subtitle="AI-synthesized overview grounded in the discovered evidence.">
      {!insights?.summary ? <EmptyState>An AI-synthesized summary was not generated for this analysis. This can happen if AI insight synthesis was skipped; check the analysis limitations for details.</EmptyState> : <>
        <p className="li-markdown">{insights.summary}</p>
        {insights.key_risks.length > 0 && <>
          <h4>Key Risks</h4>
          <ul>{insights.key_risks.map((item, index) => <li key={index}>{item}</li>)}</ul>
        </>}
        {insights.modernization_priorities.length > 0 && <>
          <h4>Modernization Priorities</h4>
          <ul>{insights.modernization_priorities.map((item, index) => <li key={index}>{item}</li>)}</ul>
        </>}
        {insights.open_questions.length > 0 && <>
          <h4>Open Questions</h4>
          <ul>{insights.open_questions.map((item, index) => <li key={index}>{item}</li>)}</ul>
        </>}
      </>}
    </Card>

    <Card
      icon={<GitBranch size={21} />}
      title="Repository Breakdown"
      subtitle="Discovered component counts per repository.">
      {!byRepository.size ? <EmptyState>No discovered components are available for a repository breakdown yet.</EmptyState> : <div className="li-repo-breakdown">
        {[...byRepository.entries()].map(([repository, counts]) => <div key={repository} className="li-repo-breakdown-row">
          <strong>{repository}</strong>
          <span>{Object.entries(counts).map(([kind, count]) => `${kind}: ${count}`).join(" · ")}</span>
        </div>)}
      </div>}
    </Card>

  </div>;
}

export function RecentAnalyses({ analyses, loading, error, onOpen, onDelete, deletingIds, deleteError, onViewAll, full = false, selectedId, onRefresh }: {
  analyses: AnalysisSummary[];
  loading: boolean;
  error?: string;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  deletingIds: string[];
  deleteError?: string;
  onViewAll?: () => void;
  full?: boolean;
  selectedId?: string;
  onRefresh: () => void;
}) {
  return <Card
    icon={<Clock3 size={20} />}
    title="Recent Analyses"
    className={`li-recent-card${full ? " li-recent-full" : ""}`}
    action={full ? <button type="button" className="li-link" onClick={onRefresh} disabled={loading}>Refresh</button> : <button type="button" className="li-link" onClick={onViewAll}>View all <ArrowRight size={14} /></button>}>

    {error ? <div className="li-error" role="alert">
      {error}
      <button type="button" className="li-link" onClick={onRefresh}>Retry</button>
    </div> : loading && !analyses.length ? <EmptyState>Loading recent analyses…</EmptyState> : !analyses.length ? <EmptyState>Your analyzed repositories will appear here. Open a previous analysis anytime without rescanning.</EmptyState> : <div className="li-recent-list" role="region" aria-label="Recent analyses list" tabIndex={0}>
      {analyses.map((analysis) => <div
        key={analysis.analysisId}
        className={`li-recent-row ${selectedId === analysis.analysisId ? "selected" : ""}`}>
        <button type="button" className="li-recent-item" onClick={() => onOpen(analysis.analysisId)} disabled={deletingIds.includes(analysis.analysisId)}>
          <GitBranch size={22} />
          <span><strong>{analysis.name}</strong><small>{formatTime(analysis.updatedAt || analysis.createdAt)}</small></span>
          <StatusBadge status={analysis.status} />
          <ChevronRight size={15} />
        </button>
        <button type="button" className="li-icon-button li-delete-analysis"
          aria-label={`Delete analysis ${analysis.name}`} title="Delete saved analysis"
          disabled={deletingIds.includes(analysis.analysisId)} onClick={() => onDelete(analysis.analysisId)}>
          {deletingIds.includes(analysis.analysisId) ? <LoaderCircle size={15} className="li-spin" /> : <Trash2 size={15} />}
        </button>
      </div>)}
    </div>}
    {deleteError && <p className="li-error" role="alert">{deleteError}</p>}

  </Card>;
}

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

const ACTIONS = [
  { view: "documentation", label: "Generate Documentation", icon: FileText },
  { view: "architecture", label: "Explore Architecture", icon: Network },
  { view: "business-rules", label: "Find Business Rules", icon: BookOpen },
  { view: "flows", label: "Trace Application Flow", icon: Workflow },
  { view: "chat", label: "Ask the Codebase", icon: MessageCircle },
  { view: "change-impact", label: "Analyze Change Impact", icon: ArrowRightLeft },
] as const;

export function QuickActions({ ready, onNavigate, onChangeImpact }: { ready: boolean; onNavigate: (view: DetailView) => void; onChangeImpact: () => void }) {
  return <Card icon={<Zap size={21} />} title="Quick Actions" subtitle="Explore and understand your legacy system.">
    <div className="li-quick-actions">
      {ACTIONS.map(({ view, label, icon: Icon }) => <button
        type="button"
        key={view}
        disabled={view !== "change-impact" && !ready}
        onClick={() => view === "change-impact" ? onChangeImpact() : onNavigate(view)}>
        <Icon size={15} />
        <span>{label}</span>
        <ChevronRight size={14} />
      </button>)}
    </div>
    {!ready && <p className="li-muted"><ListTree size={13} /> Complete an analysis to explore its insights.</p>}
  </Card>;
}
