import type { ConfluenceStatus, PublishResult, Analysis, AnalysisSummary, DocumentType, Evidence, GeneratedDocument, RepositorySource } from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api").replace(/\/$/, "");

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  let data: T & { success?: boolean; error?: string };
  try {
    data = await response.json();
  } catch {
    throw new Error(`The server returned an unreadable response (${response.status}). Check that the backend is running.`);
  }
  if (!response.ok || data.success === false) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}
const post = (body: unknown, signal?: AbortSignal): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal,
});
export const legacyApi = {
  recent: (signal?: AbortSignal) => request<{ analyses: AnalysisSummary[] }>("/legacy-intelligence/recent", { signal }),
  get: (id: string, signal?: AbortSignal) => request<{ analysis: Analysis }>(`/legacy-intelligence/${encodeURIComponent(id)}`, { signal }),
  delete: (id: string) => request<{ analysisId: string }>(`/legacy-intelligence/${encodeURIComponent(id)}`, { method: "DELETE" }),
  analyze: (repositories: RepositorySource[]) => request<{ analysis: Analysis }>("/legacy-intelligence/analyze", post({ repositories })),
  pickFolder: () => request<{ path?: string }>("/pick-folder", post({})),
  chat: (analysisId: string, question: string, signal?: AbortSignal) => request<{ answer: string; evidence: Evidence[] }>("/legacy-intelligence/chat", post({ analysisId, question }, signal)),
  documentation: (analysisId: string, types: DocumentType[], signal?: AbortSignal) => request<{ documents: GeneratedDocument[] }>(`/legacy-intelligence/${encodeURIComponent(analysisId)}/documentation`, post({ types }, signal)),
  savedDocumentation: (analysisId: string, signal?: AbortSignal) => request<{ documents: GeneratedDocument[] }>(`/legacy-intelligence/${encodeURIComponent(analysisId)}/documentation`, { signal }),
  confluenceStatus: () => request<ConfluenceStatus>("/legacy-intelligence/confluence/status"),
  publishDocumentation: (analysisId: string, documents: { type: DocumentType; revision: string }[]) => request<PublishResult>(`/legacy-intelligence/${encodeURIComponent(analysisId)}/confluence/publish`, post({ documents })),
  documentationPdf: (analysisId: string, type: DocumentType | "all" = "all", types?: DocumentType[]) => fetch(`${API_BASE}/legacy-intelligence/${encodeURIComponent(analysisId)}/documentation/pdf?type=${encodeURIComponent(type)}${types?.length ? `&types=${encodeURIComponent(types.join(","))}` : ""}`),
};
