import { useEffect, useState } from "react";
import { ExternalLink, LoaderCircle, UploadCloud } from "lucide-react";
import { legacyApi } from "./api";
import type { ConfluenceStatus, DocumentType, GeneratedDocument, PublishResult } from "./types";

export default function ConfluencePublisher({ analysisId, documents, disabled, onPublishingChange }: {
  analysisId: string; documents: GeneratedDocument[]; disabled: boolean; onPublishingChange: (busy: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<ConfluenceStatus | null>(null);
  const [selected, setSelected] = useState<DocumentType[]>([]);
  const [checking, setChecking] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PublishResult | null>(null);
  useEffect(() => { setSelected(documents.filter(doc => doc.revision).map(doc => doc.type)); setResult(null); }, [documents]);
  const check = async () => {
    setChecking(true); setError("");
    try { setStatus(await legacyApi.confluenceStatus()); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not load the Confluence connection."); }
    finally { setChecking(false); }
  };
  const publish = async () => {
    if (publishing || !selected.length || !status?.configured) return;
    setPublishing(true); onPublishingChange(true); setError(""); setResult(null);
    try {
      const response = await legacyApi.publishDocumentation(analysisId, documents.filter(doc => selected.includes(doc.type) && doc.revision).map(doc => ({ type: doc.type, revision: doc.revision! })));
      setResult(response);
      setSelected(current => current.filter(type => !response.pages.some(page => page.type === type)));
    } catch (err) { setError(err instanceof Error ? err.message : "Publishing failed."); }
    finally { setPublishing(false); onPublishingChange(false); }
  };
  return <section className="li-confluence-panel">
    <button type="button" className="li-confluence-heading" aria-expanded={open} aria-controls="confluence-publish-options"
      onClick={() => { setOpen(!open); if (!open) void check(); }}>
      <UploadCloud size={21} /><span><strong>Publish to Confluence</strong><small>Share reviewed documents with your team</small></span><span>{open ? "?" : "+"}</span>
    </button>
    {open && <div id="confluence-publish-options" className="li-confluence-body">
      {checking && <p role="status">Loading connection settings?</p>}
      {status && <>
        <dl className="li-confluence-destination"><div><dt>Site</dt><dd>{status.baseUrl || "Not configured"}</dd></div><div><dt>Space</dt><dd>{status.spaceKey || "Not configured"}</dd></div><div><dt>Parent page</dt><dd>{status.parentPageId || "Space root"}</dd></div></dl>
        {!status.configured && <div className="li-document-notice"><strong>Connect Confluence Cloud</strong><p>Set these values in the backend .env file, then restart the backend. The API token stays on the server.</p><code>CONFLUENCE_BASE_URL=https://your-team.atlassian.net<br />CONFLUENCE_EMAIL=your-account-email<br />CONFLUENCE_API_TOKEN=your-api-token<br />CONFLUENCE_SPACE_KEY=your-space-key<br />CONFLUENCE_PARENT_PAGE_ID=optional-parent-page-id</code>{status.configurationError && <p>{status.configurationError}</p>}</div>}
      </>}
      <div className="li-document-actions"><button type="button" className="li-secondary" disabled={checking || publishing} onClick={() => void check()}>Refresh connection settings</button></div>
      <fieldset disabled={publishing || disabled} className="li-confluence-selection"><legend>Documents to publish</legend>
        {documents.map(doc => <label key={doc.type}><input type="checkbox" checked={selected.includes(doc.type)} disabled={!doc.revision}
          onChange={event => setSelected(current => event.target.checked ? [...current, doc.type] : current.filter(type => type !== doc.type))} />{doc.title}</label>)}
      </fieldset>
      <p className="li-muted">Each selected document becomes a published page using the content shown above. Publishing again updates the matching page for this analysis. Review source findings and AI interpretations before sharing.</p>
      <button type="button" className="li-primary" disabled={disabled || publishing || checking || !status?.configured || !selected.length} onClick={() => void publish()}>
        {publishing ? <LoaderCircle size={16} className="li-spin" /> : <UploadCloud size={16} />}{publishing ? "Publishing?" : `Publish ${selected.length} document${selected.length === 1 ? "" : "s"}`}
      </button>
      {error && <p className="li-error" role="alert">{error}</p>}
      {result && <div aria-live="polite"><p>{result.pages.length} published; {result.errors.length} failed.</p>
        {result.pages.map(page => <p key={page.type}><a href={page.url} target="_blank" rel="noreferrer">{page.title} <ExternalLink size={13} /></a> ({page.action})</p>)}
        {result.errors.map(item => <p className="li-error" key={item.type}>{item.title}: {item.error}</p>)}
      </div>}
    </div>}
  </section>;
}
