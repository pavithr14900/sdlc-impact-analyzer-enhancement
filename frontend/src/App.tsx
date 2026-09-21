import SdlcOutput from "./sdlcOutput";
import ChangeImpactHome from "./ChangeImpactHome";
import ChangeImpactResults from "./ChangeImpactResults";
import { useEffect, useRef, useState, type ReactElement } from "react";
import {
  ArrowRight,
  Bell,
  ArrowRightLeft,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Trash2,
  Code2,
  Download,
  Eye,
  FileCog,
  History,
  Lightbulb,
  Layers3,
  Link2,
  Cloud,
  Palette,
  Settings,
  ShieldCheck,
  TestTube2,
  Upload,
  UserRound,
  UsersRound,
  WalletCards,
  X,
  FileText,
  Database,
  Check,
} from "lucide-react";
import "./App.css";

const API_BASE_URL = "http://localhost:5000/api";

const STAGE_SECTION_IDS: Record<string, number> = {
  requirement: 1,
  user_stories: 2,
  prototype: 3,
  architecture: 4,
  api_design: 5,
  data_model: 6,
  generate_code: 7,
  test_strategy: 8,
  infrastructure: 9,
  security: 10,
  checklist: 11,
  documentation: 12,
  // 0 is a sentinel meaning "no section" - once documentation is approved
  // and final assembly runs, close every section and scroll back to top.
  assemble: 0,
};

// Display order for the sidebar progress list; stageIndex matches
// `interactiveStages` (each row is its own independent stage).
const REQUIREMENT_FLOW_STEPS = [
  { label: "Requirement Summary", stageIndex: 0 },
  { label: "User Stories", stageIndex: 1 },
  { label: "Interactive Prototype", stageIndex: 2 },
  { label: "Architecture Design", stageIndex: 3 },
  { label: "API Design", stageIndex: 4 },
  { label: "Data Model", stageIndex: 5 },
  { label: "Generated Code", stageIndex: 6 },
  { label: "Test Strategy", stageIndex: 7 },
  { label: "Infrastructure", stageIndex: 8 },
  { label: "Security Considerations", stageIndex: 9 },
  { label: "Developer Checklist", stageIndex: 10 },
  { label: "Documentation", stageIndex: 11 },
];

type Capability =
  | "requirement"
  | "change-impact";

interface AgentStage {
  name: string;
  role?: string;
  status?: string;
}

interface ApiResponse {
  success: boolean;
  result?: string;
  error?: string;
  file?: string;
  diagram?: string;
  diagramFile?: string;
  stages?: AgentStage[];
    // Optional structured change impact data from backend
    changeImpact?: {
      affected_repositories?: number;
      affected_files?: number;
      api_contracts?: number;
      overall_risk?: string;
      impact_summary?: string[];
      affected_files_list?: { file: string; repo: string; impact: string; recommended: string }[];
      repository_dependencies?: any;
    };
}

interface RequirementHistoryItem {
  id: string;
  requirement: string;
  result: string;
  diagramXml: string;
  createdAt: string;
}

const REQUIREMENT_HISTORY_KEY = "buildpilot-requirement-history";
const MAX_HISTORY_ITEMS = 12;

