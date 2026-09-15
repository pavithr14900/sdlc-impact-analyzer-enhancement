"""Deterministic draw.io (mxGraph) renderer for architecture diagrams."""

import re
from datetime import datetime
from xml.sax.saxutils import escape

PALETTE = {
    "client": ("#E8F1FE", "#2563EB", "#1E3A8A"),
    "gateway": ("#EDE9FE", "#7C3AED", "#4C1D95"),
    "security": ("#FEF3C7", "#D97706", "#78350F"),
    "api": ("#E0F2FE", "#0284C7", "#075985"),
    "service": ("#DCFCE7", "#16A34A", "#14532D"),
    "repository": ("#F1F5F9", "#475569", "#1E293B"),
    "database": ("#FFE4E6", "#E11D48", "#881337"),
    "messaging": ("#FFEDD5", "#EA580C", "#7C2D12"),
    "external": ("#F5F3FF", "#8B5CF6", "#5B21B6"),
    "observability": ("#CFFAFE", "#0891B2", "#164E63"),
}

NODE_WIDTH = 210
NODE_HEIGHT = 74
NODE_GAP_X = 34
LAYER_HEADER = 34
LAYER_PAD = 22
LAYER_HEIGHT = LAYER_HEADER + LAYER_PAD + NODE_HEIGHT + LAYER_PAD
LAYER_GAP_Y = 58
CANVAS_MARGIN = 40
TITLE_HEIGHT = 70

_QUOTE = {chr(34): "&quot;"}


def fallback_spec() -> dict:

    return {
        "title": "Solution Architecture",
        "layers": [
            {
                "name": "Client Layer",
                "nodes": [
                    {
                        "id": "web_app",
                        "label": "Web Application",
                        "tech": "React / TypeScript",
                        "type": "client"
                    }
                ]
            },
            {
                "name": "Edge & Security",
                "nodes": [
                    {
                        "id": "api_gateway",
                        "label": "API Gateway",
                        "tech": "HTTPS / CORS",
                        "type": "gateway"
                    },
                    {
                        "id": "auth",
                        "label": "Authentication",
                        "tech": "Spring Security / JWT",
                        "type": "security"
                    }
                ]
            },
            {
                "name": "Application Layer",
                "nodes": [
                    {
                        "id": "controller",
                        "label": "REST Controllers",
                        "tech": "Spring Web",
                        "type": "api"
                    },
                    {
                        "id": "validation",
                        "label": "Validation & Errors",
                        "tech": "Jakarta Validation",
                        "type": "security"
                    }
                ]
            },
            {
                "name": "Domain Layer",
                "nodes": [
                    {
                        "id": "service",
                        "label": "Business Services",
                        "tech": "Spring Service",
                        "type": "service"
                    }
                ]
            },
            {
                "name": "Persistence Layer",
                "nodes": [
                    {
                        "id": "repository",
                        "label": "Repositories",
                        "tech": "Spring Data JPA",
                        "type": "repository"
                    },
                    {
                        "id": "database",
                        "label": "PostgreSQL",
                        "tech": "Relational Database",
                        "type": "database"
                    }
                ]
            }
        ],
        "connections": [
            {"from": "web_app", "to": "api_gateway", "label": "HTTPS / REST"},
            {"from": "api_gateway", "to": "auth", "label": "Authenticate"},
            {"from": "api_gateway", "to": "controller", "label": "JSON"},
            {"from": "controller", "to": "validation", "label": "Validate"},
            {"from": "controller", "to": "service", "label": "DTO"},
            {"from": "service", "to": "repository", "label": "Domain model"},
            {"from": "repository", "to": "database", "label": "JPA / SQL"}
        ]
    }


def _clean_id(value: object) -> str:

    return re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        str(value).strip()
    )


def normalize_spec(spec: dict) -> dict:

    layers = []
    known_ids = set()

    for layer in spec.get("layers", [])[:6]:

        nodes = []

        for node in layer.get("nodes", [])[:4]:

            node_id = _clean_id(node.get("id", ""))

            if not node_id or node_id in known_ids:
                continue

            known_ids.add(node_id)

            node_type = str(
                node.get("type", "service")
            ).strip().lower()

            if node_type not in PALETTE:
                node_type = "service"

            nodes.append({
                "id": node_id,
                "label": str(node.get("label", node_id))[:40],
                "tech": str(node.get("tech", ""))[:40],
                "type": node_type
            })

        if nodes:
            layers.append({
                "name": str(layer.get("name", "Layer"))[:40],
                "nodes": nodes
            })

    if not layers:
        raise ValueError("Diagram specification contains no layers.")

    connections = []

    for connection in spec.get("connections", []):

        source = _clean_id(connection.get("from", ""))
        target = _clean_id(connection.get("to", ""))

        if source in known_ids and target in known_ids:
            connections.append({
                "from": source,
                "to": target,
                "label": str(connection.get("label", ""))[:30]
            })

    return {
        "title": str(spec.get("title", "Solution Architecture"))[:80],
        "layers": layers,
        "connections": connections
    }


def _node_style(node_type: str) -> str:

    fill, stroke, font = PALETTE[node_type]

    base = (
        f"whiteSpace=wrap;html=1;fillColor={fill};"
        f"strokeColor={stroke};strokeWidth=2;"
        f"fontColor={font};fontSize=13;align=center;"
        "verticalAlign=middle;shadow=1;"
    )

    if node_type == "database":
        return (
            "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=14;"
            + base
        )

    if node_type == "messaging":
        return "shape=process;size=0.12;rounded=1;arcSize=8;" + base

    if node_type == "external":
        return "rounded=1;arcSize=14;dashed=1;dashPattern=8 4;" + base

    return "rounded=1;arcSize=14;" + base


