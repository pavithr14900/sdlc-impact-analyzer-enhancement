import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, FolderOpen, GitBranch, Info } from "lucide-react";
import ChangeImpactResults from "./ChangeImpactResults";
import type { ImpactResult } from "./ChangeImpactResults";
import "./changeImpact.css";

type Props = {
  changeRequest: string;
  setChangeRequest: (value: string) => void;
  onAnalyze?: () => void;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";
const STATUS_LABELS: Record<string, string> = {
  pending: "Waiting to start", preparing: "Preparing repository",
  indexing: "Indexing repository with codebase memory",
  searching: "Finding affected code and tracing dependencies",
  analyzing: "Generating dependencies, risks and suggested tests",
  completed: "Analysis complete", failed: "Analysis failed",
};

export default function ChangeImpactHome({ changeRequest, setChangeRequest }: Props) {
  const [editing, setEditing] = useState(false);
  const [source, setSource] = useState<"local" | "git">("local");
  const [localPath, setLocalPath] = useState("");
  const [gitUrl, setGitUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [loading, setLoading] = useState(false);
  const [picking, setPicking] = useState(false);
  const [jobStatus, setJobStatus] = useState("");
  const [error, setError] = useState("");
  const [jobResult, setJobResult] = useState<ImpactResult | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
    controller.current?.abort();
  }, []);

  const pickFolder = async () => {
    setPicking(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/pick-folder`, { method: "POST" });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || "Folder picker unavailable. Paste the repository path below.");
      if (data.path) setLocalPath(data.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Paste the repository path below.");
    } finally {
      setPicking(false);
    }
  };

  const startAnalysis = async () => {
    setError("");
    if (!changeRequest.trim()) { setError("Please describe the change."); return; }
    if (source === "local" && !localPath.trim()) { setError("Enter a local repository folder path."); return; }
    if (source === "git" && !gitUrl.trim()) { setError("Enter a Git repository URL."); return; }
    if (timer.current) clearTimeout(timer.current);
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const readJson = async (url: string, init?: RequestInit) => {
      const response = await fetch(url, { ...init, signal: abort.signal });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || `Request failed (${response.status})`);
      return data;
    };
    setLoading(true);
    setJobResult(null);
    setJobStatus("pending");
    try {
      const data = await readJson(`${API_BASE}/change-impact/start-simple`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          change: changeRequest.trim(),
          repo: source === "local" ? { local_path: localPath.trim() } : { git_url: gitUrl.trim(), branch: branch.trim() || undefined },
        }),
      });
      const jobId = encodeURIComponent(data.job_id);
      const deadline = Date.now() + 30 * 60 * 1000;
      let failures = 0;
      const poll = async () => {
        if (abort.signal.aborted) return;
        try {
          const status = await readJson(`${API_BASE}/change-impact/status?job_id=${jobId}`);
          setJobStatus(status.job.status);
          if (status.job.status === "failed") {
            setError(status.job.error || "Analysis failed. Check the backend log.");
            setLoading(false);
            return;
          }
          if (status.job.status === "completed") {
            const result = await readJson(`${API_BASE}/change-impact/result?job_id=${jobId}`);
            if (!result.job.result?.document) throw new Error("The completed job has no report.");
            setJobResult(result.job.result);
            setEditing(false);
            setLoading(false);
            return;
          }
          failures = 0;
        } catch (err) {
          if (abort.signal.aborted) return;
          failures += 1;
          if (failures >= 3) {
            setError(`Could not retrieve analysis ${data.job_id}: ${err instanceof Error ? err.message : "connection failed"}`);
            setLoading(false);
            return;
          }
        }
        if (Date.now() > deadline) {
          setError(`Stopped waiting for job ${data.job_id}. It may still be running; check the backend.`);
          setLoading(false);
          return;
        }
        timer.current = setTimeout(poll, 2000);
      };
      timer.current = setTimeout(poll, 1000);
    } catch (err) {
      if (abort.signal.aborted) return;
      setError(err instanceof Error ? err.message : "Failed to start analysis");
      setLoading(false);
      setJobStatus("failed");
    }
  };

  if (jobResult && !editing) {
    return (
      <div className="ci-home">
        <div className="ci-results-toolbar">
          <button type="button" onClick={() => setEditing(true)}><ArrowLeft size={15} /> Edit change</button>
          <span>Review before implementation</span>
        </div>
        <ChangeImpactResults result={jobResult.document} data={jobResult} />
      </div>
    );
  }

  return (
    <div className="ci-home">
      <div className="ci-card describe-card">
        <div className="ci-card-header"><div className="ci-step">1</div><h3>Describe your change</h3></div>
        <label className="ci-field-label" htmlFor="change-request">Change description</label>
        <textarea id="change-request" className="ci-textarea" value={changeRequest} disabled={loading}
          onChange={(event) => setChangeRequest(event.target.value)}
          placeholder="Describe the requested change and expected behaviour, for example: allow discounts when calculating an order total." />
        <p className="ci-help">Include affected features, APIs or function names if known.</p>
      </div>
      <div className="ci-card repos-card">
        <div className="ci-card-header"><div className="ci-step">2</div><div><h3>Repository source</h3><p className="ci-sub">Choose the codebase to analyze.</p></div></div>
        <div className="repo-source-tabs">
          <button type="button" disabled={loading} className={`repo-source ${source === "local" ? "active" : ""}`} onClick={() => setSource("local")}><FolderOpen /> Local folder</button>
          <button type="button" disabled={loading} className={`repo-source ${source === "git" ? "active" : ""}`} onClick={() => setSource("git")}><GitBranch /> Git URL</button>
        </div>
        <div className="repo-add-fields">
          {source === "local" ? (
            <div className="local-picker">
              <input aria-label="Local repository path" placeholder="C:\path\to\repo or /home/user/repo" value={localPath} disabled={loading} onChange={(event) => setLocalPath(event.target.value)} />
              <button type="button" className="browse" onClick={pickFolder} disabled={loading || picking}>{picking ? "Opening..." : "Browse folder"}</button>
            </div>
          ) : <>
            <input aria-label="Repository URL" placeholder="https://github.com/your-org/repository" value={gitUrl} disabled={loading} onChange={(event) => setGitUrl(event.target.value)} />
            <label className="branch-input"><span>Branch (optional)</span><input aria-label="Branch" placeholder="Default branch" value={branch} disabled={loading} onChange={(event) => setBranch(event.target.value)} /></label>
          </>}
        </div>
        {source === "local" && <p className="ci-help">Paste an absolute folder path accessible on the machine running the backend.</p>}
        <div className="ci-card-footer">
          <div className="ci-footer-note"><Info /> Codebase memory indexes the repository and traces code dependencies.</div>
          <div className="ci-card-actions"><button type="button" className="ci-primary" onClick={startAnalysis} disabled={loading || picking}>Analyze impact <ArrowRight /></button></div>
          <p className="ci-footer-caption">Get source evidence, dependency paths, risks and suggested tests.</p>
        </div>
        {loading && <div className="ci-progress" role="status" aria-live="polite">{STATUS_LABELS[jobStatus] || jobStatus}...</div>}
        {error && <div className="ci-error" role="alert">{error}</div>}
      </div>
    </div>
  );
}
