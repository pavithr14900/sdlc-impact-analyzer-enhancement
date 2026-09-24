import { useEffect, useState } from "react";
import { legacyApi } from "./api";
import type { DocumentType, GeneratedDocument } from "./types";

/** Read the same saved document used by Documentation; author only when absent. */
export function useAnalysisDocument(analysisId: string, type: DocumentType) {
  const [document, setDocument] = useState<GeneratedDocument | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setDocument(null); setBusy(true); setError(false);
    const load = async () => {
      try {
        const saved = await legacyApi.savedDocumentation(analysisId, controller.signal);
        if (controller.signal.aborted) return;
        let result = saved.documents.find(item => item.type === type);
        if (!result) {
          const generated = await legacyApi.documentation(analysisId, [type], controller.signal);
          result = generated.documents.find(item => item.type === type);
        }
        if (!result) throw new Error("The requested explanation was not returned.");
        if (!controller.signal.aborted) setDocument(result);
      } catch {
        if (!controller.signal.aborted) setError(true);
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    };
    void load();
    return () => controller.abort();
  }, [analysisId, type, attempt]);
  return { document, busy, error, retry: () => setAttempt(value => value + 1) };
}
