import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Background, BaseEdge, Controls, EdgeLabelRenderer, Handle, MarkerType, MiniMap, Position, ReactFlow, useNodesInitialized, useReactFlow, type Edge, type EdgeProps, type Node, type NodeProps, type ReactFlowInstance } from "@xyflow/react";
import { ArrowDown, ArrowRight, Braces, Clock, Code2, Database, Download, Focus, FolderGit2, Globe, Layers, LoaderCircle, Maximize2, Network, Search, Server, X } from "lucide-react";
import ELK from "elkjs/lib/elk-api";
import elkWorkerUrl from "elkjs/lib/elk-worker.min.js?url";
import { appearance, edgePath, layoutRequest, NODE_HEIGHT, NODE_WIDTH, normalizeArchitecture, readLayout, relationship, type ArchitectureLayout, type Direction, type RoutedEdge } from "./architectureLayout";
import { downloadArchitecture, exportDrawio, exportSvg } from "./architectureExport";
import { EmptyState, EvidencePanel } from "./shared";
import type { Architecture, ArchitectureNode } from "./types";
import "@xyflow/react/dist/style.css";
import "./architectureExplorer.css";

type ComponentNode = Node<{ component: ArchitectureNode; direction: Direction; dimmed: boolean }, "component">;
type ConnectionEdge = Edge<{ route: RoutedEdge; showLabel: boolean }, "connection">;
const icons: Record<string, typeof Network> = { repository: FolderGit2, api: Braces, service: Server, database: Database, external: Globe, job: Clock, function: Code2, client: Globe, gateway: Layers };

function ComponentCard({ data, selected }: NodeProps<ComponentNode>) {
  const { component, direction, dimmed } = data;
  const theme = appearance(component.type), Icon = icons[component.type] || Network;
  return <div className={`ax-node${selected ? " is-selected" : ""}${dimmed ? " is-dimmed" : ""}`} style={{ "--ax-accent": theme.color, "--ax-tint": theme.fill } as CSSProperties}>
    <Handle id="in" type="target" position={direction === "RIGHT" ? Position.Left : Position.Top} isConnectable={false} />
    <div className="ax-node-kind"><span className="ax-node-icon"><Icon size={17} /></span><span>{theme.label}</span></div>
    <strong title={component.name}>{component.name}</strong>
    <span className="ax-node-repo" title={component.repository}>{component.repository || "Source component"}</span>
    <Handle id="out" type="source" position={direction === "RIGHT" ? Position.Right : Position.Bottom} isConnectable={false} />
  </div>;
}

function Connection({ id, data, markerEnd, style }: EdgeProps<ConnectionEdge>) {
  if (!data) return null;
  const { route, showLabel } = data;
  return <>
    <BaseEdge id={id} path={edgePath(route.points)} markerEnd={markerEnd} style={style} interactionWidth={18} />
    {showLabel && route.label && <EdgeLabelRenderer><span className="ax-edge-label" style={{ transform: `translate(-50%, -50%) translate(${route.label.x}px, ${route.label.y}px)` }}>{route.label.text}</span></EdgeLabelRenderer>}
  </>;
}
const nodeTypes = { component: ComponentCard };
const edgeTypes = { connection: Connection };

function FitLayout({ layout }: { layout: ArchitectureLayout }) {
  const initialized = useNodesInitialized();
  const { fitView, getViewport, setViewport, viewportInitialized } = useReactFlow();
  useEffect(() => {
    let active = true;
    if (initialized && viewportInitialized) void fitView({ padding: 0.12, minZoom: 0.8, maxZoom: 1 }).then(() => {
      // Large diagrams start at their top instead of hiding entry points above the canvas.
      const viewport = getViewport();
      if (active && viewport.y < 20) void setViewport({ ...viewport, y: 20 });
    });
    return () => { active = false; };
  }, [initialized, viewportInitialized, layout, fitView, getViewport, setViewport]);
  return null;
}

