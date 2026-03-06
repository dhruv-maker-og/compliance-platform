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

export interface NarrateEvidenceRequest {
  control_id: string;
  requirement: string;
  assessment_status: ControlStatus;
  evidence_items_json: string;
}

export interface DriftDetectionRequest {
  baseline_assessments_json: string;
  current_assessments_json: string;
  scope?: string;
}

export interface DriftSnapshotRequest {
  scope?: string;
  assessments_json: string;
}

export interface DriftScheduleRequest {
  scope?: string;
  interval_seconds: number;
}

export interface DriftItem {
  control_id: string;
  baseline_status: string;
  current_status: string;
  change_type: "regression" | "improvement" | "changed";
  details?: string;
}

export interface DriftDetectionResponse {
  scope: string;
  total_controls_compared: number;
  drift_count: number;
  regressions: number;
  improvements: number;
  changed_controls: DriftItem[];
}

export interface DriftScheduleStatus {
  scope: string;
  running: boolean;
  interval_seconds?: number | null;
  has_baseline: boolean;
  has_current: boolean;
  last_run_at?: string | null;
  last_result?: DriftDetectionResponse | null;
}

export interface FrameworkComparisonRequest {
  frameworks: string[];
}

export interface FrameworkComparisonResponse {
  frameworks_requested: string[];
  frameworks_found: string[];
  total_controls_by_framework: Record<string, number>;
  common_control_ids: string[];
  unique_control_ids: Record<string, string[]>;
}

export interface RegoDebugRequest {
  policy_rego: string;
  terraform_plan_json: string;
  query?: string;
}

export interface RegoDebugResponse {
  passed: boolean;
  violations: Array<Record<string, unknown>>;
  explain_trace: string;
  summary: string;
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
