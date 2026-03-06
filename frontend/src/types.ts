/** Shared TypeScript types for the frontend. */

export type SessionStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type ControlStatus = "passed" | "gap" | "not_assessed";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface AgentStep {
  step_number: number;
  action: string;
  detail: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: Record<string, unknown>;
  status: string;
  timestamp: string;
}

export interface SessionCreatedResponse {
  session_id: string;
  status: SessionStatus;
  stream_url: string;
}

export interface EvidenceCollectionRequest {
  framework: string;
  scope: string;
  controls?: string[];
  azure_subscription_id?: string;
  github_org?: string;
  github_repo?: string;
}

export interface PolicyGenerateRequest {
  intent: string;
  target_resources: string[];
  severity?: Severity;
}

export interface PolicyEnforceRequest {
  policy_path: string;
  terraform_plan_path: string;
  auto_fix?: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  timestamp: string;
  components: {
    agent_engine: string;
    skills_loaded: number;
    active_sessions: number;
  };
}

// Chat types

export interface ChatMessage {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  timestamp?: string;
  tool_name?: string;
}

export interface ChatSendRequest {
  message: string;
  session_id?: string;
}

export interface ChatSessionResponse {
  session_id: string;
  stream_url: string;
}

export interface ExplainGapRequest {
  control_id: string;
  assessment_json: string;
  evidence_json?: string;
}

export interface WhatIfRequest {
  terraform_plan_json: string;
}

export interface ComplianceSummary {
  total_controls: number;
  passed: number;
  gaps: number;
  not_assessed: number;
  compliance_score: number;
}

export interface ControlAssessment {
  control_id: string;
  requirement: string;
  status: ControlStatus;
  gaps: string[];
  recommendations: string[];
  check_results: {
    check: string;
    passed: boolean;
    detail: string;
  }[];
}
