import SdlcOutput from "./sdlcOutput";
import { useEffect, useRef, useState } from "react";
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
  Plus,
  Settings,
  ShieldCheck,
  Sparkles,
  TestTube2,
  Upload,
  UserRound,
  UsersRound,
  WalletCards,
  X,
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

  const [loading, setLoading] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);
  const outputPanelRef = useRef<HTMLElement>(null);
  const [interactiveStageIndex, setInteractiveStageIndex] = useState(0);
  const [interactiveContext, setInteractiveContext] = useState<Record<string, string>>({});
  const [approvedSections, setApprovedSections] = useState<string[]>([]);
  const [transitionNote, setTransitionNote] = useState<string | null>(null);
  
  const [historyItems, setHistoryItems] = useState<RequirementHistoryItem[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [copiedAll, setCopiedAll] = useState(false);
  
  const [buildSettingsOpen, setBuildSettingsOpen] = useState(false);
  const [designSystemUrl, setDesignSystemUrl] = useState("");
  const [designUploading, setDesignUploading] = useState(false);
  const [engineeringFiles, setEngineeringFiles] = useState<string[]>([]);
  const [designFiles, setDesignFiles] = useState<string[]>([]);
  const [sectionsOpen, setSectionsOpen] = useState<Record<string, boolean>>({
    engineering: false,
    design: true,
    technology: false,
    security: false,
    testing: false,
    deployment: false,
  });
  const [notifOpen, setNotifOpen] = useState(false);
  const [avatarOpen, setAvatarOpen] = useState(false);
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
      interactiveStageIndex < interactiveStages.length ||
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
    setInteractiveStageIndex(interactiveStages.length);
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
        await startInteractiveAnalysis();
        break;

      case "change-impact":
        await analyzeChangeImpact();
        break;
    }
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
    context = interactiveContext
  ) => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/analyze/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requirement, stage, context, correction }),
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
      setAgents([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect to the backend.");
    } finally {
      setLoading(false);
      setTransitionNote(null);
    }
  };

  const startInteractiveAnalysis = async () => {
    lastSavedHistoryId.current = null;
    setInteractiveStageIndex(0);
    setInteractiveContext({});
    setResult("");
    setDiagramXml("");
    setApprovedSections([]);
    await runRequirementStep("requirement", "", {});
  };

  const SLOW_STAGE_HINTS: Record<string, string> = {
    generate_code: " Generating the codebase can take a little longer.",
    documentation: " Writing 5 detailed documents can take up to a minute.",
  };

  // Runs every remaining stage back-to-back with no approval gate in
  // between, threading context through a local variable (state set via
  // setInteractiveContext isn't visible again until the next render, so
  // relying on it across these sequential awaits would use stale context).
  const runRemainingStagesAutomatically = async (startIndex: number) => {
    setLoading(true);
    setError("");
    setAgents([]);
    setTransitionNote("Generating code, test strategy, security, checklist and documentation...");
    let context = interactiveContext;

    try {
      for (let index = startIndex; index < interactiveStages.length; index += 1) {
        const stage = interactiveStages[index];
        const stageLabel = stageLabels[stage] || stage;

        const response = await fetch(`${API_BASE_URL}/analyze/step`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ requirement, stage, context, correction: "" }),
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
          throw new Error(data.error || `Failed to generate ${stageLabel}.`);
        }

        context = data.context || context;
        setInteractiveContext(context);
        setDiagramXml(data.diagram || "");

        if (stage === "assemble") {
          setResult(data.content || "");
          setApprovedSections([]);
        }
      }
      setInteractiveStageIndex(interactiveStages.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect to the backend.");
    } finally {
      setLoading(false);
      setTransitionNote(null);
    }
  };

  const approveRequirementSection = async () => {
    const nextIndex = interactiveStageIndex + 1;
    if (result && nextIndex < interactiveStages.length - 1) {
      setApprovedSections((current) => [...current, result]);
    }
    const currentLabel = stageLabels[interactiveStages[interactiveStageIndex]] || "this section";

    // Manual review stays one-by-one through Data Model; once Data Model
    // is approved, run the remaining non-approval stages sequentially.
    if (interactiveStages[interactiveStageIndex] === "data_model") {
      setInteractiveStageIndex(nextIndex);
      // Run the remaining generators sequentially (blocking until done)
      await runRemainingStagesAutomatically(nextIndex);
      return;
    }

    const nextStageName = interactiveStages[Math.min(nextIndex, interactiveStages.length - 1)];
    const nextLabel = stageLabels[nextStageName] || "the next section";
    const slowHint = SLOW_STAGE_HINTS[nextStageName] || "";
    setInteractiveStageIndex(nextIndex);
    setTransitionNote(`Reviewed ${currentLabel}. Moving to ${nextLabel}...${slowHint}`);
    await runRequirementStep(interactiveStages[nextIndex]);
  };

  const correctSection = async (sectionTitle: string, correction: string) => {
    if (activeCapability === "requirement") {
      await runRequirementStep(interactiveStages[interactiveStageIndex], correction);
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
            Amazon Nova Lite
          </div>

          <div className="engine-region">
            AWS eu-west-2
          </div>
        </div>

        <div className="version">
          AI SDLC Assistant · v1.0
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
    <div className="app-shell polished-ui">
      {renderSidebar()}

      <main className={`${result ? "main-content has-results" : !loading ? "main-content home-screen" : "main-content"}${buildSettingsOpen ? " settings-open" : ""}`}>
        <header className="topbar">
          <div className="topbar-left">
            <div className="breadcrumb">
              AI SDLC
              <span>/</span>
              Developer Workspace
            </div>

            <h1>
              BuildPilot Engineering Copilot
            </h1>

            <p>
              Transform requirements and code into
              developer-ready engineering outputs.
            </p>
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

            <div style={{position: 'relative'}}>
              <div className="topbar-avatar" onClick={() => setAvatarOpen((s) => !s)}>{'PG'}</div>
              {avatarOpen && (
                <div className="avatar-menu" role="menu">
                  <button onClick={() => {}} className="avatar-menu-item">Profile</button>
                  <button onClick={() => {}} className="avatar-menu-item">Sign out</button>
                </div>
              )}
            </div>
          </div>

        </header>

        {!result && !loading && !error && (
          <section className="capability-overview" aria-label="BuildPilot capabilities">
            <article>
              <span className="capability-overview-icon"><Sparkles /></span>
              <div><strong>AI-Powered</strong><small>Smart analysis and generation</small></div>
            </article>
            <article>
              <span className="capability-overview-icon"><Layers3 /></span>
              <div><strong>End-to-End SDLC</strong><small>From requirements to delivery</small></div>
            </article>
            <article>
              <span className="capability-overview-icon code"><Code2 /></span>
              <div><strong>Developer Ready</strong><small>Code, tests and documentation</small></div>
            </article>
            <article>
              <span className="capability-overview-icon secure"><ShieldCheck /></span>
              <div><strong>Secure & Reliable</strong><small>Quality controls built in</small></div>
            </article>
          </section>
        )}

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

        <section className={!result && !loading ? "workspace home-workspace" : "workspace"}>
          <div className="workspace-header">
            <div>
              <div className="workspace-heading-icon" aria-hidden="true">
                <FileCog />
              </div>

              <div className="eyebrow">
                DEVELOPER WORKSPACE
              </div>

              <h2>{current.title}</h2>

              <p>{current.subtitle}</p>
            </div>

            <div className="workspace-helper">
              <Lightbulb aria-hidden="true" />
              <span>Describe clearly for better results</span>
            </div>

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
                      onClick={() => setSectionsOpen((s) => ({ ...s, engineering: !s.engineering }))}
                    >
                      <div>
                        <FileCog aria-hidden="true" />
                        <strong>Engineering Standards</strong>
                        <span className="optional-pill">Optional</span>
                      </div>
                      <ChevronDown className={`accordion-chevron ${sectionsOpen.engineering ? 'expanded' : ''}`} />
                    </button>

                    {sectionsOpen.engineering && (
                      <div className="accordion-body">
                        <p>Coding standards, frameworks and project conventions.</p>
                        <label className="upload-btn small">
                          <Plus aria-hidden="true" />
                          Upload documents
                          <input
                            type="file"
                            multiple
                            accept=".txt,.md,.pdf"
                            onChange={(e) => {
                              const files = e.target.files;
                              if (files && files.length) setEngineeringFiles(Array.from(files).map((f) => f.name));
                              if (e.target) e.currentTarget.value = "";
                            }}
                          />
                        </label>
                        {engineeringFiles.length > 0 && (
                          <div className="uploaded-list small">
                            <strong>{engineeringFiles.length} document(s) indexed</strong>
                            <div className="uploaded-names">{engineeringFiles.join(' | ')}</div>
                          </div>
                        )}
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
                            const files = e.target.files;
                            if (files?.length) setDesignFiles(Array.from(files).map((file) => file.name));
                            setDesignUploading(true);
                            window.setTimeout(() => setDesignUploading(false), 600);
                            e.currentTarget.value = "";
                          }} />
                        </label>
                        {designFiles.length > 0 && <div className="uploaded-design-files">{designFiles.join(" · ")}</div>}
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
                  <button className="reset-btn" onClick={() => { setDesignSystemUrl(""); setDesignFiles([]); setEngineeringFiles([]); }}>Reset</button>
                  <button className="done-btn" onClick={() => setBuildSettingsOpen(false)}>Done</button>
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

                {!loading &&
                  !error &&
                  result && (
                    <div className="structured-output">
                      {renderAgentPipeline()}

                      {activeCapability === "requirement" &&
                        interactiveStageIndex >= interactiveStages.length && (
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
                        activeSectionId={
                          interactiveStages[interactiveStageIndex]
                            ? STAGE_SECTION_IDS[interactiveStages[interactiveStageIndex]]
                            // Workflow complete (Data Model approved and the rest
                            // auto-generated): land on Generated Code and let the
                            // per-section Next buttons page through the rest.
                            : STAGE_SECTION_IDS.generate_code
                        }
                        onCorrection={interactiveStageIndex < interactiveStages.length - 1
                          ? correctSection
                          : undefined}
                        onApprove={interactiveStageIndex < interactiveStages.length - 1
                          ? approveRequirementSection
                          : undefined}
                        
                        
                      />
                    </div>
                  )}
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
