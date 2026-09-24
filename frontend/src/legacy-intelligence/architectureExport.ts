import { appearance, edgePath, NODE_HEIGHT, NODE_WIDTH, relationship, type ArchitectureLayout } from "./architectureLayout";

const esc = (text: string) => text.replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[char]!);

export function exportDrawio(layout: ArchitectureLayout): string {
  const ids = new Map(layout.nodes.map(({ node }, index) => [node.id, `n${index}`]));
  const cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>'];
  layout.nodes.forEach(({ node, x, y }) => {
    const theme = appearance(node.type);
    const label = [theme.label.toUpperCase(), node.name, node.repository].filter(Boolean).join("\n");
    cells.push(`<mxCell id="${ids.get(node.id)}" value="${esc(label).replace(/\n/g, "&#xa;")}" vertex="1" parent="1" style="rounded=1;arcSize=12;whiteSpace=wrap;html=0;fillColor=${theme.fill};strokeColor=${theme.color};strokeWidth=2;fontColor=#172b46;fontSize=13;spacing=12;"><mxGeometry x="${x}" y="${y}" width="${NODE_WIDTH}" height="${NODE_HEIGHT}" as="geometry"/></mxCell>`);
  });
  layout.edges.forEach(({ id, edge, points }) => {
    const source = layout.nodes.find(item => item.node.id === edge.source)!;
    const target = layout.nodes.find(item => item.node.id === edge.target)!;
    const start = points[0], end = points[points.length - 1];
    const bends = points.slice(1, -1).map(point => `<mxPoint x="${point.x}" y="${point.y}"/>`).join("");
    cells.push(`<mxCell id="${id}" value="${esc(relationship(edge))}" edge="1" parent="1" source="${ids.get(edge.source)}" target="${ids.get(edge.target)}" style="rounded=1;html=0;endArrow=block;strokeColor=#94a3b8;fontSize=11;labelBackgroundColor=#ffffff;exitX=${(start.x - source.x) / NODE_WIDTH};exitY=${(start.y - source.y) / NODE_HEIGHT};entryX=${(end.x - target.x) / NODE_WIDTH};entryY=${(end.y - target.y) / NODE_HEIGHT};"><mxGeometry relative="1" as="geometry"><Array as="points">${bends}</Array></mxGeometry></mxCell>`);
  });
  return `<mxfile host="app.diagrams.net"><diagram name="System Architecture" id="architecture"><mxGraphModel grid="0" page="0" background="#ffffff"><root>${cells.join("")}</root></mxGraphModel></diagram></mxfile>`;
}

function wrap(text: string, length: number, limit: number): string[] {
  const chunks = text.match(new RegExp(`.{1,${length}}(?:\\s|$)|.{1,${length}}`, "g")) || [text];
  const lines = chunks.slice(0, limit).map(line => line.trim());
  if (chunks.length > limit) lines[limit - 1] = lines[limit - 1].slice(0, -1) + "…";
  return lines;
}

export function exportSvg(layout: ArchitectureLayout): string {
  const edges = layout.edges.map(({ edge, points, label }) => `<g><title>${esc(relationship(edge))}</title><path d="${edgePath(points)}" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linejoin="round" marker-end="url(#arrow)"/>${label ? `<text x="${label.x}" y="${label.y + 4}" text-anchor="middle" font-size="11" fill="#52647b" stroke="#f8fafc" stroke-width="5" paint-order="stroke">${esc(label.text)}</text>` : ""}</g>`).join("");
  const nodes = layout.nodes.map(({ node, x, y }) => {
    const theme = appearance(node.type);
    return `<g transform="translate(${x},${y})"><title>${esc(node.name)}</title><rect width="${NODE_WIDTH}" height="${NODE_HEIGHT}" rx="12" fill="#ffffff" stroke="#d9e2ed"/><rect width="4" height="${NODE_HEIGHT - 24}" x="0" y="12" rx="2" fill="${theme.color}"/><text x="18" y="25" font-size="10" font-weight="700" fill="${theme.color}">${esc(theme.label.toUpperCase())}</text>${wrap(node.name, 29, 2).map((line, index) => `<text x="18" y="${49 + index * 18}" font-size="13" font-weight="600" fill="#172b46">${esc(line)}</text>`).join("")}<text x="18" y="97" font-size="10" fill="#64748b">${esc(wrap(node.repository || "Source component", 34, 1)[0])}</text></g>`;
  }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${layout.width}" height="${layout.height + 75}" viewBox="0 0 ${layout.width} ${layout.height + 75}" font-family="Arial, sans-serif"><title>System architecture</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/></marker></defs><rect width="100%" height="100%" fill="#f8fafc"/><text x="45" y="38" font-size="22" font-weight="700" fill="#172b46">System architecture</text><text x="45" y="60" font-size="12" fill="#64748b">${layout.nodes.length} components · ${layout.edges.length} source relationships</text><g transform="translate(0,75)">${edges}${nodes}</g></svg>`;
}

export function downloadArchitecture(content: string, extension: "svg" | "drawio") {
  const url = URL.createObjectURL(new Blob([content], { type: extension === "svg" ? "image/svg+xml" : "application/xml" }));
  const link = document.createElement("a");
  link.href = url; link.download = `system-architecture.${extension}`;
  document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
