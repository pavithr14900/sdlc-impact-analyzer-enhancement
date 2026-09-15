import "./prototypeTheme.css";
import { useMemo, useState, type CSSProperties } from "react";
import {
  CalendarPlus,
  Check,
  CheckCircle2,
  ClipboardList,
  LayoutDashboard,
  Maximize2,
  Minimize2,
  Monitor,
  PieChart,
  Smartphone,
  Tablet,
  UserCheck,
  X,
} from "lucide-react";

interface PrototypeComponentSpec {
  type: string;
  text?: string;
  label?: string;
  inputType?: string;
  variant?: string;
  columns?: string[];
  items?: string[];
}

interface PrototypeScreen {
  name: string;
  description?: string;
  components: PrototypeComponentSpec[];
}

export interface AppPrototypeSpec {
  appName?: string;
  layout?: "sidebar" | "topnav" | "stacked";
  theme?: Record<string, string>;
  designNotes?: string[];
  screens: PrototypeScreen[];
}

type Device = "desktop" | "tablet" | "mobile";

const DEVICE_WIDTHS: Record<Device, string> = {
  desktop: "100%",
  tablet: "834px",
  mobile: "390px",
};

// Screen names are AI-generated free text, so icons/mock data/status
// columns are all matched by keyword instead of an exact lookup.
function screenIcon(name: string) {
  const label = name.toLowerCase();
  if (label.includes("dashboard") || label.includes("overview")) return <LayoutDashboard size={17} />;
  if (label.includes("balance") || label.includes("summary")) return <PieChart size={17} />;
  if (label.includes("approv") || label.includes("manager") || label.includes("review")) return <UserCheck size={17} />;
  if (label.includes("submit") || label.includes("create") || label.includes("new") || label.includes("request")) return <CalendarPlus size={17} />;
  return <ClipboardList size={17} />;
}

const SAMPLE_PEOPLE = ["Jordan Lee", "Priya Nair", "Sam Carter", "Alex Morgan", "Taylor Reed"];
const SAMPLE_DATES = ["12 Jan 2026", "03 Feb 2026", "21 Feb 2026", "07 Mar 2026", "18 Mar 2026"];
const STATUS_CYCLE = ["Pending", "Approved", "Rejected"];

function statusBadgeClass(value: string) {
  const label = value.toLowerCase();
  if (label.includes("approv") || label.includes("active") || label.includes("complete")) return "proto-badge proto-badge-green";
  if (label.includes("reject") || label.includes("inactive") || label.includes("overdue")) return "proto-badge proto-badge-red";
  if (label.includes("pending") || label.includes("review")) return "proto-badge proto-badge-amber";
  return "proto-badge";
}

function mockCell(column: string, rowIndex: number, overrideStatus?: string): { value: string; isStatus: boolean } {
  const label = column.toLowerCase();

  if (overrideStatus && label.includes("status")) {
    return { value: overrideStatus, isStatus: true };
  }
  if (label.includes("status")) {
    return { value: STATUS_CYCLE[rowIndex % STATUS_CYCLE.length], isStatus: true };
  }
  if (label.includes("name") || label.includes("employee") || label.includes("customer") || label.includes("user")) {
    return { value: SAMPLE_PEOPLE[rowIndex % SAMPLE_PEOPLE.length], isStatus: false };
  }
  if (label.includes("date")) {
    return { value: SAMPLE_DATES[rowIndex % SAMPLE_DATES.length], isStatus: false };
  }
  if (label.includes("id") || label === "#") {
    return { value: `#${1000 + rowIndex}`, isStatus: false };
  }
  if (label.includes("day") || label.includes("hour") || label.includes("balance")) {
    return { value: `${3 + rowIndex * 2} days`, isStatus: false };
  }
  if (label.includes("amount") || label.includes("total") || label.includes("cost") || label.includes("price")) {
    return { value: `$${(120 + rowIndex * 45).toFixed(2)}`, isStatus: false };
  }
  if (label.includes("type") || label.includes("category")) {
    return { value: ["Annual", "Sick", "Casual"][rowIndex % 3], isStatus: false };
  }
  return { value: `Item ${rowIndex + 1} detail`, isStatus: false };
}

