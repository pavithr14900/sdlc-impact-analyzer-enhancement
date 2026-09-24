import { useState } from "react";
import { BookOpen, LoaderCircle, Workflow } from "lucide-react";
import LegacyArchitectureDiagram from "./LegacyArchitectureDiagram";
import DocumentProse from "./DocumentProse";
import { useAnalysisDocument } from "./useAnalysisDocument";
import { Card, EmptyState, EvidencePanel } from "./shared";
import type { ApplicationFlow, BusinessRule } from "./types";

export function BusinessRules({ rules, analysisId, narrative }: { rules: BusinessRule[]; analysisId: string; narrative?: string }) {
  const { document, busy, error, retry } = useAnalysisDocument(analysisId, "business_rules");

  return <Card
    icon={<BookOpen size={21} />}
    title="Business Rules"
    subtitle="Understand when each rule applies and what the application does. Source evidence is available on demand.">

    {busy && <p role="status" className="li-document-notice"><LoaderCircle size={16} className="li-spin" /> Preparing the business rules explanation. This may take a few minutes.</p>}
    {error && <div role="alert" className="li-document-notice">The business rules explanation could not be loaded. Available analysis findings are shown below. <button type="button" className="li-secondary" onClick={retry}>Retry explanation</button></div>}
    {document ? <div className="li-business-rules-document">
      {document.warning && <p className="li-document-notice">{document.warning}</p>}
      <DocumentProse content={document.content} />
      <EvidencePanel evidence={document.evidence} />
    </div> : narrative ? <div className="li-business-rules-document"><DocumentProse content={narrative} /></div> : null}

    {!rules.length ? (!document && !narrative && !busy && <EmptyState>No evidence-backed business rules were discovered by the current analysis. This does not mean the application has no business rules.</EmptyState>) : <details className="li-rule-catalogue" open={!document && !narrative}>
      <summary>Discovered rule details ({rules.length})</summary>
      <div className="li-rules li-readable-rules">
      {rules.map((rule) => <article key={rule.id} className="li-rule">
        <header>
          <span className="li-rule-id">{rule.id}</span>
          <span className={`li-confidence li-confidence-${rule.confidence.toLowerCase()}`}>{rule.confidence} confidence</span>
        </header>
        <h4>{rule.title}</h4>
        <DocumentProse content={rule.description} />
        <EvidencePanel evidence={rule.evidence} />
      </article>)}
    </div></details>}

  </Card>;
}

export function ApplicationFlows({ flows, analysisId, narrative }: { flows: ApplicationFlow[]; analysisId: string; narrative?: string }) {
  const { document, busy, error, retry } = useAnalysisDocument(analysisId, "application_flows");
  return <div className="li-detail-stack">
    <Card
      icon={<Workflow size={21} />}
      title="Application Flows"
      subtitle="Understand how a process starts, what happens along the way, and how it ends.">
      {busy && <p role="status" className="li-document-notice"><LoaderCircle size={16} className="li-spin" />Preparing a readable explanation of the application flows. This may take a few minutes.</p>}
      {error && <div role="alert" className="li-document-notice">The flow explanation could not be loaded. Available analysis findings are shown below. <button type="button" className="li-secondary" onClick={retry}>Retry explanation</button></div>}
      {document ? <div className="li-business-rules-document">
        {document.warning && <p className="li-document-notice">{document.warning}</p>}
        <DocumentProse content={document.content} />
        <EvidencePanel evidence={document.evidence} />
      </div> : narrative ? <div className="li-business-rules-document"><DocumentProse content={narrative} /></div> : !busy && !flows.length ? <EmptyState>No verified application flows are available in the current analysis.</EmptyState> : null}
    </Card>
    {flows.length > 0 && <p className="li-muted">Explore the supporting source relationships below. Connections show discovered relationships; they do not establish execution order unless the source confirms it.</p>}
    {flows.map((flow, index) => <Card key={flow.id} icon={<Workflow size={19} />} title={flow.title || flow.name || `Application flow ${index + 1}`}>
      {flow.description && <DocumentProse content={flow.description} />}
      <FlowDiagram flow={flow} />
      <EvidencePanel evidence={flow.evidence} />
    </Card>)}
  </div>;
}

function FlowDiagram({ flow }: { flow: ApplicationFlow }) {
  const [open, setOpen] = useState(false);
  return <details className="li-rule-catalogue" onToggle={event => setOpen(event.currentTarget.open)}><summary>Explore flow diagram ({flow.nodes.length} components)</summary>
    {open && <LegacyArchitectureDiagram graph={flow} title={flow.title || flow.name || "Flow relationships"} />}
  </details>;
}
