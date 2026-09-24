import { useId, useRef, useState } from "react";
import { ArrowRight, CheckCircle2, ChevronDown, ClipboardList, Download, Eye, FileCode2, FileSearch, FolderOpen, GitBranch, Info, ListChecks, ShieldAlert } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./changeImpact.css";
import "./changeImpactReport.css";

type Severity = "High" | "Medium" | "Low" | "Unknown";
export type MemoryEvidence = {
  id: string; project: string; tool: string;
  arguments: Record<string, unknown>; result: unknown;
};
export type ImpactReport = {
  title: string; summary: string; overall_risk: Severity; risk_reason: string;
  behavior_changes?: { area: string; before: string; after: string; user_impact: string; evidence_ids: string[] }[];
  affected_components: { name: string; file: string; impact: "Direct" | "Indirect" | "Review"; reason: string; action: string; evidence_ids: string[] }[];
  dependencies: { source: string; target: string; relationship: string; impact: string; evidence_ids: string[] }[];
  risks: { title: string; severity: Severity; detail: string; mitigation: string; evidence_ids: string[] }[];
  contract_impacts?: { area: string; status: string; detail: string; action: string; evidence_ids: string[] }[];
  actions: { title: string; detail: string; validation?: string }[];
  tests: { scenario: string; expected_result: string; purpose?: string }[];
  open_questions: string[];
};
export type ImpactResult = {
  document: string; change?: string; report?: ImpactReport | null;
  dependencies?: { project: string; symbol: string; evidence_id: string; trace: unknown }[];
  indexed?: { path: string; project: string; index: unknown }[];
  findings?: { evidence: MemoryEvidence[]; warnings: string[] };
};
type Props = { result: string; data?: ImpactResult; onPreview?: () => void; onDownload?: () => void };
const TOOL_LABELS: Record<string, string> = {
  index_repository: "Repository index", get_architecture: "Repository overview",
  check_index_coverage: "Index coverage", search_graph: "Matching code",
  search_code: "Source matches", get_code_snippet: "Source excerpt",
  trace_path: "Dependency trace", trace_call_path: "Dependency trace",
};
const basename = (value: string) => value.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || value;
const severityClass = (value: string) => ["High", "Medium", "Low"].includes(value) ? value.toLowerCase() : "unknown";
const markdownPlugins = [remarkGfm];
const impactLabels = { Direct: "Edit directly", Indirect: "Check downstream behavior", Review: "Confirm scope" };

function EvidenceContent({ item }: { item: MemoryEvidence }) {
  const value = item.result && typeof item.result === "object" && !Array.isArray(item.result)
    ? item.result as Record<string, unknown> : {};
  const file = typeof value.file_path === "string" ? value.file_path : "";
  const source = typeof value.source === "string" ? value.source : "";
  const subject = [item.arguments.qualified_name, item.arguments.function_name, item.arguments.query, item.arguments.pattern]
    .find((entry): entry is string => typeof entry === "string");
  return <div className="ci-source-content">
    {subject && <p className="ci-source-subject">{subject}</p>}
    {file && <p className="ci-source-location"><FileCode2 size={14} /><code>{file}{typeof value.start_line === "number" ? `:${value.start_line}` : ""}</code></p>}
    {source && <pre className="ci-source-code"><code>{source}</code></pre>}
    {item.tool === "index_repository" && <p className="ci-source-subject">
      {typeof value.nodes === "number" && `${value.nodes.toLocaleString()} indexed nodes. `}
      {typeof value.edges === "number" && `${value.edges.toLocaleString()} relationships. `}
      These describe the repository index, not the number of affected components.
    </p>}
    <details className="ci-raw-source"><summary>Full source record</summary><pre className="ci-mono">{JSON.stringify({ arguments: item.arguments, result: item.result }, null, 2)}</pre></details>
  </div>;
}

