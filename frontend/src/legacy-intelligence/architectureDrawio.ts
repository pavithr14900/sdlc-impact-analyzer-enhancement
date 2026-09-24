import type { Architecture } from "./types";

const escapeXml = (value: string) => value.replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[char]!);
const layers = [
  { title: "Repositories", types: ["repository"], fill: "#F1F5F9", stroke: "#475569" },
  { title: "Interfaces & entry points", types: ["api", "client", "gateway"], fill: "#E0F2FE", stroke: "#0284C7" },
  { title: "Application & domain", types: ["service", "function", "job"], fill: "#DCFCE7", stroke: "#16A34A" },
  { title: "Persistence", types: ["database"], fill: "#FFE4E6", stroke: "#E11D48" },
  { title: "External dependencies", types: ["external"], fill: "#F5F3FF", stroke: "#8B5CF6" },
  { title: "Other components", types: [], fill: "#FEF3C7", stroke: "#D97706" },
];

/** Build from source data rather than React labels or a filtered display layout. */
export function architectureToDrawio(graph: Architecture): string {
  const nodes = [...new Map(graph.nodes.map(node => [node.id, node])).values()];
  const ids = new Map(nodes.map((node, index) => [node.id, `component-${index}`]));
  const cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>'];
  const vertex = (id: string, label: string, style: string, x: number, y: number, width: number, height: number) => {
    cells.push(`<mxCell id="${id}" value="${escapeXml(label).replace(/\n/g, "&#xa;")}" style="${style}" vertex="1" parent="1"><mxGeometry x="${x}" y="${y}" width="${width}" height="${height}" as="geometry"/></mxCell>`);
  };
  vertex("title", "SYSTEM ARCHITECTURE", "text;html=0;align=left;fontSize=24;fontStyle=1;fontColor=#0F172A;", 40, 24, 1120, 40);
  vertex("subtitle", `${nodes.length} components · Source-backed relationships · Grouped by architectural role`, "text;html=0;align=left;fontSize=12;fontColor=#64748B;", 40, 66, 1120, 30);
  let y = 125;
  layers.forEach((layer, index) => {
    const members = nodes.filter(node => layer.types.includes(node.type) || (index === layers.length - 1 && !layers.some(item => item.types.includes(node.type))))
      .sort((a, b) => (a.repository || "").localeCompare(b.repository || "") || a.name.localeCompare(b.name));
    if (!members.length) return;
    const height = 65 + Math.ceil(members.length / 4) * 142;
    vertex(`layer-${index}`, layer.title.toUpperCase(), "swimlane;html=0;startSize=40;horizontal=1;rounded=1;arcSize=8;fillColor=#F8FAFC;swimlaneFillColor=#FFFFFF;strokeColor=#CBD5E1;fontColor=#334155;fontSize=13;fontStyle=1;align=left;spacingLeft=18;", 40, y, 1120, height);
    members.forEach((node, position) => {
      const label = [node.name, node.type.toUpperCase(), node.repository].filter(Boolean).join("\n");
      vertex(ids.get(node.id)!, label, `rounded=1;arcSize=12;whiteSpace=wrap;html=0;fillColor=${layer.fill};strokeColor=${layer.stroke};strokeWidth=1.5;fontColor=#0F172A;fontSize=13;fontFamily=Helvetica;spacing=12;${node.type === "database" ? "shape=cylinder;size=15;" : ""}`, 62 + (position % 4) * 274, y + 60 + Math.floor(position / 4) * 142, 250, 110);
    });
    y += height + 65;
  });
  graph.edges.forEach((edge, index) => {
    const source = ids.get(edge.source), target = ids.get(edge.target);
    if (!source || !target) return;
    cells.push(`<mxCell id="edge-${index}" value="${escapeXml(edge.relationship || edge.relationshipType || "")}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;jettySize=auto;html=0;endArrow=block;endFill=1;strokeColor=#64748B;strokeWidth=1.5;fontSize=11;fontColor=#475569;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="${source}" target="${target}"><mxGeometry relative="1" as="geometry"/></mxCell>`);
  });
  return `<mxfile host="app.diagrams.net"><diagram id="architecture" name="System Architecture"><mxGraphModel grid="0" page="0" pageWidth="1200" pageHeight="${y}" background="#ffffff"><root>${cells.join("")}</root></mxGraphModel></diagram></mxfile>`;
}