// A "card" component's free-text is rendered as a stat tile when it looks
// like "Label: value" (matching the dashboard summary-card look from the
// reference design); otherwise it falls back to a plain descriptive card.
function parseStatCard(text: string): { label: string; value: string } | null {
  const match = text.match(/^([^:]{2,40}):\s*(.+)$/);
  if (!match) return null;
  return { label: match[1].trim(), value: match[2].trim() };
}

function PrototypeTable({
  component,
  filterStatus,
  showActions,
}: {
  component: PrototypeComponentSpec;
  filterStatus: string | null;
  showActions: boolean;
}) {
  const columns = component.columns && component.columns.length ? component.columns : ["Item"];
  const statusColumnIndex = columns.findIndex((column) => column.toLowerCase().includes("status"));
  const rowCount = 4;

  const [overrides, setOverrides] = useState<Record<number, string>>({});

  const rows = Array.from({ length: rowCount }, (_, rowIndex) =>
    columns.map((column) => mockCell(column, rowIndex, statusColumnIndex >= 0 ? overrides[rowIndex] : undefined))
  );

  const visibleRows = rows
    .map((row, rowIndex) => ({ row, rowIndex }))
    .filter(({ row }) => {
      if (!filterStatus || statusColumnIndex < 0) return true;
      return row[statusColumnIndex].value.toLowerCase() === filterStatus.toLowerCase();
    });

  return (
    <div className="proto-table-wrapper">
      <table className="proto-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
            {showActions && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map(({ row, rowIndex }) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={columns[cellIndex]}>
                  {cell.isStatus ? <span className={statusBadgeClass(cell.value)}>{cell.value}</span> : cell.value}
                </td>
              ))}
              {showActions && (
                <td className="proto-table-actions">
                  <button
                    type="button"
                    className="proto-icon-btn proto-icon-btn-approve"
                    onClick={() => setOverrides((current) => ({ ...current, [rowIndex]: "Approved" }))}
                  >
                    <Check size={13} /> Approve
                  </button>
                  <button
                    type="button"
                    className="proto-icon-btn proto-icon-btn-reject"
                    onClick={() => setOverrides((current) => ({ ...current, [rowIndex]: "Rejected" }))}
                  >
                    <X size={13} /> Reject
                  </button>
                </td>
              )}
            </tr>
          ))}
          {visibleRows.length === 0 && (
            <tr>
              <td colSpan={columns.length + (showActions ? 1 : 0)} className="proto-table-empty">
                No matching records.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ScreenBody({ screen }: { screen: PrototypeScreen }) {
  const [submitted, setSubmitted] = useState(false);
  return (
    <div className="proto-screen-body">
      <h2 className="proto-page-title">{screen.name}</h2>
      {screen.description && <p className="proto-page-description">{screen.description}</p>}
      {submitted && <div className="proto-alert" role="status"><CheckCircle2 size={16} /> Submitted successfully.</div>}
      <form className="proto-ordered-components" onSubmit={(event) => { event.preventDefault(); setSubmitted(true); }}>
        {screen.components.map((component, index) => {
          const key = `${component.type}-${index}`;
          switch (component.type) {
            case "heading": return <h3 className="proto-subheading" key={key}>{component.text}</h3>;
            case "text": return <p className="proto-text" key={key}>{component.text}</p>;
            case "card": {
              const stat = parseStatCard(component.text || "");
              return <div className="proto-stat-card" key={key}>{stat ? <><span>{stat.label}</span><strong className="proto-stat-value">{stat.value}</strong></> : component.text}</div>;
            }
            case "field": return <label className="proto-field" key={key}>
              <span>{component.label}</span>
              {component.inputType === "select" || component.inputType === "dropdown" ?
                <select defaultValue=""><option value="" disabled>Select {component.label}</option>{(component.items || []).map(item => <option key={item}>{item}</option>)}</select> :
                component.inputType === "textarea" ? <textarea rows={3} /> :
                <input type={["text", "email", "date", "number", "password", "tel", "search", "time", "url"].includes(component.inputType || "") ? component.inputType : "text"} />}
            </label>;
            case "button": return <button key={key} type={component.variant === "primary" ? "submit" : "button"} className={`proto-button${component.variant === "primary" ? " primary" : ""}`}>{component.label || component.text}</button>;
            case "table": return <PrototypeTable key={key} component={component} filterStatus={null} showActions={false} />;
            case "list": return <ul className="proto-list" key={key}>{(component.items || []).map(item => <li key={item}>{item}</li>)}</ul>;
            case "nav": return <div className="proto-tabs" key={key}>{(component.items || []).map(item => <span className="proto-tab" key={item}>{item}</span>)}</div>;
            default: return null;
          }
        })}
      </form>
    </div>
  );
}

const THEME_DEFAULTS: Record<string, string> = {
  primary: "#2563eb", primaryText: "#ffffff", background: "#ffffff", surface: "#ffffff",
  text: "#172b4d", muted: "#505a5f", border: "#b1b4b6", headerBackground: "#172b4d",
  headerText: "#ffffff", focus: "#ffdd00", fontFamily: "Arial, sans-serif", fontSize: "16px",
  headingSize: "28px", spacing: "16px", radius: "4px", borderWidth: "1px", contentWidth: "1200px",
};

export function prototypeThemeStyle(theme?: Record<string, string>): CSSProperties {
  return Object.fromEntries(Object.entries(THEME_DEFAULTS).map(([key, fallback]) => {
    const candidate = theme?.[key];
    const valid = typeof candidate === "string" && (
      key === "fontFamily" ? /^[a-zA-Z0-9 ,"'-]{1,120}$/.test(candidate) :
      ["fontSize", "headingSize", "spacing", "radius", "borderWidth", "contentWidth"].includes(key) ? /^(?:0|[0-9]{1,4}(?:\.[0-9]{1,2})?(?:px|rem))$/.test(candidate) :
      /^#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(candidate)
    );
    return [`--proto-${key}`, valid ? candidate : fallback];
  })) as CSSProperties;
}

export default function AppPrototype({ spec }: { spec: AppPrototypeSpec }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [device, setDevice] = useState<Device>("desktop");
  const [fullscreen, setFullscreen] = useState(false);

  const screens = useMemo(() => spec.screens || [], [spec]);
  const activeScreen = screens[Math.min(activeIndex, screens.length - 1)];

  if (!screens.length) {
    return null;
  }

  const shell = (
    <div className={`proto-app-frame proto-themed proto-app-${device} proto-layout-${spec.layout || "sidebar"}`} style={{ ...prototypeThemeStyle(spec.theme), width: DEVICE_WIDTHS[device] }}>
      <div className="proto-app-header">
        <span className="proto-app-title">{spec.appName || "Generated Application"}</span>

      </div>

      <div className="proto-app-body">
        <nav className="proto-app-sidebar">
          {screens.map((screen, index) => (
            <button
              type="button"
              key={screen.name}
              className={index === activeIndex ? "proto-nav-item active" : "proto-nav-item"}
              onClick={() => setActiveIndex(index)}
              title={screen.name}
            >
              {screenIcon(screen.name)}
              <span>{screen.name}</span>
            </button>
          ))}
        </nav>

        <main className="proto-app-main">
          {activeScreen && <ScreenBody screen={activeScreen} key={activeScreen.name} />}
        </main>
      </div>
    </div>
  );

  return (
    <div className={fullscreen ? "app-prototype-shell fullscreen" : "app-prototype-shell"}>
      <div className="app-prototype-toolbar">
        <div className="app-prototype-device-toggle">
          <button type="button" className={device === "desktop" ? "active" : ""} onClick={() => setDevice("desktop")} title="Desktop">
            <Monitor size={14} />
          </button>
          <button type="button" className={device === "tablet" ? "active" : ""} onClick={() => setDevice("tablet")} title="Tablet">
            <Tablet size={14} />
          </button>
          <button type="button" className={device === "mobile" ? "active" : ""} onClick={() => setDevice("mobile")} title="Mobile">
            <Smartphone size={14} />
          </button>
        </div>
        <button type="button" className="app-prototype-fullscreen-btn" onClick={() => setFullscreen((current) => !current)}>
          {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          {fullscreen ? "Exit fullscreen" : "Fullscreen preview"}
        </button>
      </div>

      {spec.designNotes && spec.designNotes.length > 0 && <details className="prototype-design-notes"><summary>Applied design guidance</summary><ul>{spec.designNotes.map((note, index) => <li key={index}>{note}</li>)}</ul></details>}
      <div className="app-prototype-viewport">
        {shell}
      </div>
    </div>
  );
}
