import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import AppPrototype, { type AppPrototypeSpec } from "./AppPrototype";
import ArchitectureDiagram from "./ArchitectureDiagram";
import ErDiagram from "./ErDiagram";
import GeneratedCodeExplorer from "./GeneratedCodeExplorer";
import SubsectionAccordion from "./SubsectionAccordion";
import {
  BriefcaseBusiness,
  CircleCheck,
  CircleX,
  ClipboardCheck,
  ClipboardList,
  Cloud,
  Code2,
  Copy,
  Database,
  Download,
  Eye,
  FileText,
  GitBranch,
  Goal,
  KeySquare,
  Laptop,
  Layers3,
  Link2,
  ListChecks,
  Server,
  Star,
  ShieldCheck,
  Table2,
  Terminal,
  TestTube2,
  TriangleAlert,
  UsersRound,
} from "lucide-react";

interface SdlcSection {
  id: number;
  title: string;
  content: string;
}

interface SdlcOutputProps {
  content: string;
  onCorrection?: (sectionTitle: string, correction: string) => Promise<void>;
  onApprove?: (sectionTitle: string) => Promise<void>;
  onNext?: () => Promise<void> | void;
  diagramXml?: string;
  activeSectionId?: number;
  visibleSectionIds?: number[];
  // Optional human-friendly label for the active stage (e.g. "Interactive Prototype").
  // When the parsed sections do not include the numeric id expected by the
  // controller, SdlcOutput will fall back to matching this label against
  // section titles to find the correct section to open.
  activeSectionLabel?: string;
}

const SECTION_ICONS: Record<number, string> = {
  1: "◇",
  2: "◎",
  3: "▥",
  4: "✓",
  5: "▤",
  6: "⇄",
  7: "▦",
  8: "⌘",
  9: "⌁",
  10: "→",
  11: "⌗",
  12: "✓",
  13: "↔",
  14: "⚙",
  15: "◇",
  16: "🔒",
  17: "◉",
  18: "☑",
  19: "✓",
  20: "⚠",
};

function parseSections(content: string): SdlcSection[] {
  if (!content?.trim()) {
    return [];
  }

  const normalized = content
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\\n/g, "\n")
    .replace(/\\\*/g, "*");

  /*
   * Supports headings such as:
   *
   * ## 1. REQUIREMENT SUMMARY
   * ## 2. USER STORIES
   * ### 1. REQUIREMENT SUMMARY
   *
   * It also handles the equal-sign separator style
   * used by some LLM responses.
   */

  const headingRegex =
    /(?:^|\n)\s*#{1,4}\s*(\d+)\.\s*([^\n]+)\n?/g;

  const matches = [...normalized.matchAll(headingRegex)];

  if (matches.length === 0) {
    return [
      {
        id: 1,
        title: "Generated SDLC Analysis",
        content: normalized,
      },
    ];
  }
  const rawSections: SdlcSection[] = matches.map((match, index) => {
    const id = Number(match[1]);

    const title = match[2]
      .replace(/={2,}/g, "")
      .trim()
      .replace(/\*+/g, "");

    const start = (match.index ?? 0) + match[0].length;

    const end = index + 1 < matches.length ? matches[index + 1].index ?? normalized.length : normalized.length;

    let sectionContent = normalized.substring(start, end).trim();

    // Remove decorative separator lines.
    sectionContent = sectionContent.replace(/^\s*=+\s*$/gm, "").replace(/^\s*-{5,}\s*$/gm, "").trim();

    return { id, title, content: sectionContent };
  });

  // De-duplicate by normalized title, keeping the first occurrence.
  const seen = new Set<string>();
  const sections: SdlcSection[] = [];
  for (const sec of rawSections) {
    const norm = sec.title.toLowerCase().replace(/[^a-z0-9\s]/g, "").replace(/\s+/g, " ").trim();
    if (!seen.has(norm)) {
      seen.add(norm);
      sections.push(sec);
    }
  }

  return sections;
}

function parseSummaryRows(content: string) {
  const rows = content
    .split("\n")
    .filter((line) => line.trim().startsWith("|") && line.trim().endsWith("|"))
    .map((line) => line.split("|").slice(1, -1).map((cell) => cell.trim()))
    .filter((cells) => cells.length >= 2 && !/^:?-{2,}:?$/.test(cells[0]))
    .filter(([category]) => !/^category$/i.test(category))
    .map(([category, details]) => ({
      category: category.replace(/[*_]/g, "").trim(),
      details: details.replace(/<br\s*\/?>/gi, "\n").split(/[\n;]/)
        .map((item) => item.replace(/^\s*[-•]\s*/, "").trim())
        .filter(Boolean),
    }));

  return rows.reduce<{ category: string; details: string[] }[]>((summary, row) => {
    if (!row.category) {
      const previous = summary.at(-1);
      if (previous) {
        previous.details.push(...row.details);
      }
      return summary;
    }

    const existing = summary.find((item) => item.category.toLowerCase() === row.category.toLowerCase());
    if (existing) {
      existing.details.push(...row.details);
    } else {
      summary.push(row);
    }

    return summary;
  }, []);
}

function summaryIcon(category: string) {
  const label = category.toLowerCase();
  if (label.includes("business")) return <Goal />;
  if (label.includes("problem")) return <TriangleAlert />;
  if (label.includes("user")) return <UsersRound />;
  if (label.includes("out of scope")) return <CircleX />;
  if (label.includes("in scope")) return <CircleCheck />;
  return <Star />;
}

function normalizeMarkdownContent(content: string) {
  return content
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(
      /```(?:markdown|md|text)?\s*\n([\s\S]*?\|\s*Given\s*\|[\s\S]*?\|\s*When\s*\|[\s\S]*?\|\s*Then\s*\|[\s\S]*?)```/gi,
      "$1"
    );
}

function normalizeAcceptanceOrder(content: string) {
  return content.replace(
    /^\s*(?:[-*]\s*)?(.*?)\s*,?\s*\*{0,2}When\*{0,2}\s*:??\s*(.*?)\s*,?\s*\*{0,2}Then\*{0,2}\s*:??\s*(.*?)\s*\*{0,2}Given\*{0,2}\.?\s*$/gim,
    "**Given** $1, **When** $2, **Then** $3"
  );
}