export default function ArchitectureExplorer({ graph, title = "Architecture explorer" }: { graph?: Architecture; title?: string }) {
  const normalized = useMemo(() => normalizeArchitecture(graph || { nodes: [], edges: [] }), [graph]);
  const [direction, setDirection] = useState<Direction>("DOWN");
  const [repository, setRepository] = useState("");
  const [kind, setKind] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<RoutedEdge | null>(null);
  const [focused, setFocused] = useState(false);
  const [labels, setLabels] = useState(true);
  const [result, setResult] = useState<{ graph: Architecture; direction: Direction; layout: ArchitectureLayout } | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const flow = useRef<ReactFlowInstance<ComponentNode, ConnectionEdge> | null>(null);
  const connected = useMemo(() => {
    const ids = new Set(selected ? [selected] : []);
    normalized.edges.forEach(edge => { if (edge.source === selected || edge.target === selected) { ids.add(edge.source); ids.add(edge.target); } });
    return ids;
  }, [normalized, selected]);
  const focusedNeighbors = focused && selected ? connected : null;
  const visible = useMemo(() => {
    const nodes = normalized.nodes.filter(node => (!repository || node.repository === repository) && (!kind || node.type === kind) && (!focusedNeighbors || focusedNeighbors.has(node.id)));
    return normalizeArchitecture({ nodes, edges: normalized.edges });
  }, [normalized, repository, kind, focusedNeighbors]);
  const layout = result?.graph === visible && result.direction === direction ? result.layout : null;
  const repositories = [...new Set(normalized.nodes.map(node => node.repository).filter((value): value is string => Boolean(value)))].sort();
  const component = normalized.nodes.find(node => node.id === selected);
  const searchResults = query.trim() ? visible.nodes.filter(node => `${node.name} ${node.repository || ""}`.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 8) : [];

  useEffect(() => {
    if (!visible.nodes.length) return;
    let active = true;
    let engine: InstanceType<typeof ELK> | undefined;
    setError("");
    const timer = window.setTimeout(() => { if (active) { active = false; engine?.terminateWorker(); setError("The layout took too long. Choose a repository or component type to reduce the diagram, then retry."); } }, 30000);
    try {
      engine = new ELK({ workerUrl: elkWorkerUrl });
      void engine.layout(layoutRequest(visible, direction)).then(output => {
        if (active) setResult({ graph: visible, direction, layout: readLayout(visible, output) });
      }).catch(() => { if (active) setError("The diagram could not be arranged. Retry the layout or narrow the displayed components."); })
        .finally(() => { window.clearTimeout(timer); engine?.terminateWorker(); });
    } catch { setError("The diagram layout engine could not start. Retry to load it again."); window.clearTimeout(timer); }
    return () => { active = false; window.clearTimeout(timer); engine?.terminateWorker(); };
  }, [visible, direction, retry]);

  useEffect(() => {
    const changed = () => setExpanded(document.fullscreenElement === container.current);
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, []);

  const selectNode = (id: string, center = false) => {
    setSelected(id); setSelectedEdge(null); setQuery("");
    if (center && !focused) {
      const item = layout?.nodes.find(node => node.node.id === id);
      if (item) void flow.current?.setCenter(item.x + NODE_WIDTH / 2, item.y + NODE_HEIGHT / 2, { zoom: 1, duration: 350 });
    }
  };
  const reset = () => { setRepository(""); setKind(""); setFocused(false); setSelected(null); setSelectedEdge(null); setQuery(""); };
  const nodes: ComponentNode[] = layout?.nodes.map(({ node, x, y }) => ({ id: node.id, type: "component", position: { x, y },
    data: { component: node, direction, dimmed: Boolean(selected && !connected.has(node.id)) }, selected: node.id === selected,
    width: NODE_WIDTH, height: NODE_HEIGHT, ariaLabel: `${appearance(node.type).label}: ${node.name}`, style: { width: NODE_WIDTH, height: NODE_HEIGHT } })) || [];
  const edges: ConnectionEdge[] = layout?.edges.map(route => {
    const highlighted = selectedEdge?.id === route.id || route.edge.source === selected || route.edge.target === selected;
    return { id: route.id, source: route.edge.source, target: route.edge.target, sourceHandle: "out", targetHandle: "in", type: "connection",
      data: { route, showLabel: labels && (!selected || highlighted) },
      markerEnd: { type: MarkerType.ArrowClosed, color: highlighted ? "#7c3aed" : "#94a3b8", width: 16, height: 16 },
      style: { stroke: highlighted ? "#7c3aed" : "#94a3b8", strokeWidth: highlighted ? 2.3 : 1.4, opacity: selected && !highlighted ? 0.18 : 1 },
      ariaLabel: relationship(route.edge), zIndex: highlighted ? 2 : 0 };
  }) || [];

  if (!normalized.nodes.length) return <EmptyState>No source-backed components were found in this analysis.</EmptyState>;
  return <div ref={container} className="ax-explorer">
    <header className="ax-heading"><div><span className="ax-eyebrow">CODEBASE INTELLIGENCE</span><h4>{title}</h4><p>Explore the structure. Follow the relationships. Inspect the evidence.</p></div><div className="ax-metrics"><span><strong>{normalized.nodes.length}</strong> components</span><span><strong>{normalized.edges.length}</strong> relationships</span><span><strong>{repositories.length}</strong> repositories</span></div></header>
    <div className="ax-toolbar">
      <div className="ax-search"><Search size={16} /><input aria-label="Find a component" placeholder="Find a component…" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key === "Escape") setQuery(""); if (event.key === "Enter" && searchResults[0]) selectNode(searchResults[0].id, true); }} />{query && <div className="ax-search-results">{searchResults.length ? searchResults.map(node => <button type="button" key={node.id} onClick={() => selectNode(node.id, true)}><strong>{node.name}</strong><small>{appearance(node.type).label} / {node.repository || "Source"}</small></button>) : <p>No matching components in this view.</p>}</div>}</div>
      <select aria-label="Filter by repository" value={repository} onChange={event => { setRepository(event.target.value); setSelected(null); setSelectedEdge(null); setFocused(false); }}><option value="">All repositories</option>{repositories.map(repo => <option key={repo}>{repo}</option>)}</select>
      <div className="ax-segment" aria-label="Diagram direction"><button type="button" aria-label="Left to right layout" aria-pressed={direction === "RIGHT"} onClick={() => setDirection("RIGHT")}><ArrowRight size={15} /></button><button type="button" aria-label="Top to bottom layout" aria-pressed={direction === "DOWN"} onClick={() => setDirection("DOWN")}><ArrowDown size={15} /></button></div>
      <label className="ax-label-toggle"><input type="checkbox" checked={labels} onChange={event => setLabels(event.target.checked)} />Labels</label>
      <div className="ax-toolbar-end"><button type="button" disabled={!layout} onClick={() => layout && downloadArchitecture(exportSvg(layout), "svg")}><Download size={14} />SVG</button><button type="button" disabled={!layout} onClick={() => layout && downloadArchitecture(exportDrawio(layout), "drawio")}><Download size={14} />draw.io</button><button type="button" aria-label={expanded ? "Exit fullscreen" : "Fullscreen diagram"} onClick={() => { const action = expanded ? document.exitFullscreen() : container.current?.requestFullscreen(); void action?.catch(() => setError("Fullscreen is unavailable in this browser.")); }}><Maximize2 size={15} /></button></div>
    </div>
    <div className="ax-workspace">
      <div className="ax-canvas" aria-label="Interactive architecture diagram">
        {error ? <div className="ax-state" role="alert"><Network size={30} /><p>{error}</p><button type="button" onClick={() => setRetry(value => value + 1)}>Retry layout</button></div> : !visible.nodes.length ? <div className="ax-state"><p>No components match these filters.</p><button type="button" onClick={reset}>Show all components</button></div> : !layout ? <div className="ax-state" role="status"><LoaderCircle className="li-spin" size={26} /><p>Arranging components and routing connections…</p></div> : <ReactFlow<ComponentNode, ConnectionEdge>
          nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onInit={instance => { flow.current = instance; }}
          nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} minZoom={0.03} maxZoom={2}
          onNodesChange={changes => { const chosen = changes.find(change => change.type === "select" && change.selected); if (chosen?.type === "select") selectNode(chosen.id); }}
          onNodeClick={(_, node) => selectNode(node.id)} onNodeDoubleClick={(_, node) => { selectNode(node.id); setFocused(true); }}
          onEdgeClick={(_, edge) => { setSelected(null); setFocused(false); setSelectedEdge(edge.data?.route || null); }}
          onPaneClick={() => { if (!focused) { setSelected(null); setSelectedEdge(null); } }}>
          <Background gap={24} size={1} color="#dce4ee" /><Controls showInteractive={false} fitViewOptions={{ padding: 0.12, maxZoom: 1 }} /><MiniMap nodeColor={node => appearance((node.data as ComponentNode["data"]).component.type).color} maskColor="#edf2f7bb" pannable zoomable /><FitLayout layout={layout} />
        </ReactFlow>}
        <div className="ax-canvas-caption">{visible.nodes.length} of {normalized.nodes.length} components{focused ? " · Focused neighborhood" : " · Source relationships"}</div>
      </div>
      <aside className="ax-inspector" aria-label="Component inspector">
        {component ? <><div className="ax-inspector-heading"><span className="ax-eyebrow">COMPONENT DETAILS</span><button type="button" aria-label="Clear selection" onClick={() => { setSelected(null); setFocused(false); }}><X size={16} /></button></div><span className="ax-kind-badge" style={{ color: appearance(component.type).color, background: appearance(component.type).fill }}>{appearance(component.type).label}</span><h4>{component.name}</h4><p className="ax-repository-name">{component.repository || "Repository not specified"}</p><button type="button" className="ax-focus-button" aria-pressed={focused} onClick={() => setFocused(value => !value)}><Focus size={15} />{focused ? "Show full view" : "Focus connections"}</button><h5>Connected components</h5><div className="ax-connections">{normalized.edges.filter(edge => edge.source === selected || edge.target === selected).map((edge, index) => {
          const outgoing = edge.source === selected, other = normalized.nodes.find(node => node.id === (outgoing ? edge.target : edge.source));
          return <button type="button" key={index} onClick={() => { setRepository(""); setKind(""); selectNode(other!.id, true); }}><small>{outgoing ? "Outgoing" : "Incoming"} · {relationship(edge)}</small><span>{other?.name}</span></button>;
        })}{connected.size <= 1 && <p>No connections to other components were discovered.</p>}</div><EvidencePanel key={component.id} evidence={component.evidence} /></> : selectedEdge ? <><span className="ax-eyebrow">RELATIONSHIP DETAILS</span><h4>{relationship(selectedEdge.edge)}</h4><p>{normalized.nodes.find(node => node.id === selectedEdge.edge.source)?.name}</p><ArrowDown size={16} /><p>{normalized.nodes.find(node => node.id === selectedEdge.edge.target)?.name}</p><EvidencePanel key={selectedEdge.id} evidence={selectedEdge.edge.evidence} /></> : <><span className="ax-eyebrow">EXPLORE YOUR SYSTEM</span><h4>From the big picture<br />to the source.</h4><p>Select a component to see its connections and supporting code. Double-click to isolate its neighborhood.</p><div className="ax-inspector-divider" /><h5>Component types</h5><div className="ax-type-list">{[...new Set(normalized.nodes.map(node => node.type))].map(type => { const theme = appearance(type), Icon = icons[type] || Network; return <button type="button" key={type} aria-pressed={kind === type} onClick={() => { setKind(value => value === type ? "" : type); setSelectedEdge(null); }}><Icon size={16} color={theme.color} /><span>{theme.label}</span><b>{normalized.nodes.filter(node => node.type === type).length}</b></button>; })}</div></>}
        {(repository || kind || focused) && <button type="button" className="ax-reset" onClick={reset}>Clear filters and selection</button>}
      </aside>
    </div>
    <footer className="ax-footer"><span><span className="ax-status-dot" />Based on analyzed source</span><span>Scroll to zoom · Drag to pan · Select to inspect</span></footer>
  </div>;
}
