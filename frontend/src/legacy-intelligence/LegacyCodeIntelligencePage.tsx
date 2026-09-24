import { useEffect, useRef } from "react";
import { ArrowLeft, ArrowRight, Info, Network, Plus } from "lucide-react";
import { ApplicationOverview, ApplicationOverviewDetail, QuickActions, RecentAnalyses } from "./DashboardPanels";
import DocumentationGenerator from "./DocumentationGenerator";
import { ApplicationFlows, BusinessRules } from "./InsightViews";
import LegacyChat from "./LegacyChat";
import RepositorySelector from "./RepositorySelector";
import LegacyArchitectureDiagram from "./LegacyArchitectureDiagram";
import { Card, EmptyState, StatusBadge } from "./shared";
import { isRunning } from "./types";
import type { useLegacyAnalysis } from "./useLegacyAnalysis";
import "./legacyIntelligence.css";

export default function LegacyCodeIntelligencePage({ state, onChangeImpact }: { state: ReturnType<typeof useLegacyAnalysis>; onChangeImpact: () => void }) {
  const { analysis, route } = state;
  const ready = analysis?.status === "COMPLETED";
  const running = isRunning(analysis?.status);
  const generatedSections = useRef<HTMLElement>(null);
  const pendingCompletion = useRef(false);
  const observedAnalysis = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (state.starting) pendingCompletion.current = true;
    if (observedAnalysis.current !== analysis?.analysisId) {
      observedAnalysis.current = analysis?.analysisId;
      pendingCompletion.current = state.starting || running;
    }
    if (running) pendingCompletion.current = true;
    if (analysis?.status === "FAILED") pendingCompletion.current = false;
    if (!ready || !pendingCompletion.current || route.view !== "overview") return;
    const frame = requestAnimationFrame(() => {
      const target = generatedSections.current;
      if (!target) return;
      pendingCompletion.current = false;
      target.focus({ preventScroll: true });
      target.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "start",
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [analysis?.analysisId, analysis?.status, ready, running, route.view, state.starting]);

  const recentPanel = (full = false) => <RecentAnalyses
    analyses={state.recent}
    loading={state.recentLoading}
    error={state.recentError}
    onOpen={(id) => state.navigate("overview", id)}
    onViewAll={() => state.navigate("recent")}
    selectedId={analysis?.analysisId}
    onDelete={(id) => void state.deleteAnalysis(id)}
    deletingIds={state.deletingIds}
    deleteError={state.deleteError}
    full={full}
    onRefresh={() => void state.refreshRecent()} />;

  return <div className={`li-page ${route.view === "overview" ? "li-home" : "li-detail-page"}`}>

    {(route.view !== "overview" || analysis) && <div className="li-view-toolbar">
      <button
        type="button"
        className="li-link"
        onClick={() => {
          if (route.view !== "overview") {
            state.navigate("overview");
          } else {
            state.navigate("overview");
            const el = document.getElementById('legacy-repository-source');
            if (el) (el as HTMLInputElement).focus();
          }
        }}>
        {route.view !== "overview" ? <ArrowLeft size={15} /> : <Plus size={15} />}
        {route.view !== "overview" ? "Back to overview" : "Start new analysis"}
      </button>
      {analysis && <span><strong>{analysis.name}</strong><StatusBadge status={analysis.status} /></span>}
    </div>}

    {state.error && <div className="li-error li-global-error" role="alert">
      {state.error}
      {route.analysisId && <button type="button" className="li-link" onClick={state.retry}>Retry loading analysis</button>}
    </div>}

    {analysis?.status === "FAILED" && <div className="li-error" role="alert">Analysis failed:
      {analysis.error || "The analysis could not be completed. Review the source and try again."}
    </div>}

    {state.loading && !analysis && <div className="li-loading" role="status">Loading saved analysis…</div>}

    {route.view === "recent" ? recentPanel(true) : route.view === "overview" ? <>

      <div className="li-grid li-top-grid">
        <RepositorySelector busy={state.starting || running} onAnalyze={state.startAnalysis} />
        {recentPanel()}
      </div>

      {analysis?.limitations && analysis.limitations.length > 0 && <details className="li-limitations">
        <summary><Info size={15} />Analysis coverage and limitations ({analysis.limitations.length})</summary>
        <ul>{analysis.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
      </details>}

      {analysis ? <section ref={generatedSections} className="li-generated-sections" tabIndex={-1} aria-label="Generated analysis sections">

        <div className="li-grid li-insight-grid">
          <ApplicationOverview
            overview={analysis?.overview}
            action={ready ? <button type="button" className="li-link" onClick={() => state.navigate("application-overview")} aria-label="View full application overview">
              <ArrowRight size={17} />
            </button> : undefined} />
          <QuickActions ready={ready} onNavigate={state.navigate} onChangeImpact={onChangeImpact} />
        </div>

      </section> : <p className="li-muted li-collapsed-hint">Application overview and quick actions will appear here once you start an analysis.</p>}

    </> : !ready || !analysis ? <Card icon={<Info size={20} />} title="Analysis required">
      <EmptyState>
        {running ? "This view will be available when the analysis finishes." : "Complete an analysis or open a completed result from Recent Analyses to explore this view."}
      </EmptyState>
    </Card> : <div key={`${analysis.analysisId}-${route.view}`}>

      {route.view === "application-overview" && <ApplicationOverviewDetail analysis={analysis} />}

      {route.view === "architecture" && <Card
        icon={<Network size={22} />}
        title="System Architecture"
        subtitle="Components and relationships supported by the analyzed source.">
        <LegacyArchitectureDiagram graph={analysis.architecture} />
      </Card>}

      {route.view === "documentation" && <DocumentationGenerator analysisId={analysis.analysisId} />}

      {route.view === "business-rules" && <BusinessRules key={analysis.analysisId} analysisId={analysis.analysisId} rules={analysis.businessRules || []} narrative={analysis.narratives?.businessRules} />}

      {route.view === "flows" && <ApplicationFlows key={analysis.analysisId} analysisId={analysis.analysisId} flows={analysis.flows || []} narrative={analysis.narratives?.flows} />}

      {route.view === "chat" && <LegacyChat analysisId={analysis.analysisId} ready focus />}

    </div>}

  </div>;
}
