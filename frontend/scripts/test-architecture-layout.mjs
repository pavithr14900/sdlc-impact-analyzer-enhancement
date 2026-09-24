import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";
import ELK from "elkjs/lib/elk.bundled.js";

function compile(path, replacements = {}) {
  let source = ts.transpileModule(fs.readFileSync(new URL(path, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023 } }).outputText;
  for (const [from, to] of Object.entries(replacements)) source = source.replaceAll(from, to);
  return "data:text/javascript;base64," + Buffer.from(source).toString("base64");
}
const modelUrl = compile("../src/legacy-intelligence/architectureLayout.ts");
const { normalizeArchitecture, layoutRequest, readLayout, NODE_WIDTH, NODE_HEIGHT } = await import(modelUrl);
const { exportDrawio, exportSvg } = await import(compile("../src/legacy-intelligence/architectureExport.ts", { '"./architectureLayout"': JSON.stringify(modelUrl) }));

const nodes = ["api", "api", "service", "service", "database", "external", "job", "repository", "custom"].map((type, index) => ({ id: `component<&${index}`, name: `Component ${index} <A&B>`, type, repository: `repo-${index % 2}` }));
const edge = (source, target, relationship = "calls & validates") => ({ source: nodes[source].id, target: nodes[target].id, relationship });
const raw = { nodes: [...nodes, nodes[0]], edges: [edge(0, 2), edge(1, 3), edge(2, 4), edge(3, 4), edge(2, 3), edge(3, 2), edge(4, 4), { source: "missing", target: nodes[0].id }] };
const snapshot = JSON.stringify(raw);
const graph = normalizeArchitecture(raw);
assert.equal(graph.nodes.length, 9);
assert.equal(graph.edges.length, 7);
const engine = new ELK();
for (const direction of ["RIGHT", "DOWN"]) {
  const layout = readLayout(graph, await engine.layout(layoutRequest(graph, direction)));
  assert.equal(layout.nodes.length, 9);
  assert.equal(layout.edges.length, 7);
  for (const node of layout.nodes) {
    assert.ok(Number.isFinite(node.x) && Number.isFinite(node.y));
    for (const other of layout.nodes) {
      if (node === other) continue;
      assert.ok(node.x + NODE_WIDTH <= other.x || other.x + NODE_WIDTH <= node.x || node.y + NODE_HEIGHT <= other.y || other.y + NODE_HEIGHT <= node.y, "Nodes must not overlap");
    }
  }
  for (const route of layout.edges) {
    assert.ok(route.points.length >= 2);
    for (let i = 1; i < route.points.length; i++) {
      const a = route.points[i - 1], b = route.points[i];
      assert.ok(a.x === b.x || a.y === b.y, "Connectors must be orthogonal");
      for (const item of layout.nodes) {
        if (item.node.id === route.edge.source || item.node.id === route.edge.target) continue;
        const crosses = a.x === b.x
          ? a.x > item.x && a.x < item.x + NODE_WIDTH && Math.max(a.y, b.y) > item.y && Math.min(a.y, b.y) < item.y + NODE_HEIGHT
          : a.y > item.y && a.y < item.y + NODE_HEIGHT && Math.max(a.x, b.x) > item.x && Math.min(a.x, b.x) < item.x + NODE_WIDTH;
        assert.equal(crosses, false, "Connectors must not cross unrelated nodes");
      }
    }
  }
  const xml = exportDrawio(layout), svg = exportSvg(layout);
  assert.equal((xml.match(/vertex="1"/g) || []).length, 9);
  assert.equal((xml.match(/edge="1"/g) || []).length, 7);
  assert.ok(xml.includes("calls &amp; validates") && xml.includes("&lt;A&amp;B&gt;"));
  assert.ok(svg.includes("<svg") && svg.includes("&lt;A&amp;B&gt;"));
  assert.ok(!xml.includes("undefined") && !svg.includes("NaN"));
}
const large = { nodes: Array.from({ length: 100 }, (_, i) => ({ id: `n${i}`, name: `Service ${i}`, type: "service" })), edges: Array.from({ length: 99 }, (_, i) => ({ source: `n${Math.floor(i / 3)}`, target: `n${i + 1}` })) };
assert.equal(readLayout(large, await engine.layout(layoutRequest(large, "RIGHT"))).nodes.length, 100);
assert.equal(JSON.stringify(raw), snapshot, "Input must remain unchanged");
// The bundled Node runner uses ELK's synchronous worker shim (no OS worker to stop).
console.log("PASS: cycles, self-loops, shared databases, disconnected nodes, both directions, routed edges, exports, 100 components, input immutability.");
