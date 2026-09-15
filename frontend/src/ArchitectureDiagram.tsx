import { useEffect, useRef, useState } from "react";

interface ArchitectureDiagramProps {
  xml: string;
}

/*
 * The diagram is pushed into the embed with postMessage instead of a URL
 * fragment, so large models are never truncated by URL length limits.
 */
const EMBED_URL =
  "https://embed.diagrams.net/?embed=1&proto=json&spin=1&lightbox=1" +
  "&nav=1&layers=1&ui=min&noSaveBtn=1&noExitBtn=1&saveAndExit=0";

const EDITOR_BASE = "https://app.diagrams.net/?splash=0";

type Status = "loading" | "ready" | "unavailable";

export default function ArchitectureDiagram({
  xml,
}: ArchitectureDiagramProps) {
  const frameRef = useRef<HTMLIFrameElement>(null);

  const [status, setStatus] = useState<Status>("loading");
  const [showXml, setShowXml] = useState(false);

  useEffect(() => {
    setStatus("loading");

    const handleMessage = (event: MessageEvent) => {
      const frame = frameRef.current;

      if (!frame || event.source !== frame.contentWindow) {
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
        frame.contentWindow?.postMessage(
          JSON.stringify({
            action: "load",
            autosave: 0,
            xml,
          }),
          "*"
        );
      }

      if (message.event === "load") {
        // Chromeless mode only fits the diagram when asked to.
        frame.contentWindow?.postMessage(
          JSON.stringify({
            action: "resize",
            fit: true,
          }),
          "*"
        );

        setStatus("ready");
      }
    };

    window.addEventListener("message", handleMessage);

    const timeout = window.setTimeout(() => {
      setStatus((current) =>
        current === "loading" ? "unavailable" : current
      );
    }, 12000);

    return () => {
      window.removeEventListener("message", handleMessage);
      window.clearTimeout(timeout);
    };
  }, [xml]);

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
            Generated with the Architecture Design Agent and rendered with draw.io.
            Download the <code>.drawio</code> file to edit it in
            diagrams.net, VS Code or Confluence.
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
              </>
            )}
          </div>
        )}

        <iframe
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
