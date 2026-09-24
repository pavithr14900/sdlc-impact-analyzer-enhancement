import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { LoaderCircle, MessageCircle, Send } from "lucide-react";
import { legacyApi } from "./api";
import { Card, EvidencePanel } from "./shared";
import type { Evidence } from "./types";

const SUGGESTIONS = ["What services and modules exist?", "Which services depend on each other?", "What APIs and database objects were found?", "Explain the main application workflow.", "What scheduled jobs exist?", "Which external systems are integrated?"];
type Message = { question: string; answer: string; evidence: Evidence[] };

export default function LegacyChat({ analysisId, ready, focus = false }: { analysisId?: string; ready: boolean; focus?: boolean }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    abort.current?.abort();
    setMessages([]); setQuestion(""); setError(""); setBusy(false);
  }, [analysisId]);
  useEffect(() => { if (focus && ready) input.current?.focus(); }, [focus, ready]);

  const ask = async (suggestion?: string) => {
    const query = (suggestion || question).trim();
    if (!analysisId || !query || busy || !ready) return;
    setQuestion(query); setBusy(true); setError("");
    const controller = new AbortController(); abort.current = controller;
    try {
      const result = await legacyApi.chat(analysisId, query, controller.signal);
      if (!controller.signal.aborted) { setMessages((current) => [...current, { question: query, answer: result.answer, evidence: result.evidence || [] }]); setQuestion(""); }
    } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Unable to answer the question."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  };

  return <Card
    icon={<MessageCircle size={21} />}
    title="Ask the Legacy System"
    subtitle="Get evidence-backed answers about your codebase."
    className="li-chat-card">

    <div className="li-suggestions">
      {SUGGESTIONS.slice(0, focus ? 6 : 4).map((suggestion) => <button type="button" disabled={!ready || busy} key={suggestion} onClick={() => void ask(suggestion)}>
        {suggestion}
      </button>)}
    </div>

    {messages.length > 0 && <div className="li-chat-messages" aria-live="polite">
      {messages.map((message, index) => <article className="li-chat-message" key={index}>
        <strong>{message.question}</strong>
        <div className="li-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.answer}</ReactMarkdown></div>
        <EvidencePanel evidence={message.evidence} />
        {!message.evidence.length && <small className="li-muted">This response has no source references. Treat it as an analysis limitation, not a verified code fact.</small>}
      </article>)}
    </div>}

    <form className="li-chat-input" onSubmit={(event) => { event.preventDefault(); void ask(); }}>
      <MessageCircle size={16} />
      <input
        ref={input}
        aria-label="Ask a question about your codebase"
        disabled={!ready || busy}
        value={question}
        maxLength={4000}
        onChange={(event) => setQuestion(event.target.value)}
        placeholder={ready ? "Ask a question about your codebase…" : "Complete an analysis to ask questions…"} />
      <button type="submit" className="li-primary li-send" aria-label="Send question" disabled={!ready || busy || !question.trim()}>
        {busy ? <LoaderCircle className="li-spin" size={16} /> : <Send size={16} />}
      </button>
    </form>

    {busy && <p className="li-muted" role="status">Finding supporting code evidence…</p>}
    {error && <p className="li-error" role="alert">{error}</p>}

  </Card>;
}
