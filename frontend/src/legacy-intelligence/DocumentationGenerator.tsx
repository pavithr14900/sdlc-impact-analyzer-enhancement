import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Boxes,
  Braces,
  ChartNoAxesColumnIncreasing,
  Clock3,
  ChevronDown,
  Database,
  Download,
  FileText,
  GitBranch,
  LoaderCircle,
  Network,
  Share2,
  ShieldAlert,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import DocumentProse from "./DocumentProse";
import { legacyApi } from "./api";
import ConfluencePublisher from "./ConfluencePublisher";
import { Card, EvidencePanel } from "./shared";
import { downloadPdfResponse } from "./download";
import { DOCUMENT_TYPES, type DocumentType, type GeneratedDocument } from "./types";

const DOCUMENT_ICONS: Record<DocumentType, LucideIcon> = {
  application_overview: ChartNoAxesColumnIncreasing,
  system_architecture: Network,
  component_documentation: Boxes,
  api_documentation: Braces,
  database_documentation: Database,
  service_dependencies: GitBranch,
  external_integrations: Share2,
  scheduled_jobs: Clock3,
  business_rules: BookOpen,
  application_flows: Workflow,
  security_overview: ShieldAlert,
  technical_debt: AlertTriangle,
};

export default function DocumentationGenerator({ analysisId }: { analysisId: string }) {
  const [selected, setSelected] = useState<DocumentType[]>(["application_overview", "system_architecture", "api_documentation", "database_documentation", "service_dependencies", "business_rules"]);
  const [documents, setDocuments] = useState<GeneratedDocument[]>([]);
  const [expanded, setExpanded] = useState<DocumentType[]>([]);
  const [publishing, setPublishing] = useState(false);
  const [loadingSaved, setLoadingSaved] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState("");
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    setLoadingSaved(true);
    legacyApi.savedDocumentation(analysisId, controller.signal).then(result => {
      if (!controller.signal.aborted) { setDocuments(result.documents); setExpanded(result.documents.length ? [result.documents[0].type] : []); }
    }).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Could not load saved documents."); })
      .finally(() => { if (!controller.signal.aborted) setLoadingSaved(false); });
    return () => controller.abort();
  }, [analysisId]);

  const generate = async () => {
    if (!selected.length || busy || publishing || loadingSaved) return;
    setBusy(true); setError("");
    const controller = new AbortController(); abort.current = controller;
    try {
      const result = await legacyApi.documentation(analysisId, selected, controller.signal);
      if (!controller.signal.aborted) {
        setDocuments(result.documents);
        setExpanded(result.documents.length ? [result.documents[0].type] : []);
      }
    } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Documentation generation failed."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  };

  const downloadPdf = async (type: DocumentType | "all", name: string) => {
    if (downloading) return;
    setDownloading(type); setDownloadError("");
    try {
      const response = await legacyApi.documentationPdf(analysisId, type, type === "all" ? documents.map(doc => doc.type) : undefined);
      await downloadPdfResponse(response, name);
    } catch (err) { setDownloadError(err instanceof Error ? err.message : "Failed to download the PDF."); }
    finally { setDownloading(null); }
  };

  return <div className="li-detail-stack li-documentation">

    <Card
      icon={<FileText size={22} />}
      title="Generate Documentation"
      subtitle="Create detailed engineering documents with the selected AI model, grounded in your saved source analysis.">

      <div className="li-document-selection-bar">
        <span aria-live="polite"><strong>{selected.length}</strong> of {DOCUMENT_TYPES.length} document types selected</span>
        <div className="li-document-actions">
          <button type="button" className="li-secondary" disabled={busy || publishing || loadingSaved || selected.length === DOCUMENT_TYPES.length} onClick={() => setSelected(DOCUMENT_TYPES.map(([type]) => type))}>Select All</button>
          <button type="button" className="li-secondary" disabled={busy || publishing || loadingSaved || !selected.length} onClick={() => setSelected([])}>Clear All</button>
        </div>
      </div>
      <div className="li-document-options">

        {DOCUMENT_TYPES.map(([type, label]) => {
          const Icon = DOCUMENT_ICONS[type];
          return <label key={type} className={`li-document-option${selected.includes(type) ? " is-selected" : ""}`}>
            <input
              type="checkbox"
              checked={selected.includes(type)}
              disabled={busy || publishing || loadingSaved}
              onChange={(event) => setSelected(event.target.checked ? [...selected, type] : selected.filter((item) => item !== type))} />
            <Icon size={15} />
            <span>{label}</span>
          </label>;
        })}

      </div>

      <div className="li-document-footer">
        <span className="li-muted">{selected.length ? "Each document includes available analysis findings and source references." : "Select at least one document type to begin."}</span>
        <button type="button" className="li-primary" disabled={busy || publishing || loadingSaved || !selected.length} onClick={generate}>
          {busy ? <LoaderCircle size={16} className="li-spin" /> : <FileText size={16} />}
          {busy ? "Generating…" : "Generate Documentation"}
        </button>
      </div>

      {(busy || loadingSaved) && <p role="status" className="li-document-notice">{busy ? "Writing and checking each document against the available source evidence. Large selections can take several minutes." : "Loading saved documentation?"}</p>}
      {error && <p role="alert" className="li-error">{error}</p>}

    </Card>

    {documents.length > 0 && <div className="li-document-download">
      <div><h3>Generated documentation</h3><p>{documents.length} documents ready to review. Expand a section to read its contents.</p></div>
      <div className="li-document-actions">
        <button type="button" className="li-secondary" disabled={expanded.length === documents.length} onClick={() => setExpanded(documents.map(document => document.type))}>Expand All</button>
        <button type="button" className="li-secondary" disabled={!expanded.length} onClick={() => setExpanded([])}>Collapse All</button>
      <button
        type="button"
        className="li-secondary"
        disabled={downloading !== null}
        onClick={() => void downloadPdf("all", `legacy-intelligence-${analysisId}-documentation`)}>
        {downloading === "all" ? <LoaderCircle size={15} className="li-spin" /> : <Download size={15} />}
        Download All (PDF)
      </button>
      </div>
    </div>}

    {downloadError && <p role="alert" className="li-error">{downloadError}</p>}

    {documents.map((document, index) => {
      const Icon = DOCUMENT_ICONS[document.type];
      const open = expanded.includes(document.type);
      const headingId = `document-heading-${document.type}`;
      const panelId = `document-content-${document.type}`;
      return <section key={document.type} className={`li-document-card${open ? " is-open" : ""}`}>
        <header className="li-document-card-header">
          <h3>
            <button type="button" id={headingId} className="li-document-toggle" aria-expanded={open} aria-controls={panelId}
              onClick={() => setExpanded(current => open ? current.filter(type => type !== document.type) : [...current, document.type])}>
              <span className="li-document-icon"><Icon size={21} /></span>
              <span className="li-document-heading"><small>DOCUMENT {String(index + 1).padStart(2, "0")}</small><span>{document.title}</span></span>
              <ChevronDown size={18} className="li-document-chevron" />
            </button>
          </h3>
          <button type="button" className="li-secondary li-document-pdf" disabled={downloading !== null}
            aria-label={`Download ${document.title} PDF`}
            onClick={() => void downloadPdf(document.type, `${document.type}-${analysisId}`)}>
            {downloading === document.type ? <LoaderCircle size={15} className="li-spin" /> : <Download size={15} />}
            Download PDF
          </button>
        </header>
        <div id={panelId} role="region" aria-labelledby={headingId} hidden={!open} className="li-document-body">
          <div className="li-document-cover"><span className="li-document-eyebrow">BUILDPILOT / ENGINEERING REFERENCE</span><h4>{document.title}</h4>
            <div className="li-document-meta"><span>{document.generationMode === "ai-authored" ? "AI-authored review draft" : "Source analysis summary"}</span>{document.readingMinutes && <span>{document.readingMinutes} min read</span>}{document.generatedAt && <span>{new Date(document.generatedAt).toLocaleDateString()}</span>}</div>
          </div>
          {document.warning && <p className="li-document-notice">{document.warning}</p>}
          <DocumentProse content={document.content} />
          <EvidencePanel evidence={document.evidence} />
        </div>
      </section>;
    })}

    {documents.length > 0 && <ConfluencePublisher analysisId={analysisId} documents={documents} disabled={busy || loadingSaved} onPublishingChange={setPublishing} />}
  </div>;
}