function normalizeArchitectureSummary(content: string) {
  const layerLabels = [
    "Frontend Layer",
    "API Layer",
    "Application Services Layer",
    "Persistence Layer",
    "Security Layer",
    "External Systems",
  ];
  const labelPattern = layerLabels.join("|");

  // Already one bullet per layer on its own line — leave it untouched.
  if (new RegExp(`^\\s*-\\s*\\*{0,2}(?:${labelPattern})\\*{0,2}\\s*:`, "im").test(content)) {
    return content.trim();
  }

  const labelRegex = new RegExp(`\\*{0,2}(?:${labelPattern})\\*{0,2}`, "gi");

  return content
    // Force every layer label onto its own line, even when glued to the
    // end of the previous sentence.
    .replace(new RegExp(`\\s*(?=${labelRegex.source})`, "gi"), "\n")
    // Merge "**Label**" (optionally followed by a blank line and a
    // colon-led description) into a single bullet line.
    .replace(
      new RegExp(`\\*{0,2}(${labelPattern})\\*{0,2}\\s*\\n+\\s*:?\\s*`, "gi"),
      "\n- **$1**: "
    )
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function splitChecklistItem(rawLine: string) {
  const label = rawLine.replace(/^\s*-\s*\[[ xX]\]\s+/, "").trim();
  const dodIndex = label.search(/definition of done/i);

  if (dodIndex === -1) {
    return { task: label, dod: "" };
  }

  const task = label
    .slice(0, dodIndex)
    .replace(/[`*[\s]+$/, "")
    .trim();

  const dod = label
    .slice(dodIndex)
    .replace(/^definition of done\s*:?\s*/i, "")
    .replace(/[\]`*\s]+$/, "")
    .trim();

  return { task: task || label, dod };
}

function parseDocumentationItems(content: string) {
  const blocks = content
    .split(/(?=^#{2,4}\s+.+$)/m)
    .map((block) => block.trim())
    .filter((block) => block && !/^##\s*10\./i.test(block));

  return blocks
    .map((block) => {
      const cleanText = (value: string) => value.replace(/\*+/g, "").trim();
      const name = cleanText(block.match(/^#{2,4}\s+(.+)$/m)?.[1] || "");
      const audience = cleanText(block.match(/\*{0,2}Audience\*{0,2}\s*:?\s*([^\n]+)/i)?.[1] || "");
      const keyContentStart = block.search(/\*{0,2}Key Content\*{0,2}\s*:?/i);
      const keyContentBlock = keyContentStart >= 0
        ? block.slice(keyContentStart).replace(/^\*{0,2}Key Content\*{0,2}\s*:?/i, "")
        : "";
      const keyContent = [...keyContentBlock.matchAll(/^\s*[-*]\s*(.+)$/gm)]
        .map((match) => cleanText(match[1]))
        .filter((item) => item && !/^(?:[-–—]+|tbd|n\/?a|none|not applicable)$/i.test(item));

      return { name, audience, keyContent };
    })
    .filter((item) => item.name);
}

function parseSecurityControls(content: string) {
  const tableRows = content
    .split("\n")
    .filter((line) => line.trim().startsWith("|") && line.trim().endsWith("|"))
    .map((line) => line.split("|").slice(1, -1).map((cell) => cell.trim()))
    .filter((cells) => cells.length >= 2)
    .filter(([aspect]) => !/^(security aspect|aspect|[-:]+)$/i.test(aspect));

  const controls = tableRows.reduce<{ aspect: string; control: string }[]>((items, [rawAspect, rawControl]) => {
    const aspect = rawAspect.replace(/\*+/g, "").trim();
    const control = rawControl.replace(/\*+/g, "").trim();
    const previous = items.at(-1);

    if (!aspect && previous) {
      previous.control = `${previous.control} ${control}`.trim();
    } else if (aspect && control) {
      items.push({ aspect, control });
    }
    return items;
  }, []);

  if (controls.length) {
    return controls;
  }

  return content
    .split(/(?=^\s*(?:[-*]\s*)?\*{0,2}[A-Z][^\n:]{2,}\*{0,2}\s*[:|-])/m)
    .map((line) => line.replace(/^\s*[-*]\s*/, "").trim())
    .map((line) => {
      const match = line.match(/^\*{0,2}([^:|\n]+)\*{0,2}\s*[:|\-]\s*([\s\S]+)/);
      return match ? { aspect: match[1].replace(/\*+/g, "").trim(), control: match[2].replace(/\*+/g, " ").replace(/\s+/g, " ").trim() } : null;
    })
    .filter((item): item is { aspect: string; control: string } => Boolean(item?.aspect && item.control));
}

function securityIcon(aspect: string) {
  const label = aspect.toLowerCase();
  if (label.includes("auth")) return <KeySquare />;
  if (label.includes("validation") || label.includes("input")) return <ShieldCheck />;
  if (label.includes("inject")) return <Code2 />;
  if (label.includes("data") || label.includes("privacy")) return <Database />;
  if (label.includes("api") || label.includes("abuse")) return <Cloud />;
  return <ShieldCheck />;
}

function documentationPdfPath(name: string) {
  // Match by keyword rather than an exact string, since the model's exact
  // wording/spacing for a card title (e.g. "README / Setup Guide" vs.
  // "README/Setup Guide") varies between requests and an exact-match
  // lookup would silently request a PDF the backend never generates.
  const label = name.toLowerCase();

  if (label.includes("readme") || label.includes("setup guide")) return "docs/README.pdf";
  if (label.includes("user guide")) return "docs/user-guide.pdf";
  if (label.includes("api")) return "docs/api-documentation.pdf";
  if (label.includes("data model")) return "docs/data-model-documentation.pdf";
  if (label.includes("release notes")) return "docs/release-notes.pdf";

  return `docs/${label.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")}.pdf`;
}

function parseImplementationPhases(content: string) {
  const planStart = content.search(/(?:^|\n)#{2,4}\s*Implementation Plan/i);
  if (planStart < 0) return [];
  const plan = content.slice(planStart);
  const matches = [...plan.matchAll(/(?:^|\n)#{2,4}\s*Phase\s*(\d+)\s*[:.-]\s*([^\n]+)/gi)];

  const cleanText = (value: string) =>
    value
      .replace(/^\s*[-*]\s*/, "")
      .replace(/\*{1,2}/g, "")
      .trim();

  return matches.slice(0, 6).map((match, index) => {
    const end = index + 1 < matches.length ? matches[index + 1].index || plan.length : plan.length;
    const block = plan.slice((match.index || 0) + match[0].length, end);

    // Split the phase body on Tasks / Dependencies / Expected Outcome
    // labels, with or without a colon, so nothing bleeds into the wrong
    // field regardless of exact model formatting.
    const fieldMatches = [...block.matchAll(/(?:^|\n)\s*\*{0,2}(Tasks?|Activities|Dependencies|Expected Outcome|Outcome)\*{0,2}\s*:?\s*/gi)];
    const fields: { tasks: string; dependencies: string; outcome: string } = { tasks: "", dependencies: "", outcome: "" };

    fieldMatches.forEach((fieldMatch, fieldIndex) => {
      const label = fieldMatch[1].toLowerCase();
      const key = label.startsWith("task") || label.startsWith("activit")
        ? "tasks"
        : label.startsWith("depend")
          ? "dependencies"
          : "outcome";
      const fieldStart = (fieldMatch.index || 0) + fieldMatch[0].length;
      const fieldEnd = fieldIndex + 1 < fieldMatches.length ? fieldMatches[fieldIndex + 1].index || block.length : block.length;
      fields[key] = `${fields[key] ? `${fields[key]}\n` : ""}${block.slice(fieldStart, fieldEnd).trim()}`;
    });

    const tasks = fields.tasks
      .split(/\n|;/)
      .map((task) => cleanText(task).replace(/^Task\s*\d+\s*:?\s*/i, ""))
      .filter(Boolean)
      .slice(0, 4);
    const dependencies = cleanText(fields.dependencies.split("\n")[0] || "") || (index ? `Phase ${index}` : "None");
    const outcome = cleanText(fields.outcome.split("\n")[0] || "") || "Phase deliverables completed";

    return {
      number: Number(match[1]),
      title: cleanText(match[2]),
      tasks,
      dependencies,
      outcome,
    };
  });
}

function splitArchitectureContent(content: string) {
  const codeDesignStart = content.search(/(?:^|\n)#{2,4}\s*Code Design\b/i);
  const planStart = content.search(/(?:^|\n)#{2,4}\s*Implementation Plan\b/i);

  const summaryEnd = codeDesignStart >= 0 ? codeDesignStart : planStart >= 0 ? planStart : content.length;
  const summary = content
    .slice(0, summaryEnd)
    .replace(/^\s*#{2,4}\s*Architecture and Diagram Summary\s*\n?/i, "")
    .trim();

  let codeDesign = "";
  if (codeDesignStart >= 0) {
    const codeDesignEnd = planStart > codeDesignStart ? planStart : content.length;
    codeDesign = content
      .slice(codeDesignStart, codeDesignEnd)
      .replace(/^\s*#{2,4}\s*Code Design\s*\n?/i, "")
      .trim();
  }

  return { summary, codeDesign };
}

// Shared across every generic Markdown body: fenced code gets the dark
// "CODE" block, inline code (e.g. `com.example.api`) stays a plain span.
const markdownComponents: Components = {
  table({ children }) {
    return (
      <div className="markdown-table-wrapper">
        <table>{children}</table>
      </div>
    );
  },

  pre({ children }) {
    return <div className="code-block">{children}</div>;
  },

  code({ children, className }) {
    if (!className) {
      return <code>{children}</code>;
    }

    const language = className.replace("language-", "").toUpperCase() || "CODE";

    return (
      <div className="code-container">
        <div className="code-header">
          <span>{language}</span>
          <span>Generated</span>
        </div>

        <code>{children}</code>
      </div>
    );
  },

  blockquote({ children }) {
    return <blockquote className="markdown-quote">{children}</blockquote>;
  },
};

interface ErDiagramSpec {
  entities: { name: string; fields: string[] }[];
  relationships: { from: string; to: string; label?: string }[];
}

function parseErDiagramSpec(content: string): ErDiagramSpec | null {
  const block = content.match(/```(?:json)?\s*\n([\s\S]*?)```/i);
  const raw = (block ? block[1] : content).trim();

  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed?.entities) && parsed.entities.length > 0) {
      return {
        entities: parsed.entities,
        relationships: Array.isArray(parsed.relationships) ? parsed.relationships : [],
      };
    }
  } catch {
    return null;
  }

  return null;
}

function parsePrototypeSpec(content: string): AppPrototypeSpec | null {
  const block = content.match(/```(?:json)?\s*\n([\s\S]*?)```/i);
  const raw = (block ? block[1] : content).trim();

  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed?.screens) && parsed.screens.length > 0) {
      return {
        screens: parsed.screens.filter((screen: { name?: unknown; components?: unknown }) => screen && typeof screen.name === "string" && Array.isArray(screen.components)).map((screen: { name: string; description?: unknown; components: unknown[] }) => ({
          name: screen.name,
          description: typeof screen.description === "string" ? screen.description : undefined,
          components: screen.components.filter((component): component is Record<string, unknown> => !!component && typeof component === "object" && !Array.isArray(component)).map(component => ({
            type: typeof component.type === "string" ? component.type : "text",
            ...Object.fromEntries(["text", "label", "inputType", "variant"].filter(key => typeof component[key] === "string").map(key => [key, component[key]])),
            items: Array.isArray(component.items) ? component.items.filter((item): item is string => typeof item === "string") : undefined,
            columns: Array.isArray(component.columns) ? component.columns.filter((item): item is string => typeof item === "string") : undefined,
          })),
        })),
        appName: typeof parsed.appName === "string" ? parsed.appName : undefined,
        layout: ["sidebar", "topnav", "stacked"].includes(parsed.layout) ? parsed.layout : "sidebar",
        theme: parsed.theme && typeof parsed.theme === "object" && !Array.isArray(parsed.theme) ? parsed.theme : undefined,
        designNotes: Array.isArray(parsed.designNotes) ? parsed.designNotes.filter((note: unknown) => typeof note === "string") : [],
      };
    }
  } catch {
    return null;
  }

  return null;
}

function splitSubsections(content: string) {
  const matches = [...content.matchAll(/(?:^|\n)###\s+([^\n]+)\n?/g)];
  if (!matches.length) {
    return content.trim() ? [{ title: "", body: content.trim() }] : [];
  }

  return matches.map((match, index) => {
    const start = (match.index ?? 0) + match[0].length;
    const end = index + 1 < matches.length ? matches[index + 1].index ?? content.length : content.length;

    return {
      title: match[1].replace(/\*+/g, "").trim(),
      body: content.slice(start, end).trim(),
    };
  });
}

function subsectionIcon(title: string) {
  const label = title.toLowerCase();
  if (label.includes("endpoint")) return <Link2 />;
  if (label.includes("validation") || label.includes("error")) return <ShieldCheck />;
  if (label === "model") return <Table2 />;
  if (label.includes("er diagram")) return <GitBranch />;
  if (label.includes("schema")) return <Terminal />;
  if (label.includes("constraint")) return <KeySquare />;
  if (label.includes("overview")) return <ClipboardList />;
  if (label.includes("scenario")) return <ListChecks />;
  if (label.includes("edge case")) return <TriangleAlert />;
  if (label.includes("backend")) return <Server />;
  if (label.includes("frontend")) return <Laptop />;
  if (label.includes("database")) return <Database />;
  if (label.includes("deployment")) return <Cloud />;
  return <ClipboardList />;
}

function parseStory(story: string) {
  const body = normalizeAcceptanceOrder(
    story.replace(/^#{2,4}\s+(?:User\s+)?Story\s+\d+\s*:?[^\n]*\n?/i, "")
  );
  const criteriaStart = body.search(/\*{0,2}Acceptance criteria\*{0,2}/i);
  const storyDetails = criteriaStart >= 0 ? body.slice(0, criteriaStart) : body;
  const criteriaText = criteriaStart >= 0 ? body.slice(criteriaStart) : "";
  const cleanValue = (value: string) => value.replace(/\*{1,2}/g, "").trim();
  const readField = (label: string) =>
    cleanValue(storyDetails.match(new RegExp(`\\*{0,2}${label}\\*{0,2}\\s*:?\\s*([^\\n]+)`, "i"))?.[1] || "");
  const criteriaLines = criteriaText
    .split("\n")
    .map((line) => line
      .replace(/^\s*[-*]\s*/, "")
      .replace(/^\s*\|/, "")
      .replace(/\|\s*$/, "")
      .replace(/\*{1,2}/g, "")
      .trim())
    .filter(Boolean);
  // Some tables add a leading column (e.g. "Scenario"), so always read
  // the LAST three cells as Given/When/Then rather than the first three.
  const lastThreeCells = (cells: string[]) => cells.slice(-3).map((cell) => cleanValue(cell));
  const isHeaderRow = (cells: string[]) => {
    const [given, when, then] = lastThreeCells(cells).map((cell) => cell.toLowerCase());
    return given === "given" && when === "when" && then === "then";
  };
  const criteriaHeaderIndex = criteriaLines.findIndex((line) =>
    line.includes("|") && isHeaderRow(line.split("|"))
  );
  const tableCriteria = criteriaHeaderIndex >= 0
    ? criteriaLines.slice(criteriaHeaderIndex + 1)
      .filter((line) => line.includes("|") && !/^[-|\s]+$/.test(line))
      .map((line) => line.split("|"))
      .filter((cells) => !isHeaderRow(cells))
      .map((cells) => {
        const [given, when, then] = lastThreeCells(cells);
        return { given, when, then };
      })
      .filter((item) => item.given || item.when || item.then)
    : [];
  const inlineCriteria = criteriaLines
    .filter((line) => /given/i.test(line) && /when/i.test(line) && /then/i.test(line))
    .map((line) => {
      const cells = line.split("|").map((cell) => cell.trim());
      if (cells.length >= 3 && !isHeaderRow(cells)) {
        const [rawGiven, rawWhen, rawThen] = cells.slice(-3);
        const values = {
          given: cleanValue(rawGiven.replace(/^Given\s*:??\s*/i, "")),
          when: cleanValue(rawWhen.replace(/^When\s*:??\s*/i, "")),
          then: cleanValue(rawThen.replace(/^Then\s*:??\s*/i, "")),
        };
        return values.given || values.when || values.then ? values : null;
      }
      const match = line.match(/^given\s*:??\s*(.*?)\s*,?\s*when\s*:??\s*(.*?)\s*,?\s*then\s*:??\s*(.*)$/i);
      return match ? { given: cleanValue(match[1]), when: cleanValue(match[2]), then: cleanValue(match[3]) } : null;
    })
    .filter((item): item is { given: string; when: string; then: string } => Boolean(item));
  return {
    asA: readField("As a"),
    want: readField("I want"),
    soThat: readField("So that"),
    criteria: (tableCriteria.length ? tableCriteria : inlineCriteria).filter((item) => item.given || item.when || item.then),
  };
}

function Section({
  section,
  open,
  onToggle,
  onCorrection,
  onApprove,
  onNext,
  diagramXml,
  fullDocument,
}: {
  section: SdlcSection;
  open: boolean;
  onToggle: () => void;
  onCorrection?: (sectionTitle: string, correction: string) => Promise<void>;
  onApprove?: (sectionTitle: string) => Promise<void>;
  diagramXml?: string;
  onNext?: () => Promise<void> | void;
  fullDocument: string;
}) {
  const isArchitectureSection = section.title.toLowerCase().includes("architect");
  const markdownContent = normalizeMarkdownContent(
    isArchitectureSection
      ? normalizeArchitectureSummary(section.content)
      : section.content
  );
  const checklistItems = section.title.toLowerCase().includes("checklist")
    ? markdownContent
        .split(/(?=^\s*-\s*\[[ xX]\]\s+)/gm)
        .map((block) => block.replace(/\s+/g, " ").trim())
        .filter((block) => /^-\s*\[[ xX]\]/.test(block))
    : [];
  const [checkedItems, setCheckedItems] = useState<Set<number>>(new Set());
  const [correction, setCorrection] = useState("");
  const [submittingCorrection, setSubmittingCorrection] = useState(false);
  const [isApproved, setIsApproved] = useState(false);
  const [copied, setCopied] = useState(false);

  const copySection = async () => {
    try {
      await navigator.clipboard.writeText(`## ${section.id}. ${section.title}\n\n${section.content}`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  const stories = section.id === 2
    ? markdownContent
        .split(/(?=^#{2,4}\s+(?:User\s+)?Story\s+\d+)/gim)
        // Drop the leading heading-only chunk before the first "### Story N" -
        // its title text ("...AND ACCEPTANCE CRITERIA") otherwise gets
        // mistaken for a story with no acceptance criteria table.
        .filter((story) => /^#{2,4}\s+(?:User\s+)?Story\s+\d+/i.test(story.trim()))
    : [];
  const summaryRows = section.id === 1 ? parseSummaryRows(section.content) : [];
  const implementationPhases = isArchitectureSection
    ? parseImplementationPhases(section.content)
    : [];
  const archSections = isArchitectureSection
    ? splitArchitectureContent(markdownContent)
    : { summary: "", codeDesign: "" };
  const isGeneratedCodeSection = section.title.toLowerCase().includes("generated code");
  const isSecuritySection = section.title.toLowerCase().includes("security consideration");
  const securityControls = isSecuritySection ? parseSecurityControls(markdownContent) : [];
  const isPrototypeSection = /prototype/i.test(section.title);
  const prototypeSpec = isPrototypeSection ? parsePrototypeSpec(markdownContent) : null;
  const isDocumentationSection = /^documentation\b/i.test(section.title.trim());
  const documentationItems = isDocumentationSection
    ? parseDocumentationItems(markdownContent)
    : [];
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [jiraState, setJiraState] = useState<{ loading: boolean; error: string | null; success: string | null }>({
    loading: false,
    error: null,
    success: null,
  });
  const [confluenceState, setConfluenceState] = useState<{ loading: boolean; error: string | null; success: string | null }>({
    loading: false,
    error: null,
    success: null,
  });
  const [githubState, setGithubState] = useState<{ loading: boolean; error: string | null; success: string | null }>({
    loading: false,
    error: null,
    success: null,
  });

  const pushStoriesToJira = async () => {
    setJiraState({ loading: true, error: null, success: null });
    try {
      const response = await fetch("http://localhost:5000/api/integrations/jira/push-stories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_stories: section.content }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || "Could not push stories to Jira.");
      }
      setJiraState({ loading: false, error: null, success: `Created ${data.issues.length} Jira issue(s).` });
    } catch (err) {
      setJiraState({ loading: false, error: err instanceof Error ? err.message : "Could not push stories to Jira.", success: null });
    }
  };

  const publishDocsToConfluence = async () => {
    setConfluenceState({ loading: true, error: null, success: null });
    try {
      const response = await fetch("http://localhost:5000/api/integrations/confluence/publish-docs", {
        method: "POST",
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || "Could not publish documentation to Confluence.");
      }
      setConfluenceState({ loading: false, error: null, success: `Published ${data.pages.length} page(s) to Confluence.` });
    } catch (err) {
      setConfluenceState({ loading: false, error: err instanceof Error ? err.message : "Could not publish to Confluence.", success: null });
    }
  };

  const commitCodeToGithub = async () => {
    setGithubState({ loading: true, error: null, success: null });
    try {
      const response = await fetch("http://localhost:5000/api/integrations/github/commit-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "Add generated application code" }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || "Could not commit code to GitHub.");
      }
      setGithubState({ loading: false, error: null, success: `Committed ${data.commit.file_count} file(s) to GitHub.` });
    } catch (err) {
      setGithubState({ loading: false, error: err instanceof Error ? err.message : "Could not commit code to GitHub.", success: null });
    }
  };

  const openDocumentationPdf = async (name: string, download = false) => {
    setPdfError(null);
    const path = documentationPdfPath(name);
    const documentWindow = download ? null : window.open("", "_blank");

    try {
      const response = await fetch("http://localhost:5000/api/documentation/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, plan: markdownContent, fullDocument, force: true }),
      });
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Could not create the documentation PDF.");
      }

      const fileUrl = `http://localhost:5000/api/documentation/pdf?path=${encodeURIComponent(path)}${download ? "&download=true" : ""}`;

      if (download) {
        // Downloads are triggered via a real anchor click instead of a
        // pre-opened window, since some browsers ignore a same-tab
        // location change on a background window for downloads.
        const link = document.createElement("a");
        link.href = fileUrl;
        // Hint to the browser to download with the original filename and
        // open in a new tab to avoid navigation side-effects.
        link.download = path.split("/").pop() || "document.pdf";
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        link.remove();
      } else if (documentWindow) {
        documentWindow.location.replace(fileUrl);
      } else {
        // The preview popup was blocked; fall back to a same-tab open so
        // the click still results in a visible action.
        window.open(fileUrl, "_blank", "noopener");
      }
    } catch (err) {
      documentWindow?.close();
      setPdfError(err instanceof Error ? err.message : "Could not open this document.");
    }
  };
  const isCategorizedSection = !isArchitectureSection && !isGeneratedCodeSection && (
    section.title.toLowerCase().includes("api design") ||
    section.title.toLowerCase().includes("data model") ||
    section.title.toLowerCase().includes("test strategy")
  );
  const isTestStrategySection = section.title.toLowerCase().includes("test strategy");
  const isInfrastructureSection = /infrastructure|terraform/i.test(section.title);
  const [testView, setTestView] = useState<"cases" | "code">("cases");
  const categorizedSubsections = isCategorizedSection
    ? splitSubsections(markdownContent).filter((sub) => !isTestStrategySection || !/generated test code/i.test(sub.title))
    : [];
  const infrastructureSubsections = isInfrastructureSection ? splitSubsections(markdownContent) : [];

  return (
    <div
      className={`sdlc-section ${
        open ? "open" : ""
      }`}
    >
      <button
        className="sdlc-section-header"
        onClick={onToggle}
      >
        <div className="section-number">
          {String(section.id).padStart(2, "0")}
        </div>

        <div className="section-icon">
          {SECTION_ICONS[section.id] || "◇"}
        </div>

        <div className="section-heading">
          <span className="section-title">
            {section.title}
          </span>

          <span className="section-meta">
            SDLC SECTION {section.id}
          </span>
        </div>

        {isApproved && (
          <span className="section-status">
            <span aria-hidden="true">✓</span>
            Approved
          </span>
        )}

        <div
          className={`section-chevron ${
            open ? "expanded" : ""
          }`}
        >
          ›
        </div>
      </button>

      {open && (
        <div className="sdlc-section-body">
          <div className="section-copy-row">
            <button type="button" className="section-copy-btn" onClick={copySection}>
              <Copy />
              {copied ? "Copied" : "Copy section"}
            </button>
          </div>
          {summaryRows.length > 0 ? (
            <div className="summary-layout">
              <div className="summary-main">
                {summaryRows.slice(0, 4).map((row) => (
                  <div className="summary-item" key={row.category}>
                    <div className="summary-item-icon">{summaryIcon(row.category)}</div>
                    <div>
                      <strong>{row.category}</strong>
                      <p>{row.details.join(" ")}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="summary-aside">

                <div className="summary-panel scope-panel">
                  <h3>Scope</h3>
                  {summaryRows.filter((row) => /scope/i.test(row.category)).map((row) => (
                    <div className={/out/i.test(row.category) ? "scope-group out" : "scope-group"} key={row.category}>
                      <strong>{/out/i.test(row.category) ? <CircleX /> : <CircleCheck />} {row.category}</strong>
                      <ul>{row.details.map((item) => <li key={item}>{item}</li>)}</ul>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : stories.length > 0 ? (
            <div className="story-list">
              <div className="integration-action-row">
                <button type="button" className="integration-action-btn" disabled={jiraState.loading} onClick={pushStoriesToJira}>
                  {jiraState.loading ? "Pushing to Jira..." : "Push to Jira"}
                </button>
                {jiraState.error && <span className="integration-action-error">{jiraState.error}</span>}
                {jiraState.success && <span className="integration-action-success">{jiraState.success}</span>}
              </div>
              {stories.map((story, index) => {
                const title = story.match(/^#{2,4}\s+((?:User\s+)?Story\s+\d+[^\n]*)/i)?.[1] || `User story ${index + 1}`;
                const parsedStory = parseStory(story);

                return (
                  <details className="story-card" key={title} open={index === 0}>
                    <summary>
                      <span className="story-number">0{index + 1}</span>
                      <span>{title.replace(/^(?:User\s+)?Story\s+\d+:?\s*/i, "") || title}</span>
                      <span className="story-toggle">+</span>
                    </summary>
                    <div className="story-card-body">
                      <div className="story-details-panel">
                        <div><UsersRound /><strong>As a:</strong><span>{parsedStory.asA || "User"}</span></div>
                        <div><Star /><strong>I want:</strong><span>{parsedStory.want || "Complete this action"}</span></div>
                        <div><Goal /><strong>So that:</strong><span>{parsedStory.soThat || "The business goal is achieved"}</span></div>
                      </div>

                      <div className="acceptance-heading">
                        <ClipboardList />
                        <strong>Acceptance Criteria</strong>
                      </div>

                      {parsedStory.criteria.length > 0 ? (
                        <div className="acceptance-table">
                          <div className="acceptance-table-header"><span>Given</span><span>When</span><span>Then</span></div>
                          {parsedStory.criteria.map((criterion, criterionIndex) => (
                            <div className="acceptance-table-row" key={`${criterion.given}-${criterionIndex}`}>
                              <span><b>{String(criterionIndex + 1).padStart(2, "0")}</b>{criterion.given}</span>
                              <span>{criterion.when}</span>
                              <span>{criterion.then}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{story.replace(/^#{2,4}\s+(?:User\s+)?Story\s+\d+\s*:?[^\n]*\n?/i, "")}</ReactMarkdown>
                      )}
                    </div>
                  </details>
                );
              })}
            </div>
          ) : checklistItems.length > 0 ? (
            <div className="developer-checklist">
              <div className="checklist-progress">
                <span>{checkedItems.size} of {checklistItems.length} complete</span>
                <div><span style={{ width: `${(checkedItems.size / checklistItems.length) * 100}%` }} /></div>
              </div>
              <div className="checklist-table">
                <div className="checklist-table-header">
                  <span>#</span>
                  <span>Task</span>
                  <span>Definition of Done</span>
                  <span>Done</span>
                </div>
                {checklistItems.map((item, index) => {
                  const { task, dod } = splitChecklistItem(item);

                  return (
                    <div className={checkedItems.has(index) ? "checklist-table-row checked" : "checklist-table-row"} key={item}>
                      <span><b>{String(index + 1).padStart(2, "0")}</b></span>
                      <span>{task}</span>
                      <span>{dod || "\u2014"}</span>
                      <span>
                        <input
                          type="checkbox"
                          checked={checkedItems.has(index)}
                          onChange={() => setCheckedItems((current) => {
                            const next = new Set(current);
                            if (next.has(index)) next.delete(index); else next.add(index);
                            return next;
                          })}
                        />
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : isArchitectureSection ? (
            <div className="architecture-subsections">
              <SubsectionAccordion icon={<Layers3 />} title="Architecture Diagram">
                {diagramXml ? (
                  <ArchitectureDiagram xml={diagramXml} />
                ) : (
                  <p className="arch-subsection-empty">Diagram not available yet.</p>
                )}
              </SubsectionAccordion>

              <SubsectionAccordion icon={<ClipboardList />} title="Architecture Summary">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {archSections.summary}
                </ReactMarkdown>
              </SubsectionAccordion>

              {archSections.codeDesign && (
                <SubsectionAccordion icon={<Code2 />} title="Code Design">
                  {(() => {
                    const subsections = splitSubsections(archSections.codeDesign);
                    if (subsections.length > 1) {
                      return subsections.map((sub) => (
                        <div className="code-design-subsection" key={sub.title || sub.body.substring(0, 40)}>
                          {sub.title && <h4 className="code-design-subsection-title">{sub.title}</h4>}
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                            {sub.body}
                          </ReactMarkdown>
                        </div>
                      ));
                    }

                    return (
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                        {archSections.codeDesign}
                      </ReactMarkdown>
                    );
                  })()}
                </SubsectionAccordion>
              )}

              {implementationPhases.length > 0 && (
                <SubsectionAccordion icon={<ListChecks />} title="Implementation Plan">
                  <div className="plan-metrics">
                    <div><Layers3 /><span>Total Phases</span><strong>{implementationPhases.length}</strong></div>
                    <div><ListChecks /><span>Total Tasks</span><strong>{implementationPhases.reduce((total, phase) => total + phase.tasks.length, 0)}</strong></div>
                    <div><Goal /><span>Goal</span><strong>Successful Delivery</strong></div>
                  </div>
                  <div className="phase-timeline">
                    {implementationPhases.map((phase) => (
                      <div className="phase-item" key={phase.number}>
                        <div className="phase-marker">{phaseIcon(phase.number)}<span>{String(phase.number).padStart(2, "0")}</span></div>
                        <div className="phase-content">
                          <h3>Phase {phase.number}: {phase.title}</h3>
                          <div className="phase-columns">
                            <div><strong>TASKS</strong><ul>{phase.tasks.map((task) => <li key={task}><CircleCheck />{task}</li>)}</ul></div>
                            <div><strong>DEPENDENCIES</strong><p>{phase.dependencies}</p></div>
                            <div><strong>EXPECTED OUTCOME</strong><p className="phase-outcome">{phase.outcome}</p></div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </SubsectionAccordion>
              )}
            </div>
          ) : isDocumentationSection && documentationItems.length > 0 ? (
            <div className="documentation-section">
              <div className="integration-action-row">
                <button type="button" className="integration-action-btn" disabled={confluenceState.loading} onClick={publishDocsToConfluence}>
                  {confluenceState.loading ? "Publishing to Confluence..." : "Publish to Confluence"}
                </button>
                {confluenceState.error && <span className="integration-action-error">{confluenceState.error}</span>}
                {confluenceState.success && <span className="integration-action-success">{confluenceState.success}</span>}
              </div>
              {pdfError && (
                <div className="documentation-pdf-error">{pdfError}</div>
              )}
              <div className="documentation-grid">
                {documentationItems.map((item) => (
                  <div className="documentation-card" key={item.name}>
                    <div className="documentation-card-header">
                      <FileText />
                      <span>{item.name}</span>
                    </div>
                    {item.audience && (
                      <div className="documentation-card-audience">
                        <UsersRound />
                        <span>{item.audience}</span>
                      </div>
                    )}
                    {item.keyContent.length > 0 && (
                      <ul className="documentation-card-content">
                        {item.keyContent.map((point) => (
                          <li key={point}>{point}</li>
                        ))}
                      </ul>
                    )}
                    <div className="documentation-card-actions">
                      <button
                        type="button"
                        onClick={() => openDocumentationPdf(item.name)}
                      >
                        <Eye />
                        Preview PDF
                      </button>
                      <button
                        type="button"
                        onClick={() => openDocumentationPdf(item.name, true)}
                      >
                        <Download />
                        Download PDF
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : isSecuritySection && securityControls.length > 0 ? (
            <div className="security-controls">
              <div className="security-controls-heading">
                <span>Security Aspect</span>
                <span>Implementation Control</span>
              </div>
              <div className="security-controls-grid">
                {securityControls.map((item) => (
                  <article className="security-control-card" key={item.aspect}>
                    <div className="security-control-icon">{securityIcon(item.aspect)}</div>
                    <div>
                      <strong>{item.aspect}</strong>
                      <p>{item.control}</p>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : isPrototypeSection && prototypeSpec ? (
            <div className="prototype-section">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {markdownContent.split(/(?:^|\n)###\s+UI Specification\b/i)[0]}
              </ReactMarkdown>
              <AppPrototype spec={prototypeSpec} />
            </div>
          ) : isGeneratedCodeSection ? (
            <div className="generated-code-section">
              <div className="integration-action-row">
                <button type="button" className="integration-action-btn" disabled={githubState.loading} onClick={commitCodeToGithub}>
                  {githubState.loading ? "Committing to GitHub..." : "Commit to GitHub"}
                </button>
                {githubState.error && <span className="integration-action-error">{githubState.error}</span>}
                {githubState.success && <span className="integration-action-success">{githubState.success}</span>}
              </div>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {markdownContent}
              </ReactMarkdown>
              <GeneratedCodeExplorer />
            </div>
          ) : isInfrastructureSection ? (
            <div className="architecture-subsections">
              {infrastructureSubsections
                .filter((sub) => !/generated infrastructure files/i.test(sub.title))
                .map((sub) => (
                  <SubsectionAccordion icon={subsectionIcon(sub.title)} title={sub.title || section.title} key={sub.title || section.title}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                      {sub.body}
                    </ReactMarkdown>
                  </SubsectionAccordion>
                ))}
              <SubsectionAccordion icon={<Terminal />} title="Generated Terraform Files">
                <GeneratedCodeExplorer prefix="infrastructure" rootLabel="infrastructure" />
              </SubsectionAccordion>
            </div>
          ) : isCategorizedSection ? (
            <div className="architecture-subsections">
              {isTestStrategySection && (
                <div className="proto-tabs test-view-tabs">
                  <button
                    type="button"
                    className={testView === "cases" ? "proto-tab active" : "proto-tab"}
                    onClick={() => setTestView("cases")}
                  >
                    Test Cases
                  </button>
                  <button
                    type="button"
                    className={testView === "code" ? "proto-tab active" : "proto-tab"}
                    onClick={() => setTestView("code")}
                  >
                    Test Code
                  </button>
                </div>
              )}

              {(!isTestStrategySection || testView === "cases") && categorizedSubsections.map((sub) => {
                const erSpec = /er diagram/i.test(sub.title) ? parseErDiagramSpec(sub.body) : null;

                return (
                  <SubsectionAccordion icon={subsectionIcon(sub.title)} title={sub.title || section.title} key={sub.title || section.title}>
                    {erSpec ? (
                      <ErDiagram spec={erSpec} />
                    ) : (
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                        {sub.body}
                      </ReactMarkdown>
                    )}
                  </SubsectionAccordion>
                );
              })}

              {isTestStrategySection && testView === "code" && (
                <>
                  <SubsectionAccordion icon={<TestTube2 />} title="Unit Tests (JUnit)">
                    <GeneratedCodeExplorer prefix="backend/src/test" rootLabel="backend/src/test" />
                  </SubsectionAccordion>
                  <SubsectionAccordion icon={<Code2 />} title="Selenium End-to-End Tests">
                    <GeneratedCodeExplorer prefix="selenium-tests" rootLabel="selenium-tests" />
                  </SubsectionAccordion>
                </>
              )}
            </div>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {markdownContent}
            </ReactMarkdown>
          )}

          {onCorrection && !onNext && !isApproved && (
            <div className="section-footer">
              <div className="section-correction">
                <div className="review-illustration" aria-hidden="true">
                  <ClipboardCheck />
                  <span><ShieldCheck /></span>
                </div>
                <div className="section-correction-heading">
                  <strong>Review this step before continuing</strong>
                  <span>Please review the generated section and approve it to proceed, or provide corrections if needed.</span>
                </div>
                <div className="section-button-group">
                  <button
                    type="button"
                    className="section-action section-action-primary"
                    onClick={async () => {
                      await onApprove?.(section.title);
                      setIsApproved(true);
                    }}
                  >
                    Approve
                  </button>
                  <div className="section-correction-form">
                    <input
                      value={correction}
                      onChange={(event) => setCorrection(event.target.value)}
                      placeholder={`Correction for ${section.title}`}
                      aria-label={`Correction for ${section.title}`}
                      disabled={submittingCorrection}
                    />
                    <button
                      type="button"
                      className="section-action"
                      disabled={!correction.trim() || submittingCorrection}
                      onClick={async () => {
                        setSubmittingCorrection(true);
                        try {
                          await onCorrection(section.title, correction.trim());
                          setCorrection("");
                          setIsApproved(false);
                        } finally {
                          setSubmittingCorrection(false);
                        }
                      }}
                    >
                      {submittingCorrection ? "Rerunning..." : "Correct & rerun"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {onNext && (
            <div className="section-footer">
              <div className="section-button-group section-button-group-simple">
                <button
                  type="button"
                  className="section-action section-action-primary"
                  onClick={onNext}
                >
                  {section.title.toLowerCase().includes("documentation") ? "Show all sections" : "Next"}
                </button>
              </div>
            </div>
          )}

          {isApproved && (
            <div className="section-approved-banner">
              <span>✓ Section approved</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SdlcOutput({
  content,
  onCorrection,
  onApprove,
  onNext,
  diagramXml,
  activeSectionId,
  activeSectionLabel,
  visibleSectionIds,
}: SdlcOutputProps) {
  const sections = useMemo(
    () => {
      const parsed = parseSections(content);
      if (!visibleSectionIds?.length) {
        return parsed;
      }
      return parsed.filter((section) => visibleSectionIds.includes(section.id));
    },
    [content, visibleSectionIds]
  );
  const [openSectionIds, setOpenSectionIds] = useState<Set<number>>(new Set());
  const [focusSectionId, setFocusSectionId] = useState<number | null>(null);
  const activeSectionRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // A sentinel of 0 (used for the final "assemble" stage) means there is
    // no section to focus - close everything and return to the top of the
    // results instead of leaving the last-approved section open.
    if (activeSectionId === 0) {
      setOpenSectionIds(new Set());
      setFocusSectionId(null);
      requestAnimationFrame(() => {
        topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      return;
    }
    // Prefer numeric id match, but fall back to matching the section title
    // when the model's generated headings don't contain the expected id.
    const byId = sections.find((section) => section.id === activeSectionId);
    const normalizedLabel = activeSectionLabel?.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    const byLabel = normalizedLabel
      ? sections.find((section) => {
        const normalizedTitle = section.title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
        if (normalizedTitle.includes(normalizedLabel) || normalizedLabel.includes(normalizedTitle)) {
          return true;
        }

        // Generated headings occasionally shorten the canonical stage label.
        const aliases = [
          normalizedLabel.includes("prototype") ? "prototype" : "",
          normalizedLabel.includes("user stor") ? "user stor" : "",
          normalizedLabel.includes("api design") ? "api" : "",
          normalizedLabel.includes("data model") ? "data model" : "",
        ].filter(Boolean);
        return aliases.some((alias) => normalizedTitle.includes(alias));
      })
      : undefined;
    const targetSection = byId || byLabel || sections.at(-1);
    setOpenSectionIds(targetSection ? new Set([targetSection.id]) : new Set());
    setFocusSectionId(targetSection?.id ?? null);
  }, [activeSectionId, content, sections]);

  useEffect(() => {
    if (focusSectionId == null) {
      return;
    }

    // Tall sections (checklist table, documentation cards) can still be
    // mid-layout after one animation frame, so wait for a second frame
    // before measuring, then re-affirm the scroll once more shortly after
    // in case late layout shifts (e.g. wrapped text) moved the target.
    let innerFrame = 0;
    const outerFrame = requestAnimationFrame(() => {
      innerFrame = requestAnimationFrame(() => {
        activeSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        activeSectionRef.current?.focus({ preventScroll: true });
      });
    });

    const settleTimeout = window.setTimeout(() => {
      activeSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 180);

    return () => {
      cancelAnimationFrame(outerFrame);
      cancelAnimationFrame(innerFrame);
      window.clearTimeout(settleTimeout);
    };
  }, [focusSectionId]);

  if (!sections.length) {
    return (
      <div className="sdlc-empty-result">
        No analysis generated yet.
      </div>
    );
  }

  return (
    <div className="sdlc-output">
      <div ref={topRef} />
      <div className="sdlc-sections">
        {sections.map((section, index) => {
          const sectionOnApprove = section.id === activeSectionId && onApprove ? onApprove : undefined;
          const sectionOnCorrection = section.id === activeSectionId && onCorrection ? onCorrection : undefined;

          return (
            <div
              key={`${section.id}-${content.length}`}
              ref={section.id === focusSectionId ? activeSectionRef : undefined}
              tabIndex={-1}
            >
              <Section
                section={section}
                open={openSectionIds.has(section.id)}
                onToggle={() => setOpenSectionIds((current) => {
                  const next = new Set(current);
                  if (next.has(section.id)) {
                    next.delete(section.id);
                  } else {
                    next.add(section.id);
                  }
                  return next;
                })}
                onCorrection={sectionOnCorrection}
                onApprove={sectionOnApprove}
                diagramXml={diagramXml}
                onNext={(() => {
                  const isDocumentation = section.title.toLowerCase().includes("documentation");
                  if (section.id === activeSectionId && onNext) {
                    return isDocumentation ? () => {
                      setOpenSectionIds(new Set());
                      setFocusSectionId(null);
                      requestAnimationFrame(() => topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
                    } : onNext;
                  }

                  if (!sectionOnApprove && sections[index + 1]) {
                    return isDocumentation ? () => {
                      setOpenSectionIds(new Set());
                      setFocusSectionId(null);
                      requestAnimationFrame(() => topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
                    } : () => {
                      const nextSection = sections[index + 1];
                      setOpenSectionIds(new Set([nextSection.id]));
                      setFocusSectionId(nextSection.id);
                    };
                  }

                  return undefined;
                })()} 
                fullDocument={content}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function phaseIcon(number: number) {
  const icons = [BriefcaseBusiness, Database, Layers3, Code2, Code2, TestTube2];
  const Icon = icons[Math.min(number - 1, icons.length - 1)];
  return <Icon />;
}
