import { useCallback, useEffect, useRef, useState } from "react";
import { legacyApi } from "./api";
import { isRunning, type Analysis, type AnalysisSummary, type DetailView, type RepositorySource } from "./types";

const VIEWS = new Set<DetailView>(["overview", "application-overview", "architecture", "documentation", "business-rules", "flows", "chat", "recent"]);
function readRoute(): { analysisId?: string; view: DetailView } {
  const parts = window.location.hash.replace(/^#\/?/, "").split("/");
  if (parts[0] !== "legacy-intelligence") return { view: "overview" };
  if (parts[1] === "recent") return { view: "recent" };
  let analysisId: string | undefined;
  try { analysisId = parts[1] ? decodeURIComponent(parts[1]) : undefined; } catch { /* Invalid fragments render the overview. */ }
  const candidate = parts[2] as DetailView;
  return { analysisId, view: VIEWS.has(candidate) ? candidate : "overview" };
}

export function useLegacyAnalysis() {
  const [route, setRoute] = useState(readRoute);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [recent, setRecent] = useState<AnalysisSummary[]>([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [recentError, setRecentError] = useState("");
  const [deletingIds, setDeletingIds] = useState<string[]>([]);
  const [deleteError, setDeleteError] = useState("");
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const recentAbort = useRef<AbortController | null>(null);
  const active = useRef(true);

  const refreshRecent = useCallback(async () => {
    recentAbort.current?.abort();
    const controller = new AbortController(); recentAbort.current = controller;
    setRecentLoading(true); setRecentError("");
    try { const result = await legacyApi.recent(controller.signal); if (!controller.signal.aborted) setRecent(result.analyses); }
    catch (err) { if (!controller.signal.aborted) setRecentError(err instanceof Error ? err.message : "Could not load recent analyses."); }
    finally { if (!controller.signal.aborted) setRecentLoading(false); }
  }, []);

  useEffect(() => {
    active.current = true;
    const changed = () => setRoute(readRoute());
    window.addEventListener("hashchange", changed);
    void refreshRecent();
    return () => { active.current = false; window.removeEventListener("hashchange", changed); recentAbort.current?.abort(); };
  }, [refreshRecent]);

  useEffect(() => {
    if (!route.analysisId) { setAnalysis(null); setLoading(false); setError(""); return; }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    const id = route.analysisId;
    setLoading(true); setError("");
    setAnalysis((current) => current?.analysisId === id ? current : null);
    const poll = async () => {
      try {
        const result = await legacyApi.get(id, controller.signal);
        if (controller.signal.aborted) return;
        setAnalysis(result.analysis); setLoading(false); setError(""); failures = 0;
        if (isRunning(result.analysis.status)) timer = setTimeout(poll, 1600);
        else void refreshRecent();
      } catch (err) {
        if (controller.signal.aborted) return;
        failures += 1;
        if (failures < 3) timer = setTimeout(poll, 2000);
        else { setError(err instanceof Error ? err.message : "Unable to load analysis."); setLoading(false); }
      }
    };
    void poll();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [route.analysisId, reload, refreshRecent]);

  const navigate = (view: DetailView, id = route.analysisId) => {
    const next = view === "recent" ? "#/legacy-intelligence/recent" : id ? `#/legacy-intelligence/${encodeURIComponent(id)}${view === "overview" ? "" : `/${view}`}` : "#/legacy-intelligence";
    window.location.hash = next;
    setRoute(readRoute());
  };

  const startAnalysis = async (repositories: RepositorySource[]) => {
    setStarting(true); setError("");
    try {
      const result = await legacyApi.analyze(repositories);
      if (!active.current) return;
      setAnalysis(result.analysis);
      navigate("overview", result.analysis.analysisId);
      void refreshRecent();
    } catch (err) { if (active.current) setError(err instanceof Error ? err.message : "Could not start analysis."); }
    finally { if (active.current) setStarting(false); }
  };

  const deleteAnalysis = async (id: string) => {
    if (deletingIds.includes(id)) return;
    setDeletingIds((ids) => [...ids, id]);
    setDeleteError("");
    try {
      await legacyApi.delete(id);
      if (!active.current) return;
      recentAbort.current?.abort();
      setRecent((items) => items.filter((item) => item.analysisId !== id));
      // Inspect the current route, since navigation may change during the request.
      if (readRoute().analysisId === id) {
        setAnalysis(null);
        navigate("overview", "");
      }
      void refreshRecent();
    } catch (err) {
      if (active.current) setDeleteError(err instanceof Error ? err.message : "Could not delete analysis.");
    } finally {
      if (active.current) setDeletingIds((ids) => ids.filter((item) => item !== id));
    }
  };

  return { route, analysis, recent, recentLoading, recentError, deletingIds, deleteError, deleteAnalysis, loading, starting, error, refreshRecent, navigate, startAnalysis, retry: () => setReload((value) => value + 1) };
}
