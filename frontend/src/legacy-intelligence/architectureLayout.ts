import type { ElkNode, ElkPoint } from "elkjs/lib/elk-api";
import type { Architecture, ArchitectureEdge, ArchitectureNode } from "./types";

export const NODE_WIDTH = 252;
export const NODE_HEIGHT = 116;
export type Direction = "RIGHT" | "DOWN";
export interface PositionedNode { node: ArchitectureNode; x: number; y: number }
export interface RoutedEdge { id: string; edge: ArchitectureEdge; points: ElkPoint[]; label?: { x: number; y: number; text: string } }
export interface ArchitectureLayout { nodes: PositionedNode[]; edges: RoutedEdge[]; width: number; height: number }
export const componentAppearance: Record<string, { label: string; color: string; fill: string }> = {
  repository: { label: "Repository", color: "#64748b", fill: "#f1f5f9" },
  api: { label: "API endpoint", color: "#0284c7", fill: "#e0f2fe" },
  client: { label: "Client", color: "#2563eb", fill: "#eff6ff" },
  gateway: { label: "Gateway", color: "#7c3aed", fill: "#f5f3ff" },
  service: { label: "Service", color: "#059669", fill: "#ecfdf5" },
  function: { label: "Function", color: "#0891b2", fill: "#ecfeff" },
  database: { label: "Database", color: "#e11d48", fill: "#fff1f2" },
  external: { label: "External reference", color: "#d97706", fill: "#fffbeb" },
  job: { label: "Scheduled job", color: "#9333ea", fill: "#faf5ff" },
};
export const appearance = (type: string) => componentAppearance[type] || { label: type || "Component", color: "#64748b", fill: "#f1f5f9" };
export const relationship = (edge: ArchitectureEdge) => edge.relationship || edge.relationshipType || "Related to";

export function normalizeArchitecture(graph: Architecture): Architecture {
  const nodes = [...new Map(graph.nodes.map(node => [node.id, node])).values()];
  const ids = new Set(nodes.map(node => node.id));
  return { nodes, edges: graph.edges.filter(edge => ids.has(edge.source) && ids.has(edge.target)) };
}

export function layoutRequest(graph: Architecture, direction: Direction): ElkNode {
  const ids = new Map(graph.nodes.map((node, index) => [node.id, `n${index}`]));
  return {
    id: "architecture",
    layoutOptions: {
      "elk.algorithm": "layered", "elk.direction": direction, "elk.edgeRouting": "ORTHOGONAL",
      "elk.padding": "[top=45,left=45,bottom=45,right=45]",
      "elk.spacing.nodeNode": "40", "elk.layered.spacing.nodeNodeBetweenLayers": "65",
      "elk.spacing.edgeNode": "25", "elk.layered.spacing.edgeNodeBetweenLayers": "30",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      "elk.separateConnectedComponents": "true", "elk.spacing.componentComponent": "85",
      "elk.randomSeed": "1",
    },
    children: graph.nodes.map((_, index) => ({
      id: `n${index}`, width: NODE_WIDTH, height: NODE_HEIGHT,
      layoutOptions: { "elk.portConstraints": "FIXED_POS" },
      ports: [
        { id: `n${index}-in`, x: direction === "RIGHT" ? 0 : NODE_WIDTH / 2, y: direction === "RIGHT" ? NODE_HEIGHT / 2 : 0, width: 0, height: 0, layoutOptions: { "elk.port.side": direction === "RIGHT" ? "WEST" : "NORTH" } },
        { id: `n${index}-out`, x: direction === "RIGHT" ? NODE_WIDTH : NODE_WIDTH / 2, y: direction === "RIGHT" ? NODE_HEIGHT / 2 : NODE_HEIGHT, width: 0, height: 0, layoutOptions: { "elk.port.side": direction === "RIGHT" ? "EAST" : "SOUTH" } },
      ],
    })),
    edges: graph.edges.map((edge, index) => {
      const text = relationship(edge).slice(0, 38);
      return { id: `e${index}`, sources: [`${ids.get(edge.source)}-out`], targets: [`${ids.get(edge.target)}-in`],
        labels: [{ text, width: Math.max(48, text.length * 6.5 + 16), height: 24 }] };
    }),
  };
}

export function readLayout(graph: Architecture, result: ElkNode): ArchitectureLayout {
  const positions = new Map(result.children?.map(node => [node.id, node]));
  const routes = new Map(result.edges?.map(edge => [edge.id, edge]));
  return {
    width: result.width || 0, height: result.height || 0,
    nodes: graph.nodes.map((node, index) => ({ node, x: positions.get(`n${index}`)?.x || 0, y: positions.get(`n${index}`)?.y || 0 })),
    edges: graph.edges.map((edge, index) => {
      const route = routes.get(`e${index}`);
      const section = route?.sections?.[0];
      if (!section) throw new Error("A source relationship could not be routed.");
      const label = route?.labels?.[0];
      return { id: `e${index}`, edge, points: [section.startPoint, ...(section.bendPoints || []), section.endPoint],
        label: label ? { x: (label.x || 0) + (label.width || 0) / 2, y: (label.y || 0) + (label.height || 0) / 2, text: label.text || "" } : undefined };
    }),
  };
}

export const edgePath = (points: ElkPoint[]) => points.map((point, index) => `${index ? "L" : "M"}${point.x},${point.y}`).join(" ");