function App() {
  const [activeCapability, setActiveCapability] =
    useState<Capability>("requirement");

  const [requirement, setRequirement] = useState("");
  const [changeRequest, setChangeRequest] = useState("");

  const [result, setResult] = useState("");
  const [diagramXml, setDiagramXml] = useState("");
  const [agents, setAgents] = useState<AgentStage[]>([]);
  const [error, setError] = useState("");
  const [changeImpactData, setChangeImpactData] = useState<any>(null);

  const [loading, setLoading] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);
  const [models, setModels] = useState<{ id: string; label: string }[]>([]);
  const [activeModelId, setActiveModelId] = useState<string>("");
  const outputPanelRef = useRef<HTMLElement>(null);
  const [interactiveStageIndex, setInteractiveStageIndex] = useState(0);
  const [activeStagesSequence, setActiveStagesSequence] = useState<string[]>([]);
  const [interactiveContext, setInteractiveContext] = useState<Record<string, unknown>>({});
  const [approvedSections, setApprovedSections] = useState<string[]>([]);
  const [transitionNote, setTransitionNote] = useState<string | null>(null);
  
  const [historyItems, setHistoryItems] = useState<RequirementHistoryItem[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [copiedAll, setCopiedAll] = useState(false);
  
  const [buildSettingsOpen, setBuildSettingsOpen] = useState(false);
  const [sectionsModalOpen, setSectionsModalOpen] = useState(false);
  const [sectionsSelected, setSectionsSelected] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    // derive default selections from STAGE_SECTION_IDS so it doesn't depend on
    // interactiveStages initialization order
    Object.keys(STAGE_SECTION_IDS).forEach((s) => {
      if (s === "assemble") return;
      initial[s] = s !== "infrastructure" && s !== "documentation";
    });
    return initial;
  });
  const [designSystemUrl, setDesignSystemUrl] = useState("");
  const [engineeringStandardsUrl, setEngineeringStandardsUrl] = useState("");
  const [engineeringFileError, setEngineeringFileError] = useState("");
  const [designUploading, setDesignUploading] = useState(false);
  const [engineeringFiles, setEngineeringFiles] = useState<File[]>([]);
  const [designFiles, setDesignFiles] = useState<File[]>([]);
  const [buildSettingsProcessing, setBuildSettingsProcessing] = useState(false);
  const [buildSettingsSuccess, setBuildSettingsSuccess] = useState<string | null>(null);
  const [buildSettingsError, setBuildSettingsError] = useState<string | null>(null);
  const [engineeringSummary, setEngineeringSummary] = useState("");
  const [designSummary, setDesignSummary] = useState("");
  const [sectionsOpen, setSectionsOpen] = useState<Record<string, boolean>>({
    engineering: false,
    design: true,
    technology: false,
    security: false,
    testing: false,
    deployment: false,
  });
  const [notifOpen, setNotifOpen] = useState(false);
  const lastSavedHistoryId = useRef<string | null>(null);
  const interactiveStages = [
    "requirement",
    "user_stories",
    "prototype",
    "architecture",
    "api_design",
    "data_model",
    "generate_code",
    "test_strategy",
    "infrastructure",
    "security",
    "checklist",
    "documentation",
    "assemble",
  ];
  const stageLabels: Record<string, string> = {
    requirement: "Requirement Summary",
    user_stories: "User Stories & Acceptance Criteria",
    prototype: "Interactive Application Prototype",
    architecture: "Architecture Design",
    api_design: "API Design",
    data_model: "Data Model",
    generate_code: "Generated Code",
    test_strategy: "Test Strategy",
    infrastructure: "Terraform / Infrastructure as Code",
    security: "Security Considerations",
    checklist: "Developer Checklist",
    documentation: "Documentation",
    assemble: "Final Assembly",
  };

  // Initialize the active stages sequence to the full interactiveStages on mount
  useEffect(() => {
    setActiveStagesSequence(interactiveStages.slice());
  }, []);

  const stageIcons: Record<string, ReactElement> = {
    requirement: <FileText />,
    user_stories: <UsersRound />,
    prototype: <Palette />,
    architecture: <Layers3 />,
    api_design: <Link2 />,
    data_model: <Database />,
    generate_code: <Code2 />,
    test_strategy: <TestTube2 />,
    infrastructure: <Cloud />,
    security: <ShieldCheck />,
    checklist: <ClipboardList />,
    documentation: <FileCog />,
  };

  useEffect(() => {
    try {
      const saved = localStorage.getItem(REQUIREMENT_HISTORY_KEY);
      setHistoryItems(saved ? JSON.parse(saved) : []);
    } catch {
      setHistoryItems([]);
    }
  }, []);

  useEffect(() => {
    if (
      activeCapability !== "requirement" ||
      interactiveStageIndex < activeStagesSequence.length ||
      !requirement.trim() ||
      !result.trim() ||
      lastSavedHistoryId.current
    ) {
      return;
    }

    const item: RequirementHistoryItem = {
      id: crypto.randomUUID(),
      requirement: requirement.trim(),
      result,
      diagramXml,
      createdAt: new Date().toISOString(),
    };
    const next = [item, ...historyItems].slice(0, MAX_HISTORY_ITEMS);
    localStorage.setItem(REQUIREMENT_HISTORY_KEY, JSON.stringify(next));
    lastSavedHistoryId.current = item.id;
    setHistoryItems(next);
  }, [activeCapability, diagramXml, historyItems, interactiveStageIndex, requirement, result]);

  const examplePrompts = [
    "Expense Management",
    "Employee Leave",
    "Customer Management",
  ];

  useEffect(() => {
    checkBackendHealth();
    // fetch available models and current selection
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/models`);
        if (res.ok) {
          const data = await res.json();
          setModels(data.models || []);
        }
        const cur = await fetch(`${API_BASE_URL}/model`);
        if (cur.ok) {
          const d = await cur.json();
          setActiveModelId(d.model_id || "");
        }
      } catch (e) {
        // ignore
      }
    })();
    const interval = setInterval(checkBackendHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  

  useEffect(() => {
    if (!result) {
      return;
    }

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const outputPanel = outputPanelRef.current;
        if (!outputPanel) {
          return;
        }

        outputPanel.querySelector<HTMLElement>(".output-content")?.scrollTo({
          top: 0,
          behavior: "auto",
        });
        outputPanel.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        outputPanel.focus({ preventScroll: true });
      });
    });
  }, [result]);

  const checkBackendHealth = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/health`);
      if (!response.ok) {
        setBackendOnline(false);
        return;
      }
      const data = await response.json();
      setBackendOnline(data.status === "UP");
    } catch {
      setBackendOnline(false);
    }
  };

  

  const resetWorkspace = () => {
    lastSavedHistoryId.current = null;
    setRequirement("");
    setChangeRequest("");
    setResult("");
    setDiagramXml("");
    setAgents([]);
    setError("");
    setInteractiveStageIndex(0);
    setInteractiveContext({});
    setApprovedSections([]);
  };

  const openHistoryItem = (item: RequirementHistoryItem) => {
    setActiveCapability("requirement");
    setRequirement(item.requirement);
    setResult(item.result);
    setDiagramXml(item.diagramXml);
    setInteractiveStageIndex(activeStagesSequence.length);
    setApprovedSections([]);
    setError("");
    setHistoryOpen(false);
  };

  const clearInput = () => {
    if (activeCapability === "requirement") {
      setRequirement("");
    } else if (activeCapability === "change-impact") {
      setChangeRequest("");
    }
    setError("");
  };

  /*
   * ----------------------------------------------------------
   * CHANGE IMPACT
   * ----------------------------------------------------------
   */

  const analyzeChangeImpact = async (changeOverride?: string) => {
    const requestedChange = changeOverride || changeRequest;

    if (!requestedChange.trim()) {
      setError(
        "Please describe the requested change."
      );
      return;
    }

    setLoading(true);
    setError("");
    setResult("");
    setAgents([]);

    try {
      const response = await fetch(
        `${API_BASE_URL}/change-impact`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            change: requestedChange,
          }),
        }
      );

      const data: ApiResponse = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error ||
            "Change impact analysis failed."
        );
      }

      setResult(data.result || "");
      setAgents(data.stages || []);

      // Prefer structured payload when available
      if (data.changeImpact) {
        setChangeImpactData(data.changeImpact);
      } else {
        // Attempt to extract simple metrics from the textual `result`
        const text = (data.result || "").replace(/\n/g, " ");
        const reposMatch = text.match(/(\d+)\s+affected\s+repositories/i);
        const filesMatch = text.match(/(\d+)\s+affected\s+files/i);
        const apiMatch = text.match(/(\d+)\s+api\s+contracts?/i);
        const riskMatch = text.match(/overall\s+risk\s*[:\-]?\s*(\w+)/i);

        const metrics: any = {};
        if (reposMatch) metrics.affected_repositories = Number(reposMatch[1]);
        if (filesMatch) metrics.affected_files = Number(filesMatch[1]);
        if (apiMatch) metrics.api_contracts = Number(apiMatch[1]);
        if (riskMatch) metrics.overall_risk = riskMatch[1];

        // try to extract a short impact summary list
        const summaryMatch = (data.result || "").match(/Impact summary[\s\S]*?(?=\n\n|$)/i);
        if (summaryMatch) {
          metrics.impact_summary = summaryMatch[0].split(/\n{1,}/).map((s) => s.replace(/^[-\d\.\s]*/, '').trim()).filter(Boolean);
        }

        setChangeImpactData(Object.keys(metrics).length ? metrics : null);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  };

  /*
   * ----------------------------------------------------------
   * EXECUTE ACTIVE CAPABILITY
   * ----------------------------------------------------------
   */

  const executeCapability = async () => {
    setError("");

    switch (activeCapability) {
      case "requirement":
        // Show sections selection modal first so user can choose outputs
        setSectionsModalOpen(true);
        return;
        break;

      case "change-impact":
        await analyzeChangeImpact();
        break;
    }
  };

  const toggleSection = (section: string) => {
    setSectionsSelected((s) => ({ ...s, [section]: !s[section] }));
  };

  const selectAllSections = (on: boolean) => {
    const next: Record<string, boolean> = {};
    interactiveStages.forEach((s) => {
      if (s === "assemble") return;
      next[s] = on;
    });
    setSectionsSelected(next);
  };

  const confirmSectionsAndStart = async () => {
    const selected = Object.keys(sectionsSelected).filter((k) => sectionsSelected[k]);
    if (!selected.length) {
      setError("Select at least one section to generate.");
      return;
    }

    // Preserve the canonical order, but run exactly the checked stages.
    const seq = interactiveStages.filter((stage) => selected.includes(stage));
    const initialContext: Record<string, unknown> = { ...interactiveContext, selected_sections: selected };
    setInteractiveContext(initialContext);
    setActiveStagesSequence(seq);
    setSectionsModalOpen(false);
    await startInteractiveAnalysis(seq, initialContext);
  };


  /*
   * ----------------------------------------------------------
   * CAPABILITY CONFIG
   * ----------------------------------------------------------
   */

  const capabilityConfig = {
    requirement: {
      title: "Application Builder",
      subtitle:
        "Turn a business requirement into architecture, code, tests, security controls, and documentation.",
      button: "Build Application",
      inputLabel: "Business Requirement",
      placeholder:
        "Describe the application, users, key workflows, and expected outcome...",
      hint:
        "Describe the application you want to build in natural language.",
      icon: "◇",
    },

    "change-impact": {
      title: "Change Impact Analysis",
      subtitle:
        "Identify affected components, APIs, database changes, tests and implementation risks.",
      button: "Analyze Change",
      inputLabel: "Change Request",
      placeholder:
        "Describe the requested change...\n\nExample:\nAdd support for half-day leave requests and update the approval workflow.",
      hint:
        "Describe the requested change and expected business behaviour.",
      icon: "⇄",
    },
  };

  const current = capabilityConfig[activeCapability];

  /*
   * ----------------------------------------------------------
   * INPUT VALUE
   * ----------------------------------------------------------
   */

  const getInputValue = () => {
    switch (activeCapability) {
      case "requirement":
        return requirement;

      case "change-impact":
        return changeRequest;
    }
  };

  const setInputValue = (value: string) => {
    switch (activeCapability) {
      case "requirement":
        setRequirement(value);
        break;

      case "change-impact":
        setChangeRequest(value);
        break;
    }
  };

  const runRequirementStep = async (
    stage: string,
    correction = "",
    context = interactiveContext,
    selectedSections = (context.selected_sections as string[]) || []
  ) => {
    setLoading(true);
    setError("");

    try {
      console.debug("Requesting stage:", stage);
      const response = await fetch(`${API_BASE_URL}/analyze/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requirement, stage, context, correction, selected_sections: selectedSections }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.error || "Requirement stage failed.");
      }
      setInteractiveContext(data.context || {});
      if (stage === "assemble") {
        setApprovedSections([]);
      }
      // When the backend reports generation is in progress for this section
      // show a section-level generating message instead of blocking the whole UI.
      if (data.generating) {
        setResult("Generating...");
      } else {
        setResult(data.content || "");
      }
      setDiagramXml(data.diagram || "");
      setAgents(data.stages || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect to the backend.");
    } finally {
      setLoading(false);
      setTransitionNote(null);
    }
  };

  const startInteractiveAnalysis = async (
    selectedSequence = activeStagesSequence,
    initialContext = interactiveContext,
  ) => {
    lastSavedHistoryId.current = null;
    setInteractiveStageIndex(0);
    // Build an explicit initial context including standards and selected sections
    const requestContext = {
      ...initialContext,
      development_standards: engineeringSummary || "",
      design_standards: designSummary || "",
      selected_sections: initialContext.selected_sections || selectedSequence,
    } as Record<string, any>;
    setInteractiveContext(requestContext);
    setResult("");
    setDiagramXml("");
    setApprovedSections([]);
    // Start the first selected stage (should be 'requirement')
    const firstStage = selectedSequence[0];
    await runRequirementStep(firstStage, "", requestContext, requestContext.selected_sections as string[]);
  };

  const SLOW_STAGE_HINTS: Record<string, string> = {
    generate_code: " Generating the codebase can take a little longer.",
    documentation: " Writing 5 detailed documents can take up to a minute.",
  };

  const approveRequirementSection = async () => {
    const nextIndex = interactiveStageIndex + 1;
    if (result) {
      setApprovedSections((current) => [...current, result]);
    }

    if (nextIndex >= activeStagesSequence.length) {
      setInteractiveStageIndex(activeStagesSequence.length);
      return;
    }

    const currentLabel = stageLabels[activeStagesSequence[interactiveStageIndex]] || "this section";
    const nextStageName = activeStagesSequence[nextIndex];
    const nextLabel = stageLabels[nextStageName] || "the next section";
    const slowHint = SLOW_STAGE_HINTS[nextStageName] || "";
    setInteractiveStageIndex(nextIndex);
    setTransitionNote(`Reviewed ${currentLabel}. Moving to ${nextLabel}...${slowHint}`);
    await runRequirementStep(nextStageName, "", interactiveContext);
  };

  const correctSection = async (sectionTitle: string, correction: string) => {
    if (activeCapability === "requirement") {
      await runRequirementStep(activeStagesSequence[interactiveStageIndex], correction);
      return;
    }

    const feedback = `\n\nUser correction for ${sectionTitle}:\n${correction}`;
    await analyzeChangeImpact(`${changeRequest}${feedback}`);
  };

  const previewRequirementPack = () => {
    window.open(`${API_BASE_URL}/requirement-analysis/preview`, "_blank", "noopener,noreferrer");
  };

  const downloadRequirementPack = () => {
    window.open(`${API_BASE_URL}/requirement-analysis/download`, "_blank", "noopener,noreferrer");
  };

  /*
   * ----------------------------------------------------------
   * CAPABILITY SWITCH
   * ----------------------------------------------------------
   */

  const switchCapability = (
    capability: Capability
  ) => {
    setActiveCapability(capability);
    setResult("");
    setDiagramXml("");
    setAgents([]);
    setError("");
    setInteractiveStageIndex(0);
    setInteractiveContext({});
    setApprovedSections([]);
  };

  /*
   * ----------------------------------------------------------
   * SIDEBAR
   * ----------------------------------------------------------
   */

  const renderSidebar = () => (
    <aside className={loading || result ? "sidebar sidebar-scrollable" : "sidebar"}>
      <div className="brand">
        <div className="brand-icon">AI</div>

        <div>
          <div className="brand-title">
            BuildPilot
          </div>
          <div className="brand-subtitle">Engineering Copilot</div>
        </div>
      </div>

      <div className="sidebar-top-actions">
        <button className="new-build-btn" onClick={() => { resetWorkspace(); setActiveCapability("requirement"); }}>
          <span className="new-build-icon">+</span>
          <span>New Build</span>
        </button>

        <div className="sidebar-section-label">CAPABILITIES</div>

        <nav className="sidebar-capabilities">
          <button
            className={
              activeCapability === "requirement"
                ? "sidebar-capability active"
                : "sidebar-capability"
            }
            onClick={() => switchCapability("requirement")}
          >
            <span className="sidebar-capability-icon app">
              <FileCog />
            </span>

            <span>
              <strong>Application Builder</strong>
              <small>Full SDLC delivery</small>
            </span>
          </button>
          {activeCapability === "requirement" && (loading || result) && (
            <ul className="sidebar-flow-steps">
              {REQUIREMENT_FLOW_STEPS.filter((step) => activeStagesSequence.includes(interactiveStages[step.stageIndex])).map((step) => {
                const stageName = interactiveStages[step.stageIndex];
                const pos = activeStagesSequence.indexOf(stageName);

                let status: string;
                if (interactiveStageIndex >= activeStagesSequence.length) {
                  status = "done";
                } else if (pos === -1) {
                  status = "pending";
                } else if (pos < interactiveStageIndex) {
                  status = "done";
                } else if (pos === interactiveStageIndex) {
                  status = "current";
                } else {
                  status = "pending";
                }

                return (
                  <li className={`sidebar-flow-step ${status}`} key={step.label}>
                    <span className="sidebar-flow-step-dot">{status === "done" ? "✓" : ""}</span>
                    <span>{step.label}</span>
                  </li>
                );
              })}
            </ul>
          )}

          <button
            className={
              activeCapability === "change-impact"
                ? "sidebar-capability active"
                : "sidebar-capability"
            }
            onClick={() => switchCapability("change-impact")}
          >
            <span className="sidebar-capability-icon impact">
              <ArrowRightLeft />
            </span>

            <span>
              <strong>Change Impact</strong>
              <small>Dependencies & risks</small>
            </span>
          </button>
        </nav>
      </div>

      <nav className="sidebar-links">
        <button className="sidebar-capability" onClick={() => setHistoryOpen(true)}>
          <span className="sidebar-capability-icon history">
            <History />
          </span>

          <span>
            <strong>History</strong>
            <small>Recent analyses</small>
          </span>
        </button>
      </nav>

      <div className="sidebar-bottom">
        <div className="engine-card">
          <div className="engine-header">
            <span
              className={
                backendOnline
                  ? "status-dot"
                  : "status-dot offline"
              }
            />

            <span>AI Engine</span>

            <span className="engine-connected">
              {backendOnline
                ? "Connected"
                : "Offline"}
            </span>
          </div>

          <div className="engine-model">
            <label style={{display: 'block', fontWeight: 700, fontSize: 12, marginBottom: 6}}>Model</label>
            <select
              value={activeModelId}
              onChange={async (e) => {
                const id = e.target.value;
                setActiveModelId(id);
                try {
                  await fetch(`${API_BASE_URL}/model`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_id: id })
                  });
                } catch {
                  // ignore
                }
              }}
              style={{width: '100%'}}
            >
              <option value="">Select model...</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>

          <div className="engine-region">
            {activeModelId.includes('nova') ? 'AWS eu-west-2' : 'Claude'}
          </div>
        </div>

      </div>
    </aside>
  );

  /*
   * ----------------------------------------------------------
   * ANALYSIS STATUS
   * ----------------------------------------------------------
   */

  const renderAnalysisStatus = () => {
    if (!loading && !result) {
      return null;
    }

    return (
      <div
        className={
          loading
            ? "analysis-status running"
            : "analysis-status completed"
        }
      >
        <span className="analysis-status-icon">
          {loading ? "●" : "✓"}
        </span>

        <span>
          {loading
            ? `AI is analyzing your ${activeCapability === "requirement"
                ? "requirement"
                : "change request"
              }...`
            : "Analysis completed successfully"}
        </span>

        {loading && (
          <span className="analysis-status-pulse" />
        )}
      </div>
    );
  };

  /*
   * ----------------------------------------------------------
   * AGENT PIPELINE
   * ----------------------------------------------------------
   */

  const renderAgentPipeline = () => {
    const visibleAgents = agents.filter((agent) => agent.name !== "Assembler Agent");

    if (!visibleAgents.length) {
      return null;
    }

    return (
      <div className="agent-pipeline">
        <div className="agent-pipeline-header">
          <span className="output-eyebrow">
            LANGGRAPH AGENT RUN
          </span>

          <span className="agent-count">
            {visibleAgents.length} agents
          </span>
        </div>

        <div className="agent-pipeline-list">
          {visibleAgents.map((agent, index) => (
            <div
              className="agent-step"
              key={`${agent.name}-${index}`}
              title={agent.role}
            >
              <span className="agent-step-index">
                {String(index + 1).padStart(2, "0")}
              </span>

              <span className="agent-step-body">
                <strong>{agent.name}</strong>

                {agent.role && (
                  <small>{agent.role}</small>
                )}
              </span>

              <span className="agent-step-status">
                {activeCapability === "requirement"
                  ? "Review"
                  : agent.status || "Completed"}
              </span>
            </div>
          ))}
        </div>

      </div>
    );
  };

  /*
   * ----------------------------------------------------------
   * MAIN UI
   * ----------------------------------------------------------
   */
  const displayedResult = [...approvedSections, result]
    .filter(Boolean)
    .join("\n\n");
  const currentStage = activeStagesSequence[interactiveStageIndex];
  const isPostDataModelStage = Boolean(
    currentStage &&
    interactiveStages.indexOf(currentStage) > interactiveStages.indexOf("data_model")
  );

  const copyAllOutput = async () => {
    const text = displayedResult || result;

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        throw new Error("Clipboard API unavailable");
      }
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand("copy");
      } catch {
        // Ignore: clipboard copy is best-effort.
      }
      document.body.removeChild(textarea);
    }

    setCopiedAll(true);
    window.setTimeout(() => setCopiedAll(false), 1800);
  };

  return (
    <div className={`app-shell polished-ui ${activeCapability === "change-impact" ? "change-impact-app" : ""}`}>
      {renderSidebar()}

      <main className={`${result ? "main-content has-results" : !loading ? "main-content home-screen" : "main-content"}${buildSettingsOpen ? " settings-open" : ""}`}>
        <header className="topbar">
          <div className="topbar-left">
            <div className="breadcrumb">
              WORKSPACE
              <span>/</span>
              {activeCapability === "change-impact" ? "CHANGE IMPACT" : "APPLICATION BUILDER"}
            </div>
            <div className="topbar-heading-row">
              <div>
                <h1>{activeCapability === "change-impact" ? "Change intelligence" : "Build your next application"}</h1>
                <p>{activeCapability === "change-impact" ? "Trace downstream dependencies before the first line of code changes." : "From business intent to a developer-ready implementation pack."}</p>
              </div>
              
            </div>
          </div>

          <div className="topbar-actions">
            <div style={{position: 'relative'}}>
              <button className="topbar-bell" type="button" aria-label="Notifications" onClick={() => setNotifOpen((s) => !s)}>
                <Bell aria-hidden="true" />
              </button>

              {notifOpen && (
                <div className="notif-panel" role="dialog" aria-label="Notifications">
                  <div className="notif-header">Notifications</div>
                  <div className="notif-list">
                    <div className="notif-item">AI analysis completed for <strong>Expense Management</strong></div>
                    <div className="notif-item">Knowledge base updated (3 docs)</div>
                    <div className="notif-item">Backend health check: Online</div>
                  </div>
                </div>
              )}
            </div>

          </div>

        </header>

        {historyOpen && (
          <div className="history-backdrop" role="presentation" onClick={() => setHistoryOpen(false)}>
            <section className="history-dialog" role="dialog" aria-modal="true" aria-label="Requirement history" onClick={(event) => event.stopPropagation()}>
              <div className="history-dialog-header">
                <div>
                  <span>REQUIREMENT HISTORY</span>
                  <strong>Saved implementation packs</strong>
                </div>
                <button type="button" onClick={() => setHistoryOpen(false)} aria-label="Close history">×</button>
              </div>
              <div className="history-list">
                {historyItems.length ? historyItems.map((item) => (
                  <article className="history-item" key={item.id}>
                    <div>
                      <strong>{item.requirement}</strong>
                      <span>{new Date(item.createdAt).toLocaleString()}</span>
                    </div>
                    <div className="history-item-actions">
                      <button type="button" onClick={() => openHistoryItem(item)}>Open</button>
                    </div>
                  </article>
                )) : (
                  <p className="history-empty">Completed requirement analyses will appear here.</p>
                )}
              </div>
            </section>
          </div>
        )}

        {sectionsModalOpen && (
          <div className="sections-backdrop" role="presentation" onClick={() => setSectionsModalOpen(false)}>
            <section className="sections-dialog" role="dialog" aria-modal="true" aria-label="Select sections to generate" onClick={(event) => event.stopPropagation()}>
              <div className="sections-dialog-header">
                <div>
                  <span>SECTIONS TO GENERATE</span>
                  <strong>Choose the outputs to include in this build.</strong>
                </div>
                <button type="button" onClick={() => setSectionsModalOpen(false)} aria-label="Close sections dialog">×</button>
              </div>

              <div className="sections-dialog-body">
                <div className="sections-dialog-meta">
                  <div className="selected-count">{Object.values(sectionsSelected).filter(Boolean).length} of {interactiveStages.filter(s => s !== 'assemble').length} selected</div>
                  <div className="sections-controls">
                    <button type="button" onClick={() => selectAllSections(true)}>Select all</button>
                    <span className="divider">|</span>
                    <button type="button" onClick={() => selectAllSections(false)}>Clear</button>
                  </div>
                </div>

                <div className="sections-list">
                  {interactiveStages.filter(s => s !== 'assemble').map((s) => (
                    <label className="section-item" key={s}>
                      <div className="section-item-icon" aria-hidden="true">{stageIcons[s]}</div>

                      <div className="section-text">
                        <strong>{stageLabels[s] || s}</strong>
                        <small>{/* description could go here */}</small>
                      </div>

                      <div className="section-check">
                        <input id={`chk-${s}`} type="checkbox" checked={!!sectionsSelected[s]} onChange={() => toggleSection(s)} />
                        <span className="custom-check" aria-hidden="true">
                          {sectionsSelected[s] ? <Check size={14} /> : null}
                        </span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div className="sections-dialog-actions">
                <button className="reset-btn" type="button" onClick={() => setSectionsModalOpen(false)}>Cancel</button>
                <button className="done-btn" type="button" onClick={confirmSectionsAndStart}>Build</button>
              </div>
            </section>
          </div>
        )}

        <section className={`${!result && !loading ? "workspace home-workspace" : "workspace"} ${activeCapability === "change-impact" ? "change-impact-workspace" : ""}`}>
          <div className="workspace-header">
            <div>
              <div className="workspace-kicker">{activeCapability === "change-impact" ? "RISK & DEPENDENCY REVIEW" : "INTELLIGENT DELIVERY WORKSPACE"}</div>
              <div className="workspace-heading-icon" aria-hidden="true">
                {activeCapability === "change-impact" ? <ArrowRightLeft /> : <FileCog />}
              </div>

              <h2>{current.title}</h2>

              <p>{current.subtitle}</p>
            </div>

            <div className="workspace-helper">
              <Lightbulb aria-hidden="true" />
              <span>Describe clearly for better results</span>
            </div>

            {!result && !loading && (
              <div className="workspace-metrics" aria-label="Workspace capabilities">
                <span><strong>12</strong> delivery stages</span>
                <span><strong>AI</strong> guided review</span>
              </div>
            )}

            <button
              className="clear-btn"
              onClick={resetWorkspace}
              title="Start new analysis (clear workspace)"
              aria-label="Start new analysis"
            >
              <Trash2 className="clear-icon" aria-hidden="true" />
              New Analysis
            </button>
          </div>

          {renderAnalysisStatus()}

          <div className={`editor-layout ${buildSettingsOpen ? "has-build-settings" : ""}`}>
            {activeCapability === "change-impact" && !result && !loading ? (
              <div className="input-panel">
                <ChangeImpactHome
                  changeRequest={changeRequest}
                  setChangeRequest={setChangeRequest}
                  onAnalyze={() => analyzeChangeImpact()}
                />
              </div>
            ) : (
              <section className="input-panel">
              <div className="panel-header">
                <div className="panel-heading-group">
                  <span className="panel-label">
                    INPUT
                  </span>

                  <span className="panel-type">
                    {current.inputLabel}
                  </span>
                </div>

                  <div className="panel-controls">
                    <span className="character-count">
                      {getInputValue().length} / 4000
                    </span>
                  </div>
              </div>

              <div className="editor-input-area">
                <textarea
                  value={getInputValue()}
                  onChange={(event) => setInputValue(event.target.value)}
                  placeholder={current.placeholder}
                  spellCheck={activeCapability === "requirement"}
                  className="requirement-editor"
                />

                {activeCapability === "requirement" && (
                  <div className="example-prompts">
                    <span>Try an example</span>
                    {examplePrompts.map((prompt) => (
                      <button
                        type="button"
                        className="example-chip"
                        key={prompt}
                        onClick={() => setRequirement(
                          `Build a ${prompt.toLowerCase()} application for our organization.`
                        )}
                      >
                        <span className="example-chip-icon" aria-hidden="true">
                          {prompt === "Expense Management" ? <WalletCards /> : prompt === "Employee Leave" ? <UserRound /> : <UsersRound />}
                        </span>
                        <span className="example-chip-copy">
                          <strong>{prompt}</strong>
                          <small>{prompt === "Expense Management" ? "Track and approve expenses" : prompt === "Employee Leave" ? "Leave requests and approvals" : "Manage customers and interactions"}</small>
                        </span>
                        <ChevronRight className="example-arrow" aria-hidden="true" />
                      </button>
                    ))}
                  </div>
                )}
              </div>

              

              <div className="editor-footer">
                <div className="editor-hint">
                  <span className="editor-hint-icon" aria-hidden="true">
                    <ClipboardList />
                  </span>
                  {current.hint}
                </div>

                <div className="editor-actions">
                  <button
                    type="button"
                    className={`build-settings-btn ${buildSettingsOpen ? "active" : ""}`}
                    onClick={() => setBuildSettingsOpen((s) => !s)}
                  >
                    <Settings aria-hidden="true" />
                    Build Settings
                    <ChevronDown className={buildSettingsOpen ? "expanded" : ""} aria-hidden="true" />
                  </button>
                  <button className="clear-input-btn" type="button" onClick={clearInput}>
                    <Trash2 aria-hidden="true" />
                    Clear
                  </button>
                  <button
                    className="execute-btn"
                    onClick={executeCapability}
                    disabled={
                      loading ||
                      !getInputValue().trim() ||
                      !backendOnline
                    }
                  >
                    {loading ? (
                      <><span className="spinner" /> Processing...</>
                    ) : (
                      <>{current.button}<ArrowRight aria-hidden="true" /></>
                    )}
                  </button>
                </div>
              </div>
            </section>
            )}

            {buildSettingsOpen && (
              <aside className="build-settings-drawer" role="dialog" aria-label="Build Settings">
                <div className="build-settings-header">
                  <div className="build-settings-heading">
                    <Settings aria-hidden="true" />
                    <div>
                      <strong>Build Settings</strong>
                      <div className="build-settings-sub">Configure optional settings to guide the generated application.</div>
                    </div>
                  </div>
                  <button className="build-settings-close" onClick={() => setBuildSettingsOpen(false)} aria-label="Close build settings"><X /></button>
                </div>

                <div className="build-settings-body">
                  <div className="build-settings-section engineering-section">
                    <button
                      type="button"
                      className={`accordion-toggle ${sectionsOpen.engineering ? 'open' : ''}`}
                      aria-expanded={sectionsOpen.engineering}
                      aria-controls="engineering-standards-body"
                      onClick={() => setSectionsOpen((s) => ({ ...s, engineering: !s.engineering }))}
                    >
                      <div className="accordion-heading">
                        <FileCog aria-hidden="true" />
                        <span><strong>Development Standards</strong><small>Coding conventions, development practices and project guidelines.</small></span>
                        <span className="optional-pill">Optional</span>
                      </div>
                      <ChevronDown className={`accordion-chevron ${sectionsOpen.engineering ? 'expanded' : ''}`} />
                    </button>

                    {sectionsOpen.engineering && (
                      <div className="accordion-body design-standards-body" id="engineering-standards-body">
                        <label className="field-label" htmlFor="engineering-standards-url">Development standards URL</label>
                        <div className="design-url">
                          <Link2 aria-hidden="true" />
                          <input
                            id="engineering-standards-url"
                            type="url"
                            placeholder="https://engineering.example.com/standards"
                            value={engineeringStandardsUrl}
                            onChange={(event) => setEngineeringStandardsUrl(event.target.value)}
                          />
                        </div>
                        <div className="or-divider"><span>OR</span></div>
                        <label className="design-upload-zone">
                          <Upload aria-hidden="true" />
                          <strong>Upload development guidelines</strong>
                          <small>PDF, DOCX, TXT or MD · Max 10 MB per file</small>
                          <input
                            type="file"
                            multiple
                            accept=".txt,.md,.pdf,.docx"
                            onChange={(e) => {
                              const files = Array.from(e.target.files ?? []);
                              if (!files.length) return;
                              const invalid = files.some((file) =>
                                file.size > 10 * 1024 * 1024 || !/\.(pdf|docx|txt|md)$/i.test(file.name)
                              );
                              if (invalid) {
                                setEngineeringFileError("Choose PDF, DOCX, TXT or MD files up to 10 MB each.");
                              } else {
                                setEngineeringFileError("");
                                setEngineeringFiles(files);
                              }
                              e.currentTarget.value = "";
                            }}
                          />
                        </label>
                        {engineeringFileError && <p role="alert" className="design-help">{engineeringFileError}</p>}
                        {engineeringFiles.length > 0 && (
                          <div className="uploaded-design-files" title={engineeringFiles.map((f) => f.name).join(' · ')}>
                            {engineeringFiles.length} file(s) selected: {engineeringFiles.map((f) => f.name).join(' · ')}
                          </div>
                        )}
                        <p className="design-help">Add coding conventions, development practices and project guidelines.</p>
                      </div>
                    )}
                  </div>
                  <div className="build-settings-section">
                    <button type="button" className={`accordion-toggle ${sectionsOpen.design ? "open" : ""}`} onClick={() => setSectionsOpen((s) => ({ ...s, design: !s.design }))}>
                      <div className="accordion-heading">
                        <Palette aria-hidden="true" />
                        <span><strong>Design Standards</strong><small>Guide the look and feel of the generated prototype.</small></span>
                        <span className="optional-pill">Optional</span>
                      </div>
                      <ChevronDown className={`accordion-chevron ${sectionsOpen.design ? "expanded" : ""}`} />
                    </button>
                    {sectionsOpen.design && (
                      <div className="accordion-body design-standards-body">
                        <label className="field-label" htmlFor="design-system-url">Design system URL</label>
                        <div className="design-url">
                          <Link2 aria-hidden="true" />
                          <input id="design-system-url" type="url" placeholder="https://design-system.example.com" value={designSystemUrl} onChange={(e) => setDesignSystemUrl(e.target.value)} />
                        </div>
                        <div className="or-divider"><span>OR</span></div>
                        <label className="design-upload-zone">
                          <Upload aria-hidden="true" />
                          <strong>{designUploading ? "Uploading..." : "Upload design guidelines"}</strong>
                          <small>PDF, DOCX or image · Max 10 MB</small>
                          <input type="file" accept=".pdf,.docx,image/*" onChange={(e) => {
                            const files = Array.from(e.target.files ?? []);
                            if (files?.length) setDesignFiles(files);
                            setDesignUploading(true);
                            window.setTimeout(() => setDesignUploading(false), 600);
                            e.currentTarget.value = "";
                          }} />
                        </label>
                        {designFiles.length > 0 && <div className="uploaded-design-files">{designFiles.map((f) => f.name).join(" · ")}</div>}
                        <p className="design-help">The prototype will use these colours, components, typography and accessibility rules.</p>
                      </div>
                    )}
                  </div>

                  <div className="build-settings-section">
                    <button type="button" className="accordion-toggle" onClick={() => setSectionsOpen((s) => ({ ...s, technology: !s.technology }))}>
                      <div className="accordion-heading"><Code2 /><span><strong>Technology Preferences</strong><small>Preferred languages, frameworks, and tools</small></span></div>
                      <ChevronDown className={`accordion-chevron ${sectionsOpen.technology ? "expanded" : ""}`} />
                    </button>
                    {sectionsOpen.technology && <div className="accordion-body pref-list">
                      <label><input type="checkbox" defaultChecked /> React (frontend)</label>
                      <label><input type="checkbox" defaultChecked /> TypeScript</label>
                      <label><input type="checkbox" /> Spring Boot (Java)</label>
                      <label><input type="checkbox" /> Terraform</label>
                    </div>}
                  </div>

                  <div className="build-settings-section">
                    <button type="button" className="accordion-toggle" onClick={() => setSectionsOpen((s) => ({ ...s, security: !s.security }))}>
                      <div className="accordion-heading"><ShieldCheck /><span><strong>Security &amp; Compliance</strong><small>Security requirements and compliance standards</small></span></div>
                      <ChevronDown className={`accordion-chevron ${sectionsOpen.security ? "expanded" : ""}`} />
                    </button>
                    {sectionsOpen.security && <div className="accordion-body pref-list">
                      <label><input type="checkbox" defaultChecked /> OWASP basics</label>
                      <label><input type="checkbox" /> Data encryption at rest</label>
                    </div>}
                  </div>

                  <div className="build-settings-section">
                    <button type="button" className="accordion-toggle" onClick={() => setSectionsOpen((s) => ({ ...s, testing: !s.testing }))}>
                      <div className="accordion-heading"><TestTube2 /><span><strong>Testing Preferences</strong><small>Test frameworks and coverage expectations</small></span></div>
                      <ChevronDown className={`accordion-chevron ${sectionsOpen.testing ? "expanded" : ""}`} />
                    </button>
                    {sectionsOpen.testing && <div className="accordion-body pref-list">
                      <label><input type="checkbox" defaultChecked /> Unit tests</label>
                      <label><input type="checkbox" /> Integration tests</label>
                      <label><input type="checkbox" /> E2E tests</label>
                    </div>}
                  </div>

                  <div className="build-settings-section">
                    <button type="button" className="accordion-toggle" onClick={() => setSectionsOpen((s) => ({ ...s, deployment: !s.deployment }))}>
                      <div className="accordion-heading"><Cloud /><span><strong>Deployment Preferences</strong><small>Cloud platform and deployment options</small></span></div>
                      <ChevronDown className={`accordion-chevron ${sectionsOpen.deployment ? "expanded" : ""}`} />
                    </button>
                    {sectionsOpen.deployment && <div className="accordion-body pref-list">
                      <label><input type="checkbox" defaultChecked /> AWS</label>
                      <label><input type="checkbox" /> Container deployment</label>
                      <label><input type="checkbox" /> Serverless deployment</label>
                    </div>}
                  </div>

                </div>

                  <div className="build-settings-actions">
                    {buildSettingsProcessing && <div className="build-settings-status">Processing...</div>}
                    {buildSettingsSuccess && <div className="build-settings-status success">{buildSettingsSuccess}</div>}
                    {buildSettingsError && <div className="build-settings-status error">{buildSettingsError}</div>}
                  <button className="reset-btn" onClick={async () => {
                    // Clear frontend state and backend store
                    setDesignSystemUrl("");
                    setEngineeringStandardsUrl("");
                    setEngineeringFileError("");
                    setDesignFiles([]);
                    setEngineeringFiles([]);
                    setEngineeringSummary("");
                    setDesignSummary("");

                    try {
                      setBuildSettingsProcessing(true);
                      const r = await fetch(`${API_BASE_URL}/knowledge-base`, { method: 'DELETE' });
                      if (!r.ok) throw new Error('Failed to clear backend knowledge base');
                      setBuildSettingsSuccess('Cleared');
                    } catch (err) {
                      setBuildSettingsError(err instanceof Error ? err.message : 'Reset failed');
                    } finally {
                      setBuildSettingsProcessing(false);
                      window.setTimeout(() => { setBuildSettingsSuccess(null); setBuildSettingsError(null); }, 1800);
                    }
                  }}>Reset</button>
                  <button className="done-btn" onClick={async () => {
                    setBuildSettingsProcessing(true);
                    setBuildSettingsError(null);
                    setBuildSettingsSuccess(null);

                    try {
                      // Engineering: URL first, then files
                      let engSummary = "";
                      if (engineeringStandardsUrl) {
                        const resp = await fetch(`${API_BASE_URL}/build-settings/fetch-url`, {
                          method: 'POST', headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ url: engineeringStandardsUrl, category: 'engineering' })
                        });
                        const data = await resp.json();
                        if (!resp.ok || !data.success) throw new Error(data.error || 'Failed to fetch engineering URL');
                        engSummary = data.summary || '';
                        if (data.warning) setBuildSettingsError(data.warning);
                      }

                      if (engineeringFiles.length > 0) {
                        const form = new FormData();
                        engineeringFiles.forEach((f) => form.append('files', f));
                        form.append('category', 'engineering');
                        const resp = await fetch(`${API_BASE_URL}/build-settings/upload`, { method: 'POST', body: form });
                        const data = await resp.json();
                        if (!resp.ok || !data.success) throw new Error(data.error || 'Failed to upload engineering files');
                        engSummary = engSummary || data.summary || '';
                        if (data.warning) setBuildSettingsError(data.warning);
                      }

                      let desSummary = "";
                      if (designSystemUrl) {
                        const resp = await fetch(`${API_BASE_URL}/build-settings/fetch-url`, {
                          method: 'POST', headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ url: designSystemUrl, category: 'design' })
                        });
                        const data = await resp.json();
                        if (!resp.ok || !data.success) throw new Error(data.error || 'Failed to fetch design URL');
                        desSummary = data.summary || '';
                        if (data.warning) setBuildSettingsError(data.warning);
                      }

                      if (designFiles.length > 0) {
                        const form = new FormData();
                        designFiles.forEach((f) => form.append('files', f));
                        form.append('category', 'design');
                        const resp = await fetch(`${API_BASE_URL}/build-settings/upload`, { method: 'POST', body: form });
                        const data = await resp.json();
                        if (!resp.ok || !data.success) throw new Error(data.error || 'Failed to upload design files');
                        desSummary = data.summary || desSummary;
                        if (data.warning) setBuildSettingsError(data.warning);
                      }

                      setEngineeringSummary(engSummary || '');
                      setDesignSummary(desSummary || '');
                      setInteractiveContext(current => ({ ...current, design_standards: desSummary || '', development_standards: engSummary || '' }));

                      setBuildSettingsSuccess('Saved');
                      // Close the drawer and keep settings retained
                      setTimeout(() => setBuildSettingsOpen(false), 300);

                    } catch (err) {
                      setBuildSettingsError(err instanceof Error ? err.message : 'Failed to save settings');
                    } finally {
                      setBuildSettingsProcessing(false);
                      window.setTimeout(() => { setBuildSettingsSuccess(null); setBuildSettingsError(null); }, 2200);
                    }
                  }}>Done</button>
                </div>
              </aside>
            )}

            {(loading || error || result) && <section
              className="output-panel"
              ref={outputPanelRef}
              tabIndex={-1}
              aria-live="polite"
            >
              <div className="output-panel-header">
                <div className="output-title-group">
                  <div className="output-title">
                    <span className="output-ai-icon">
                      ✦
                    </span>

                    <div>
                      <span className="panel-label">
                        AI OUTPUT
                      </span>

                      <span className="panel-type">
                        {loading
                          ? "Generating response..."
                          : result
                          ? "Developer-ready output"
                          : "Awaiting analysis"}
                      </span>
                    </div>
                  </div>
                </div>

                {result && (
                  <button
                    className="copy-btn"
                    type="button"
                    onClick={copyAllOutput}
                  >
                    <span>⧉</span>
                    {copiedAll ? "Copied" : "Copy All"}
                  </button>
                )}
              </div>

              <div className="output-content">
                {loading && (
                  <div className="loading-state">
                    <div className="loading-orb">
                      <span>AI</span>
                    </div>

                    <h3>
                      {transitionNote ? "Section approved — moving on" : "Building your output"}
                    </h3>

                    <p>
                      {transitionNote || "The AI agent is analyzing the input and preparing a developer-ready response."}
                    </p>

                    {!transitionNote && (
                      <div className="loading-steps">
                        <span className="active">
                          Understanding input
                        </span>
                        <span>
                          Applying SDLC knowledge
                        </span>
                        <span>
                          Structuring output
                        </span>
                      </div>
                    )}

                    <div className="loading-bar">
                      <div />
                    </div>
                  </div>
                )}

                {!loading && error && (
                  <div className="error-state">
                    <div className="error-icon">
                      !
                    </div>

                    <h3>
                      Processing failed
                    </h3>

                    <p>{error}</p>

                    {!backendOnline && (
                      <p className="error-hint">
                        Make sure your Flask backend
                        is running on port 5000.
                      </p>
                    )}
                  </div>
                )}

                {!loading &&
                  !error &&
                  !result && (
                    <div className="empty-state">
                      <div className="empty-icon">
                        ✦
                      </div>

                      <div className="empty-label">
                        AI OUTPUT
                      </div>

                      <h3>
                        Your engineering output
                        will appear here
                      </h3>

                      <p>
                        Enter your input above and run
                        the AI agent. Your generated
                        sections will appear below as
                        expandable cards.
                      </p>

                      <div className="empty-features">
                        <span>
                          <b>✓</b> Structured
                        </span>

                        <span>
                          <b>✓</b> SDLC-aware
                        </span>

                        <span>
                          <b>✓</b> Developer-ready
                        </span>
                      </div>
                    </div>
                  )}

                {!loading && !error && result && activeCapability === "change-impact" ? (
                  <ChangeImpactResults result={result} data={changeImpactData} onPreview={previewRequirementPack} onDownload={downloadRequirementPack} />
                ) : (!loading && !error && result) ? (
                  <div className="structured-output">
                    {renderAgentPipeline()}

                    {activeCapability === "requirement" &&
                      interactiveStageIndex >= activeStagesSequence.length && (
                        <div className="workflow-complete-banner">
                          <div className="workflow-complete-status">
                            <CheckCircle2 />
                            <div>
                              <strong>Implementation pack completed</strong>
                              <span>All stages have been reviewed and approved.</span>
                            </div>
                          </div>
                          <div className="workflow-complete-actions">
                            <button type="button" className="section-action" onClick={previewRequirementPack}>
                              <Eye aria-hidden="true" />
                              Preview
                            </button>
                            <button type="button" className="section-action section-action-primary" onClick={downloadRequirementPack}>
                              <Download aria-hidden="true" />
                              Download
                            </button>
                          </div>
                        </div>
                      )}

                    <SdlcOutput
                      content={displayedResult}
                      diagramXml={activeCapability === "requirement" ? diagramXml : undefined}
                      visibleSectionIds={activeStagesSequence
                        .map((stage) => STAGE_SECTION_IDS[stage])
                        .filter((sectionId) => sectionId > 0)}
                      activeSectionId={
                        activeStagesSequence[interactiveStageIndex]
                          ? STAGE_SECTION_IDS[activeStagesSequence[interactiveStageIndex]]
                          : STAGE_SECTION_IDS.generate_code
                      }
                      activeSectionLabel={stageLabels[activeStagesSequence[interactiveStageIndex]]}
                      onCorrection={interactiveStageIndex < activeStagesSequence.length - 1
                        ? correctSection
                        : undefined}
                      onApprove={interactiveStageIndex < activeStagesSequence.length - 1
                        ? approveRequirementSection
                        : undefined}
                      onNext={isPostDataModelStage ? approveRequirementSection : undefined}
                    />
                  </div>
                ) : null}
              </div>
            </section>}
          </div>

          <div className="workspace-footer">
            <div className="footer-spacer" />

            <div className="footer-item">
              BuildPilot · v1.0
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
