export type AnalysisStatus = "NOT_STARTED" | "SCANNING" | "INDEXING" | "ANALYZING" | "COMPLETED" | "FAILED";
export type RepositorySource = { type: "git"; url: string } | { type: "local"; path: string };

export interface Evidence {
  repository: string;
  file: string;
  symbol?: string;
  snippet?: string;
  lineStart?: number;
  lineEnd?: number;
  evidenceType?: "CODE" | "CONFIGURATION" | "DATABASE" | "API" | "TEST" | "COMMENT";
}

export interface Overview {
  repositories: number | null;
  services: number | null;
  classes: number | null;
  apis: number | null;
  databaseTables: number | null;
  externalIntegrations: number | null;
  scheduledJobs: number | null;
}

export interface ArchitectureNode {
  id: string;
  name: string;
  type: string;
  repository?: string;
  evidence?: Evidence[];
}

export interface ArchitectureEdge {
  id?: string;
  source: string;
  target: string;
  relationship?: string;
  relationshipType?: string;
  sourceRepository?: string;
  sourceSymbol?: string;
  targetRepository?: string;
  targetSymbol?: string;
  evidence?: Evidence[];
}

export interface Architecture { nodes: ArchitectureNode[]; edges: ArchitectureEdge[] }
export interface BusinessRule {
  id: string;
  title: string;
  description: string;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  evidence: Evidence[];
}
export interface ApplicationFlow extends Architecture {
  id: string;
  title?: string;
  name?: string;
  description?: string;
  evidence?: Evidence[];
}
export interface AnalysisSummary {
  analysisId: string;
  name: string;
  repositories: RepositorySource[];
  status: AnalysisStatus;
  createdAt: string;
  updatedAt: string;
}
export interface Analysis extends AnalysisSummary {
  progress: { step: number; totalSteps: number; message: string; percent: number };
  overview?: Overview | null;
  architecture?: Architecture;
  businessRules?: BusinessRule[];
  flows?: ApplicationFlow[];
  facts?: Array<{ kind: string; name: string; repository: string; description?: string; evidence: Evidence[] }>;
  narratives?: Record<string, string>;
  insights?: { summary: string; key_risks: string[]; modernization_priorities: string[]; open_questions: string[] } | null;
  limitations?: string[];
  engine?: string | { name?: string; mode?: string;[key: string]: unknown };
  error?: string | null;
}

export const DOCUMENT_TYPES = [
  ["application_overview", "Application Overview"],
  ["system_architecture", "System Architecture"],
  ["component_documentation", "Component Documentation"],
  ["api_documentation", "API Documentation"],
  ["database_documentation", "Database Documentation"],
  ["service_dependencies", "Service Dependencies"],
  ["external_integrations", "External Integrations"],
  ["scheduled_jobs", "Scheduled Jobs"],
  ["business_rules", "Business Rules"],
  ["application_flows", "Application Flows"],
  ["security_overview", "Security Overview"],
  ["technical_debt", "Technical Debt"],
] as const;
export type DocumentType = typeof DOCUMENT_TYPES[number][0];
export interface GeneratedDocument {
  type: DocumentType; title: string; content: string; evidence: Evidence[];
  revision?: string; generationMode?: "ai-authored" | "source-summary"; warning?: string;
  generatedAt?: string; model?: string; wordCount?: number; readingMinutes?: number;
}
export interface ConfluenceStatus { configured: boolean; baseUrl: string; spaceKey: string; parentPageId: string; missing: string[]; configurationError?: string }
export interface PublishResult {
  pages: { type: DocumentType; title: string; url: string; action: string }[];
  errors: { type: DocumentType; title: string; error: string }[];
}
export type DetailView = "overview" | "application-overview" | "architecture" | "documentation" | "business-rules" | "flows" | "chat" | "recent";
export const isRunning = (status?: AnalysisStatus) => status === "NOT_STARTED" || status === "SCANNING" || status === "INDEXING" || status === "ANALYZING";