def _cell(cell_id: str, value: str, style: str, geometry: str) -> str:

    return (
        f'        <mxCell id="{cell_id}" '
        f'value="{escape(value, _QUOTE)}" '
        f'style="{style}" vertex="1" parent="1">\n'
        f'          {geometry}\n'
        "        </mxCell>\n"
    )


def build_drawio_xml(spec: dict) -> str:

    spec = normalize_spec(spec)

    widest = max(
        len(layer["nodes"])
        for layer in spec["layers"]
    )

    inner_width = widest * NODE_WIDTH + (widest - 1) * NODE_GAP_X

    layer_width = max(inner_width + 2 * LAYER_PAD, 780)
    canvas_width = layer_width + 2 * CANVAS_MARGIN

    cells = [
        _cell(
            "diagram_title",
            spec["title"],
            "text;html=1;align=center;verticalAlign=middle;"
            "fontSize=22;fontStyle=1;fontColor=#0F172A;",
            f'<mxGeometry x="{CANVAS_MARGIN}" y="20" '
            f'width="{layer_width}" height="40" as="geometry" />'
        )
    ]

    node_positions = {}
    y_cursor = TITLE_HEIGHT + 20

    for index, layer in enumerate(spec["layers"]):

        cells.append(
            _cell(
                f"layer_{index}",
                layer["name"],
                "swimlane;html=1;horizontal=1;rounded=1;arcSize=8;"
                f"startSize={LAYER_HEADER};fillColor=#FFFFFF;"
                "strokeColor=#CBD5E1;strokeWidth=1;"
                "fontColor=#0F172A;fontSize=13;fontStyle=1;"
                "swimlaneFillColor=#F8FAFC;"
                "dashed=1;dashPattern=6 4;shadow=0;",
                f'<mxGeometry x="{CANVAS_MARGIN}" y="{y_cursor}" '
                f'width="{layer_width}" height="{LAYER_HEIGHT}" '
                'as="geometry" />'
            )
        )

        count = len(layer["nodes"])

        row_width = count * NODE_WIDTH + (count - 1) * NODE_GAP_X

        start_x = (layer_width - row_width) / 2
        node_y = y_cursor + LAYER_HEADER + LAYER_PAD

        for position, node in enumerate(layer["nodes"]):

            node_x = CANVAS_MARGIN + start_x + position * (
                NODE_WIDTH + NODE_GAP_X
            )

            label = f"<b>{node['label']}</b>"

            if node["tech"]:
                label += (
                    '<br/><font style="font-size:10px;">'
                    f"{node['tech']}</font>"
                )

            cells.append(
                _cell(
                    node["id"],
                    label,
                    _node_style(node["type"]),
                    f'<mxGeometry x="{node_x:.0f}" y="{node_y}" '
                    f'width="{NODE_WIDTH}" height="{NODE_HEIGHT}" '
                    'as="geometry" />'
                )
            )

            node_positions[node["id"]] = {
                "layer": index,
                "x": node_x
            }

        y_cursor += LAYER_HEIGHT + LAYER_GAP_Y

    edges = []

    for edge_index, connection in enumerate(spec["connections"]):

        source = node_positions[connection["from"]]
        target = node_positions[connection["to"]]

        if target["layer"] > source["layer"]:
            side = 1 if edge_index % 2 == 0 else 0
            exit_x, exit_y, entry_x, entry_y = side, 0.5, side, 0.5
        elif target["layer"] < source["layer"]:
            exit_x, exit_y, entry_x, entry_y = 0.5, 0, 0.5, 1
        elif target["x"] > source["x"]:
            exit_x, exit_y, entry_x, entry_y = 1, 0.5, 0, 0.5
        else:
            exit_x, exit_y, entry_x, entry_y = 0, 0.5, 1, 0.5

        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;"
            "jettySize=auto;orthogonalLoop=1;strokeColor=#64748B;"
            "strokeWidth=2;endArrow=blockThin;endFill=1;"
            "fontSize=10;fontColor=#334155;labelBackgroundColor=#FFFFFF;"
            f"exitX={exit_x};exitY={exit_y};exitDx=0;exitDy=0;"
            f"entryX={entry_x};entryY={entry_y};entryDx=0;entryDy=0;"
        )

        edges.append(
            f'        <mxCell id="edge_{edge_index}" '
            f'value="{escape(connection["label"], _QUOTE)}" '
            f'style="{style}" edge="1" parent="1" '
            f'source="{connection["from"]}" '
            f'target="{connection["to"]}">\n'
            '          <mxGeometry relative="1" as="geometry" />\n'
            "        </mxCell>\n"
        )

    canvas_height = y_cursor + CANVAS_MARGIN

    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    body = "".join(cells) + "".join(edges)

    return (
        '<mxfile host="ai-sdlc-agent" '
        f'modified="{timestamp}" agent="AI SDLC Assistant" '
        'type="device">\n'
        '  <diagram id="architecture" '
        f'name="{escape(spec["title"], _QUOTE)}">\n'
        '    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" '
        'guides="1" tooltips="1" connect="1" arrows="1" fold="1" '
        f'page="1" pageScale="1" pageWidth="{canvas_width}" '
        f'pageHeight="{canvas_height}" math="0" shadow="0">\n'
        "      <root>\n"
        '        <mxCell id="0" />\n'
        '        <mxCell id="1" parent="0" />\n'
        f"{body}"
        "      </root>\n"
        "    </mxGraphModel>\n"
        "  </diagram>\n"
        "</mxfile>\n"
    )
