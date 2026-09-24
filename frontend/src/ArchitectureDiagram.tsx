import { useEffect, useRef, useState } from "react";

interface ArchitectureDiagramProps {
  xml: string;
  description?: string;
}

/*
 * The diagram is pushed into the embed with postMessage instead of a URL
 * fragment, so large models are never truncated by URL length limits.
 *
 * Use the environment variables `VITE_DRAWIO_EMBED_URL` and
 * `VITE_DRAWIO_EDITOR_URL` to force the draw.io host (for example,
 * drawio.io). Defaults target diagrams.net which is the same editor
 * under the diagrams.net brand.
 */
const EMBED_URL =
  import.meta.env.VITE_DRAWIO_EMBED_URL ||
  "https://embed.diagrams.net/?embed=1&proto=json&spin=1&lightbox=1&nav=1&layers=1&ui=min&noSaveBtn=1&noExitBtn=1&saveAndExit=0";

const EDITOR_BASE = import.meta.env.VITE_DRAWIO_EDITOR_URL || "https://app.diagrams.net/?splash=0";

type Status = "loading" | "ready" | "unavailable";

export default function ArchitectureDiagram({
  xml,
  description = "Generated with the Architecture Design Agent and rendered with draw.io. Download the .drawio file to edit it in diagrams.net, VS Code or Confluence.",
}: ArchitectureDiagramProps) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const initialized = useRef(false);
  const [retry, setRetry] = useState(0);

  const [status, setStatus] = useState<Status>("loading");
  const [showXml, setShowXml] = useState(false);

  useEffect(() => {
    setStatus("loading");
    const origin = new URL(EMBED_URL).origin;
    const load = () => frameRef.current?.contentWindow?.postMessage(
      JSON.stringify({ action: "load", autosave: 0, xml, fit: true }), origin
    );
    if (initialized.current) load();

    const handleMessage = (event: MessageEvent) => {
      const frame = frameRef.current;

      if (!frame || event.source !== frame.contentWindow || event.origin !== origin) {
        return;
      }

      let message: { event?: string };

      if (typeof event.data === "string") {
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }
      } else if (event.data && typeof event.data === "object") {
        message = event.data as { event?: string };
      } else {
        return;
      }

      if (message.event === "init") {
        initialized.current = true;
        load();
      }

      if (message.event === "load") {
        setStatus("ready");
      }
    };

    window.addEventListener("message", handleMessage);

    const timeout = window.setTimeout(() => {
      setStatus((current) =>
        current === "loading" ? "unavailable" : current
      );
    }, 30000);

    return () => {
      window.removeEventListener("message", handleMessage);
      window.clearTimeout(timeout);
    };
  }, [xml, retry]);

  const downloadDiagram = () => {
    const blob = new Blob([xml], {
      type: "application/xml",
    });

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = "architecture.drawio";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  };

  const openInEditor = () => {
    window.open(
      `${EDITOR_BASE}#R${encodeURIComponent(xml)}`,
      "_blank",
      "noopener,noreferrer"
    );
  };

  if (!xml.trim()) {
    return null;
  }

  return (
    <div className="architecture-diagram">
      <div className="architecture-diagram-header">
        <div>
          <div className="output-eyebrow">
            SOLUTION ARCHITECTURE
          </div>

          <h3>Architecture Diagram</h3>

          <p>
            {description}
          </p>
        </div>

        <div className="architecture-diagram-actions">
          <button
            className="section-action"
            onClick={downloadDiagram}
          >
            ⭳ Download .drawio
          </button>

          <button
            className="section-action"
            onClick={openInEditor}
          >
            ↗ Edit in draw.io
          </button>

          <button
            className="section-action"
            onClick={() => setShowXml((value) => !value)}
          >
            {showXml ? "Hide XML" : "View XML"}
          </button>
        </div>
      </div>

      <div className="architecture-diagram-canvas">
        {status !== "ready" && (
          <div className="architecture-diagram-overlay">
            {status === "loading" ? (
              <>
                <span className="spinner" />
                Rendering diagram...
              </>
            ) : (
              <>
                <strong>
                  The draw.io renderer could not be reached.
                </strong>

                <span>
                  Download the .drawio file and open it locally
                  instead.
                </span>
                <button className="section-action" onClick={() => { initialized.current = false; setRetry(value => value + 1); }}>Retry renderer</button>
              </>
            )}
          </div>
        )}

        <iframe
          key={retry}
          ref={frameRef}
          title="Architecture diagram"
          src={EMBED_URL}
          allowFullScreen
        />
      </div>

      {showXml && (
        <div className="architecture-diagram-xml">
          <div className="code-header">
            <span>DRAWIO XML</span>

            <button
              className="section-action"
              onClick={() =>
                navigator.clipboard.writeText(xml)
              }
            >
              Copy
            </button>
          </div>

          <pre>
            <code>{xml}</code>
          </pre>
        </div>
      )}
    </div>
  );
}
