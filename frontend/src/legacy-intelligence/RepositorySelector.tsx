import { useState } from "react";
import { CodeXml, FolderOpen, GitBranch, Layers3, Link2, LoaderCircle, Plus, Search, Trash2 } from "lucide-react";
import { legacyApi } from "./api";
import { Card } from "./shared";
import type { RepositorySource } from "./types";

type SourceMode = "git" | "local" | "multiple";
type Row = { id: number; type: "git" | "local"; value: string };

export default function RepositorySelector({ busy, onAnalyze }: { busy: boolean; onAnalyze: (repositories: RepositorySource[]) => Promise<void> }) {
  const [mode, setMode] = useState<SourceMode>("local");
  const [gitUrl, setGitUrl] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [rows, setRows] = useState<Row[]>([{ id: 0, type: "local", value: "" }, { id: 1, type: "git", value: "" }]);
  const [nextId, setNextId] = useState(2);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState("");

  const pickFolder = async () => {
    setError(""); setPicking(true);
    try { const result = await legacyApi.pickFolder(); if (result.path) setLocalPath(result.path); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not open folder picker. Paste the path below."); }
    finally { setPicking(false); }
  };
  const analyze = async () => {
    setError("");
    const sources = mode === "multiple" ? rows : [{ type: mode, value: mode === "git" ? gitUrl : localPath }];
    if (!sources.length || sources.some((row) => !row.value.trim())) { setError("Provide a path or URL for every repository, or remove empty rows."); return; }
    if (sources.some((row) => row.type === "git" && !/^https:\/\//i.test(row.value.trim()))) { setError("Use an HTTPS repository URL."); return; }
    const repositories: RepositorySource[] = sources.map((row) => row.type === "git" ? { type: "git", url: row.value.trim() } : { type: "local", path: row.value.trim() });
    await onAnalyze(repositories);
  };

  return <Card
    icon={<CodeXml size={22} />}
    title="Analyze a Codebase"
    subtitle="Connect to a repository or local codebase to analyze its architecture, dependencies and business logic."
    className="li-analyze-card">

    <div className="li-source-tabs" role="group" aria-label="Repository source">

      {([{ id: "local", label: "Local Folder", icon: <FolderOpen size={16} /> }, { id: "git", label: "Git Repository", icon: <GitBranch size={16} /> }, { id: "multiple", label: "Multiple Repositories", icon: <Layers3 size={16} /> }] as const).map((tab) => <button
        type="button"
        key={tab.id}
        disabled={busy || picking}
        aria-pressed={mode === tab.id}
        className={mode === tab.id ? "active" : ""}
        onClick={() => { setMode(tab.id); setError(""); }}>
        {tab.icon}
        {tab.label}
      </button>)}

    </div>

    {mode !== "multiple" && <label className="li-field-label" htmlFor="legacy-repository-source">{mode === "git" ? "Repository URL" : "Repository folder path"}</label>}
    {mode === "multiple" ? <div className="li-repository-rows">
      {rows.map((row, index) => <div className="li-repository-row" key={row.id}>
        <span className="li-row-number">{index + 1}</span>
        <select
          aria-label={`Repository ${index + 1} source`}
          disabled={busy}
          value={row.type}
          onChange={(event) => setRows(rows.map((item) => item.id === row.id ? { ...item, type: event.target.value as Row["type"] } : item))}>
          <option value="local">Local folder</option>
          <option value="git">Git URL</option>
        </select>
        <input
          aria-label={`Repository ${index + 1} path or URL`}
          disabled={busy}
          value={row.value}
          placeholder={row.type === "git" ? "https://github.com/org/service.git" : "C:\\projects\\service"}
          onChange={(event) => setRows(rows.map((item) => item.id === row.id ? { ...item, value: event.target.value } : item))} />
        <button
          type="button"
          className="li-icon-button"
          disabled={busy || rows.length === 1}
          aria-label={`Remove repository ${index + 1}`}
          onClick={() => setRows(rows.filter((item) => item.id !== row.id))}>
          <Trash2 size={16} />
        </button>
      </div>)}
      <button
        type="button"
        className="li-link"
        disabled={busy || rows.length >= 5}
        onClick={() => { setRows([...rows, { id: nextId, type: "local", value: "" }]); setNextId(nextId + 1); }}>
        <Plus size={14} /> Add repository
      </button>
    </div> : <div className="li-source-input">
      <span>
        {mode === "local" ? <FolderOpen size={16} /> : <Link2 size={16} />}
        <input
          id="legacy-repository-source"
          aria-label={mode === "git" ? "Repository URL" : "Local repository folder"}
          disabled={busy || picking}
          value={mode === "git" ? gitUrl : localPath}
          onChange={(event) => mode === "git" ? setGitUrl(event.target.value) : setLocalPath(event.target.value)}
          placeholder={mode === "git" ? "https://github.com/your-org/legacy-system.git" : "C:\\projects\\legacy-system"}
          onKeyDown={(event) => { if (event.key === "Enter" && !busy && !picking) void analyze(); }} />
      </span>
      {mode === "local" && <button type="button" className="li-secondary" disabled={busy || picking} onClick={pickFolder}>
        <FolderOpen size={15} />
        {picking ? "Opening…" : "Browse"}
      </button>}
    </div>}

    <div className="li-source-footer">
      <p className="li-muted">{mode === "git" ? "Enter an HTTPS URL for the repository to analyze." : "Local paths must be accessible on the machine running the backend."}</p>
      <button type="button" className="li-primary" disabled={busy || picking} onClick={analyze}>
        {busy ? <LoaderCircle className="li-spin" size={16} /> : <Search size={16} />}Analyze Codebase
      </button>
    </div>

    {error && <p className="li-error" role="alert">{error}</p>}

  </Card>;
}
