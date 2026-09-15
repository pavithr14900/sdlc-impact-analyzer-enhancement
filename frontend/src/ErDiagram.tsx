import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

interface ErEntity {
  name: string;
  fields: string[];
}

interface ErRelationship {
  from: string;
  to: string;
  label?: string;
}

interface ErDiagramProps {
  spec: {
    entities: ErEntity[];
    relationships: ErRelationship[];
  };
}

const COLUMNS = 3;
const COLUMN_GAP = 260;
const ROW_GAP = 190;

export default function ErDiagram({ spec }: ErDiagramProps) {
  const { nodes, edges } = useMemo(() => {
    const flowNodes: Node[] = spec.entities.map((entity, index) => ({
      id: entity.name,
      position: {
        x: (index % COLUMNS) * COLUMN_GAP,
        y: Math.floor(index / COLUMNS) * ROW_GAP,
      },
      data: {
        label: (
          <div className="er-node">
            <strong>{entity.name}</strong>
            <ul>
              {entity.fields.slice(0, 6).map((field) => (
                <li key={field}>{field}</li>
              ))}
            </ul>
          </div>
        ),
      },
      style: {
        width: 210,
        padding: 0,
        border: "1px solid #d9d3fb",
        borderRadius: 10,
        background: "#ffffff",
      },
    }));

    const nodeIds = new Set(flowNodes.map((node) => node.id));
    const flowEdges: Edge[] = spec.relationships
      .filter((rel) => nodeIds.has(rel.from) && nodeIds.has(rel.to))
      .map((rel, index) => ({
        id: `er-edge-${index}`,
        source: rel.from,
        target: rel.to,
        label: rel.label,
        type: "smoothstep",
        style: { stroke: "#9d91ff" },
        labelStyle: { fill: "#5649bd", fontSize: 10, fontWeight: 700 },
        labelBgStyle: { fill: "#f5f3fd" },
      }));

    return { nodes: flowNodes, edges: flowEdges };
  }, [spec]);

  return (
    <div className="er-diagram-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} color="#ece9fb" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
