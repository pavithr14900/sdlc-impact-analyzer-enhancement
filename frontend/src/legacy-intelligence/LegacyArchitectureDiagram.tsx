import { lazy, Suspense } from "react";
import type { Architecture } from "./types";

const ArchitectureExplorer = lazy(() => import("./ArchitectureExplorer"));

export default function LegacyArchitectureDiagram({ graph, title }: { graph?: Architecture; title?: string }) {
  return <Suspense fallback={<p role="status" className="li-loading">Loading architecture explorer…</p>}><ArchitectureExplorer graph={graph} title={title} /></Suspense>;
}
