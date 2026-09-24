import { useMemo, useState } from "react";
import { Background, Controls, MarkerType, ReactFlow, type Node, type Edge } from "@xyflow/react";
import { Network, Database, Globe, FolderGit2, Server, Braces, Clock, Code2 } from "lucide-react";
import { EmptyState, EvidencePanel } from "./shared";
import type { Architecture, ArchitectureNode, Evidence } from "./types";
import "@xyflow/react/dist/style.css";

const componentStyles: Record<string, { icon: typeof Network; label: string }> = {
  repository: { icon: FolderGit2, label: "Repository" },
  service: { icon: Server, label: "Source component" },
  database: { icon: Database, label: "Database table" },
  external: { icon: Globe, label: "External reference" },
  api: { icon: Braces, label: "API endpoint" },
  job: { icon: Clock, label: "Scheduled job" },
  function: { icon: Code2, label: "Function" },
};

export function layoutGraph(graph: Architecture): { nodes: Node[]; edges: Edge[] } {
  const ids = new Set(graph.nodes.map((node) => node.id));
  const edges = graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target));

  // Try to lay out as: API Gateway (top center) -> services (row) -> databases (under each service)
  const services = graph.nodes.filter((n) => n.type === "service");
  const apis = graph.nodes.filter((n) => n.type === "api" || /gateway/i.test(n.name || ""));
  const databases = graph.nodes.filter((n) => n.type === "database");

  if (services.length >= 1 && apis.length >= 1) {
    const apiNode = apis[0];
    const serviceCount = services.length;
    const spacingX = 320;
    const startX = -((serviceCount - 1) / 2) * spacingX;
    const apiY = 0;
    const serviceY = 150;
    const dbY = 320;

    const nodes: Node[] = [];

    // API gateway node centered
    const apiComponent = componentStyles[apiNode.type] || { icon: Network, label: apiNode.type };
    const ApiIcon = apiComponent.icon;
    nodes.push({
      id: apiNode.id,
      position: { x: 0, y: apiY },
      data: {
        label: (
          <div className="li-graph-label">
            <ApiIcon size={22} />
            <span className="li-graph-kind">{apiComponent.label}</span>
            <strong title={apiNode.name}>{apiNode.name}</strong>
            <small>{apiNode.repository || "Source analysis"}</small>
          </div>
        ),
      },
      className: `li-graph-node li-node-${apiNode.type.replace(/[^a-z-]/gi, "").toLowerCase()}`,
      style: { width: 260, height: 120 },
    });

    // Place services in a horizontal row
    services.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
    services.forEach((svc, i) => {
      const x = startX + i * spacingX;
      const comp = componentStyles[svc.type] || { icon: Network, label: svc.type };
      const Icon = comp.icon;
      nodes.push({
        id: svc.id,
        position: { x, y: serviceY },
        data: {
          label: (
            <div className="li-graph-label">
              <Icon size={22} />
              <span className="li-graph-kind">{comp.label}</span>
              <strong title={svc.name}>{svc.name}</strong>
              <small>{svc.repository || "Source analysis"}</small>
            </div>
          ),
        },
        className: `li-graph-node li-node-${svc.type.replace(/[^a-z-]/gi, "").toLowerCase()}`,
        style: { width: 230, height: 130 },
      });

      // Find a database associated with this service (edge from service -> db or db -> service)
      const dbEdge = edges.find((e) => e.source === svc.id && (graph.nodes.find(n => n.id === e.target)?.type === "database"));
      const dbNode = dbEdge ? graph.nodes.find((n) => n.id === dbEdge.target) : undefined;
      // fallback: find a database node that references the service repository
      const fallbackDb = !dbNode && databases.find((d) => d.repository && svc.repository && d.repository === svc.repository);
      const finalDb = dbNode || fallbackDb;
      if (finalDb) {
        const dbComp = componentStyles[finalDb.type] || { icon: Network, label: finalDb.type };
        const DbIcon = dbComp.icon;
        nodes.push({
          id: finalDb.id,
          position: { x, y: dbY },
          data: {
            label: (
              <div className="li-graph-label">
                <DbIcon size={20} />
                <span className="li-graph-kind">{dbComp.label}</span>
                <strong title={finalDb.name}>{finalDb.name}</strong>
                <small>{finalDb.repository || "Source analysis"}</small>
              </div>
            ),
          },
          className: `li-graph-node li-node-${finalDb.type.replace(/[^a-z-]/gi, "").toLowerCase()}`,
          style: { width: 200, height: 110 },
        });
      }
    });

    // Add other nodes that weren't explicitly placed (external, apis, jobs) around the right/bottom area
    const placed = new Set(nodes.map((n) => n.id));
    let extraX = startX + Math.max(0, services.length - 1) * spacingX + 200;
    let extraY = serviceY;
    for (const node of graph.nodes) {
      if (placed.has(node.id)) continue;
      const comp = componentStyles[node.type] || { icon: Network, label: node.type };
      const Icon = comp.icon;
      nodes.push({
        id: node.id,
        position: { x: extraX, y: extraY },
        data: {
          label: (
            <div className="li-graph-label">
              <Icon size={20} />
              <span className="li-graph-kind">{comp.label}</span>
              <strong title={node.name}>{node.name}</strong>
              <small>{node.repository || "Source analysis"}</small>
            </div>
          ),
        },
        className: `li-graph-node li-node-${node.type.replace(/[^a-z-]/gi, "").toLowerCase()}`,
        style: { width: 200, height: 110 },
      });
      extraY += 140;
      if (extraY > dbY + 200) {
        extraY = serviceY;
        extraX += 220;
      }
    }

    return {
      nodes,
      edges: edges.map((edge, index) => ({
        id: edge.id || `${edge.source}-${edge.target}-${index}`,
        source: edge.source,
        target: edge.target,
        label: edge.relationship || edge.relationshipType,
        data: { evidence: edge.evidence || [] },
        type: "smoothstep",
        markerEnd: { type: MarkerType.ArrowClosed, color: "#a2aec6" },
        style: { stroke: "#94a3b8", strokeWidth: 1.5 },
        labelBgStyle: { fill: "#ffffff", fillOpacity: 0.95 },
        labelBgPadding: [6, 4] as [number, number],
        labelBgBorderRadius: 5,
        labelStyle: { fill: "#71809c", fontSize: 10 },
      })),
    };
  }

  // Fallback: original automatic layout
  const targets = new Set(edges.map((edge) => edge.target));
  const levels = new Map<string, number>();
  const roots = graph.nodes.filter((node) => !targets.has(node.id));
  const queue = (roots.length ? roots : graph.nodes.slice(0, 1)).map((node) => ({ id: node.id, level: 0 }));
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const current = queue[cursor];
    if (levels.has(current.id)) continue;
    levels.set(current.id, current.level);
    for (const edge of edges.filter((item) => item.source === current.id)) {
      if (!levels.has(edge.target)) queue.push({ id: edge.target, level: current.level + 1 });
    }
  }
  const rows = new Map<number, ArchitectureNode[]>();
  for (const node of graph.nodes) {
    const level = levels.get(node.id) ?? 0;
    rows.set(level, [...(rows.get(level) || []), node]);
  }
  let offsetY = 0;
  const nodes = [...rows.entries()].sort(([a], [b]) => a - b).flatMap(([, row]) => {
    const columns = Math.min(row.length, 4);
    const startY = offsetY;
    offsetY += Math.ceil(row.length / columns) * 180 + 70;
    return row.map((node, index) => {
      const component = componentStyles[node.type] || { icon: Network, label: node.type };
      const Icon = component.icon;
      return {
        id: node.id,
        position: { x: (index % columns - (columns - 1) / 2) * 270, y: startY + Math.floor(index / columns) * 180 },
        data: {
          label: <div className="li-graph-label">
            <Icon size={22} />
            <span className="li-graph-kind">{component.label}</span>
            <strong title={node.name}>{node.name}</strong>
            <small>{node.repository || "Source analysis"}</small>
          </div>,
        },
        className: `li-graph-node li-node-${node.type.replace(/[^a-z-]/gi, "").toLowerCase()}`,
        style: { width: 230, height: 130 },
      };
    });
  });
  return {
    nodes,
    edges: edges.map((edge, index) => ({
      id: edge.id || `${edge.source}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      label: edge.relationship || edge.relationshipType,
      data: { evidence: edge.evidence || [] },
      type: "smoothstep",
      markerEnd: { type: MarkerType.ArrowClosed, color: "#a2aec6" },
      style: { stroke: "#94a3b8", strokeWidth: 1.5 },
      labelBgStyle: { fill: "#ffffff", fillOpacity: 0.95 },
      labelBgPadding: [6, 4] as [number, number],
      labelBgBorderRadius: 5,
      labelStyle: { fill: "#71809c", fontSize: 10 },
    })),
  };
}

export default function ArchitectureOverview({ graph, full = false }: { graph?: Architecture; full?: boolean }) {
  const [selection, setSelection] = useState<{ title: string; evidence: Evidence[] } | null>(null);
  const layout = useMemo(() => layoutGraph(graph || { nodes: [], edges: [] }), [graph]);
  if (!graph?.nodes.length) return <EmptyState>Analyze a codebase to discover its architecture. Only relationships supported by source evidence will appear here.</EmptyState>;
  return <div className="li-architecture">
    <div className="li-graph-summary"><span><strong>{graph.nodes.length}</strong> components</span><span><strong>{layout.edges.length}</strong> source relationships</span></div>
    <div className="li-graph-legend" aria-label="Component types">
      {[...new Set(graph.nodes.map(node => node.type))].map(type => {
        const component = componentStyles[type] || { icon: Network, label: type };
        const Icon = component.icon;
        return <span key={type}><Icon size={14} />{component.label}</span>;
      })}
    </div>
    <div className={`li-graph ${full ? "li-graph-full" : ""}`} aria-label="Codebase architecture graph">
      <ReactFlow
        key={`${full}-${graph.nodes.length}-${graph.edges.length}`}
        nodes={layout.nodes}
        edges={layout.edges}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        fitView
        fitViewOptions={{ padding: 0.22 }}
        minZoom={0.08}
        maxZoom={1.5}
        panOnScroll={false}
        zoomOnScroll={full}
        preventScrolling={full}
        onNodeClick={(_, node) => { const source = graph.nodes.find((item) => item.id === node.id); setSelection({ title: source?.name || node.id, evidence: source?.evidence || [] }); }}
        onEdgeClick={(_, edge) => { setSelection({ title: String(edge.label || "Relationship"), evidence: (edge.data?.evidence || []) as Evidence[] }); }}>

        <Background color="#e7eaf3" gap={20} />
        <Controls showInteractive={false} />

      </ReactFlow>
    </div>
    {selection && <div className="li-graph-selection">
      <strong>{selection.title}</strong>
      {selection.evidence.length ? <EvidencePanel evidence={selection.evidence} /> : <p className="li-muted">No additional source reference was supplied for this graph item.</p>}
    </div>}
    {full && <p className="li-muted">Select a component or connection to inspect its source evidence. Scroll to zoom; drag the canvas to pan.</p>}
  </div>;
}