function legacySections(markdown: string) {
  const sections: { title: string; body: string }[] = [];
  let title = "Report", body: string[] = [];
  const finish = () => {
    if (body.join("\n").trim()) sections.push({ title, body: body.join("\n").replace(/\n---\s*$/, "").trim() });
  };
  for (const line of markdown.split("\n")) {
    const heading = line.match(/^##\s+(?:\d+\.\s*)?(.+)$/);
    if (heading) { finish(); title = heading[1]; body = []; }
    else body.push(line);
  }
  finish();
  return sections;
}

export default function ChangeImpactResults({ result, data, onPreview, onDownload }: Props) {
  const report = data?.report;
  const evidence = data?.findings?.evidence || [];
  const warnings = data?.findings?.warnings || [];
  const traceEvidence = data?.dependencies || [];
  const evidencePanel = useRef<HTMLDetailsElement>(null);
  const evidenceKey = useId();
  const [componentFilter, setComponentFilter] = useState("All");
  const repositories = data?.indexed || [];
  const coverageGaps = warnings.filter((warning) => !warning.startsWith("Retrieval is bounded:"));
  const sections = report ? [] : legacySections(result);
  const headline = report?.title || "Change impact report";
  const evidenceId = (id: string) => evidenceKey + "-" + id;
  const sectionId = (name: string) => evidenceKey + "-section-" + name;
  const visibleComponents = report?.affected_components.filter((item) => componentFilter === "All" || item.impact === componentFilter) || [];
  const revealEvidence = (id: string) => {
    if (evidencePanel.current) evidencePanel.current.open = true;
    const item = document.getElementById(evidenceId(id)) as HTMLDetailsElement | null;
    if (item) {
      item.open = true;
      item.scrollIntoView({ behavior: "smooth", block: "center" });
      item.querySelector("summary")?.focus();
    }
  };
  const sourceButton = (ids: string[]) => {
    const available = ids.filter((id) => evidence.some((item) => item.id === id));
    return available.length ? <span className="ci-source-links">{available.map((id) => <button key={id} type="button" className="ci-source-link" onClick={() => revealEvidence(id)} aria-label={"View supporting source " + id}><FileSearch size={13} /> Source {id}</button>)}</span> : null;
  };
  const downloadReport = () => {
    const url = URL.createObjectURL(new Blob([result], { type: "text/markdown;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "change-impact-report.md";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <article className="ci-results ci-polished-report" aria-label="Change impact results">
      <header className="ci-report-hero">
        <div className="ci-report-topline">
          <span className="ci-completed"><CheckCircle2 size={15} /> Analysis complete</span>
          <div className="ci-report-actions">
            {onPreview && <button type="button" className="ci-ghost" onClick={onPreview}><Eye /> Preview</button>}
            <button type="button" className="ci-ghost" onClick={onDownload || downloadReport}><Download /> Export report</button>
          </div>
        </div>
        <h2>{headline}</h2>
        {report?.summary && <p className="ci-report-intro">{report.summary}</p>}
        {data?.change && <details className="ci-request-details"><summary>Original change request</summary><p>{data.change}</p></details>}
        <div className="ci-report-meta">
          {repositories.map((repo) => <span className="ci-repo-chip" key={repo.project} title={repo.path}><FolderOpen size={13} />{basename(repo.path)}</span>)}
          <span><FileSearch size={13} />{evidence.length ? "Based on repository evidence" : "Repository evidence unavailable"}</span>
        </div>
        {report && <div className="ci-risk-overview">
          <span className={"ci-risk-badge " + severityClass(report.overall_risk)}>{report.overall_risk === "Unknown" ? "Risk needs review" : report.overall_risk + " risk"}</span>
          <p>{report.risk_reason || "Review the findings before implementing this change."}</p>
        </div>}
      </header>
      {report ? <>
        <div className="ci-report-metrics" aria-label="Findings at a glance">
          <div><FileCode2 /><strong>{report.affected_components.filter((item) => item.impact === "Direct").length}</strong><span>Proposed direct edits</span></div>
          <div><GitBranch /><strong>{report.affected_components.filter((item) => item.impact !== "Direct").length}</strong><span>Components to check</span></div>
          <div><ShieldAlert /><strong>{report.risks.length}</strong><span>Risks to assess</span></div>
          <div><ListChecks /><strong>{report.tests.length}</strong><span>Proposed test scenarios</span></div>
        </div>
        <div className={"ci-coverage-note ci-coverage-summary " + (coverageGaps.length || !evidence.length ? "partial" : "")}>
          <Info size={17} /><span>{!evidence.length ? "Source evidence is unavailable. Treat the recommendations as provisional." : coverageGaps.length ? "This assessment has coverage gaps. Some affected code may be missing." : "This assessment covers the retrieved code. Additional affected areas may exist."}</span>
          {(!!evidence.length || !!warnings.length) && <button type="button" className="ci-source-link" onClick={() => { if (evidencePanel.current) { evidencePanel.current.open = true; evidencePanel.current.scrollIntoView({ behavior: "smooth", block: "start" }); evidencePanel.current.querySelector("summary")?.focus(); } }}>Review coverage</button>}
        </div>
        <nav className="ci-report-nav" aria-label="Report sections">
          {!!report.behavior_changes?.length && <a href={"#" + sectionId("behavior")}>User impact</a>}
          <a href={"#" + sectionId("code")}>Affected code</a>
          {!!report.contract_impacts?.length && <a href={"#" + sectionId("contracts")}>Data &amp; API</a>}
          <a href={"#" + sectionId("risks")}>Risks</a><a href={"#" + sectionId("steps")}>Next steps</a>
          {!!report.tests.length && <a href={"#" + sectionId("tests")}>Verification plan</a>}
        </nav>
        {!!report.behavior_changes?.length && <section className="ci-insight-card" id={sectionId("behavior")}>
          <div className="ci-insight-heading"><Eye /><h3>What changes for users</h3><span>Current behavior and intended outcome</span></div>
          <div className="ci-behavior-list">{report.behavior_changes.map((item, index) => <div className="ci-behavior-item" key={index}>
            <h4>{item.area}</h4><div className="ci-before-after"><div><strong>Today</strong><p>{item.before}</p></div><div><strong>After this change</strong><p>{item.after}</p></div></div>
            <p className="ci-user-impact"><strong>For users</strong> {item.user_impact}</p>{sourceButton(item.evidence_ids)}
          </div>)}</div>
        </section>}
        <section className="ci-insight-card" id={sectionId("code")}>
          <div className="ci-insight-heading"><FileCode2 /><h3>Where to make the change</h3><span>Why it matters and what to do</span></div>
          {!!report.affected_components.length && <div className="ci-component-filters" role="group" aria-label="Filter affected components">{["All", "Direct", "Indirect", "Review"].map((filter) => <button type="button" key={filter} aria-pressed={componentFilter === filter} onClick={() => setComponentFilter(filter)}>{filter === "All" ? "All components" : impactLabels[filter as keyof typeof impactLabels]} <span>{filter === "All" ? report.affected_components.length : report.affected_components.filter((item) => item.impact === filter).length}</span></button>)}</div>}
          {visibleComponents.length ? <div className="ci-component-list">{visibleComponents.map((component, index) => <div className="ci-component-card" key={index}>
            <div className="ci-component-title"><h4>{component.name}</h4><span className={"ci-impact-tag " + component.impact.toLowerCase()}>{impactLabels[component.impact]}</span></div>
            <p className="ci-component-file">{component.file ? <code>{component.file}</code> : "Source location needs confirmation"}</p>
            <dl><div><dt>Why it is affected</dt><dd>{component.reason}</dd></div><div><dt>Recommended action</dt><dd>{component.action || "Confirm this component's responsibility before planning an edit."}</dd></div></dl>
            {sourceButton(component.evidence_ids)}
          </div>)}</div> : <p className="ci-empty">{report.affected_components.length ? "No components in this category." : "No affected components were confirmed in the retrieved code. Add a specific feature or function name to refine the analysis."}</p>}
        </section>
        {!!report.dependencies.length && <section className="ci-insight-card">
          <div className="ci-insight-heading"><GitBranch /><h3>Dependency impact</h3><span>How the change may spread</span></div>
          <div className="ci-dependency-list">{report.dependencies.map((dependency, index) => <div className="ci-dependency-item" key={index}>
            <div className="ci-dependency-path"><code>{dependency.source}</code><span title={dependency.relationship}><ArrowRight size={17} /><small>{dependency.relationship}</small></span><code>{dependency.target}</code></div>
            <div className="ci-dependency-description"><p>{dependency.impact}</p>{sourceButton(dependency.evidence_ids)}</div>
          </div>)}</div>
        </section>}
        {!!report.contract_impacts?.length && <section className="ci-insight-card" id={sectionId("contracts")}>
          <div className="ci-insight-heading"><GitBranch /><h3>Data, API and access impact</h3><span>Contracts and stored information</span></div>
          <div className="ci-contract-list">{report.contract_impacts.map((item, index) => <div className="ci-contract-item" key={index}>
            <div className="ci-component-title"><h4>{item.area}</h4><span className="ci-contract-status">{item.status}</span></div><p>{item.detail}</p>
            {item.action && <p><strong>Next step:</strong> {item.action}</p>}{sourceButton(item.evidence_ids)}
          </div>)}</div>
        </section>}
        <div className="ci-report-columns">
          <section className="ci-insight-card" id={sectionId("risks")}>
            <div className="ci-insight-heading"><ShieldAlert /><h3>Key risks</h3><span>Potential impact and mitigation</span></div>
            {report.risks.length ? <div className="ci-risk-list">{report.risks.map((risk, index) => <div className="ci-risk-item" key={index}>
              <div className="ci-risk-title"><h4>{risk.title}</h4><span className={"ci-risk-badge " + severityClass(risk.severity)}>{risk.severity}</span></div>
              <p>{risk.detail}</p>
              {risk.mitigation && <div className="ci-mitigation"><strong>Mitigation</strong><span>{risk.mitigation}</span></div>}
              {sourceButton(risk.evidence_ids)}
            </div>)}</div> : <p className="ci-empty">No specific risks were identified in the retrieved evidence. Review the coverage notes before proceeding.</p>}
          </section>
          <section className="ci-insight-card" id={sectionId("steps")}>
            <div className="ci-insight-heading"><ClipboardList /><h3>Recommended steps</h3><span>Suggested implementation order</span></div>
            {report.actions.length ? <ol className="ci-action-list">{report.actions.map((action, index) => <li key={index}><span className="ci-action-number" aria-hidden="true">{index + 1}</span><div><h4>{action.title}</h4>{action.detail && <p>{action.detail}</p>}{action.validation && <div className="ci-done-when"><strong>Done when</strong><p>{action.validation}</p></div>}</div></li>)}</ol> : <p className="ci-empty">Confirm the affected code before planning implementation.</p>}
          </section>
        </div>
        {!!report.tests.length && <section className="ci-insight-card" id={sectionId("tests")}>
          <div className="ci-insight-heading"><ListChecks /><h3>Verification plan</h3><span>Proposed checks · Not run</span></div>
          <ol className="ci-verification-list">{report.tests.map((test, index) => <li key={index}><span className="ci-action-number" aria-hidden="true">{index + 1}</span><div><h4>{test.scenario}</h4>{test.purpose && <p className="ci-test-purpose">{test.purpose}</p>}<p className="ci-expected-result"><strong>Expected result</strong>{test.expected_result}</p></div></li>)}</ol>
        </section>}
        {!!report.open_questions.length && <section className="ci-review-note">
          <Info size={18} /><div><h3>Confirm before implementation</h3><ul>{report.open_questions.map((question, index) => <li key={index}>{question}</li>)}</ul></div>
        </section>}
      </> : <section className="ci-insight-card ci-legacy-report">
        <div className="ci-insight-heading"><ClipboardList /><h3>Report details</h3></div>
        <p className="ci-legacy-note">Expand a section to review the findings. Run a new analysis for the concise summary view.</p>
        {sections.map((section, index) => <details key={index} open={false}>
          <summary>{section.title}<ChevronDown size={16} /></summary>
          <div className="ci-report"><ReactMarkdown remarkPlugins={markdownPlugins}>{section.body}</ReactMarkdown></div>
        </details>)}
      </section>}
      {!report && <div className={"ci-coverage-note " + (coverageGaps.length ? "partial" : "")}>
        <Info size={16} /><span>{!evidence.length ? "Code dependencies could not be verified. Treat this assessment as provisional." : coverageGaps.length ? "Some code or supporting details could not be fully assessed. Review the coverage notes below." : "Based on retrieved code and dependencies. Dynamic calls and unindexed areas may need further review."}</span>
      </div>}
      {(!!evidence.length || !!warnings.length || !!traceEvidence.length) && <details className="ci-evidence-panel" ref={evidencePanel}>
        <summary><span><FileSearch size={17} /><strong>Sources and analysis coverage</strong><small>{evidence.length} source records</small></span><ChevronDown size={17} /></summary>
        <div className="ci-evidence-content">
          {!!warnings.length && <section className="ci-coverage-details"><h4>Coverage notes</h4><ul>{warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></section>}
          {repositories.map((repo) => <p className="ci-repository" key={repo.project}><strong>Repository:</strong> {repo.path}</p>)}
          {evidence.map((item) => <details className="ci-evidence-item" key={item.id} id={evidenceId(item.id)}>
            <summary><span>{TOOL_LABELS[item.tool] || "Supporting evidence"}</span><small>{item.id}</small></summary>
            <EvidenceContent item={item} />
          </details>)}
          {!evidence.length && traceEvidence.map((item) => <details className="ci-evidence-item" key={item.evidence_id}><summary>Dependency trace: {item.symbol}</summary><pre className="ci-mono">{JSON.stringify(item.trace, null, 2)}</pre></details>)}
        </div>
      </details>}
    </article>
  );
}
