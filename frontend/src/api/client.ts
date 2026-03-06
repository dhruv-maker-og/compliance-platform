/** API client for the ComplianceRewind backend. */

import type {
  ChatSendRequest,
  ChatSessionResponse,
  DriftDetectionRequest,
  DriftDetectionResponse,
  DriftScheduleRequest,
  DriftScheduleStatus,
  DriftSnapshotRequest,
  EvidenceCollectionRequest,
  ExplainGapRequest,
  FrameworkComparisonRequest,
  FrameworkComparisonResponse,
  HealthResponse,
  NarrateEvidenceRequest,
  PolicyEnforceRequest,
  PolicyGenerateRequest,
  RegoDebugRequest,
  RegoDebugResponse,
  SessionCreatedResponse,
  WhatIfRequest,
} from "../types";

const API_BASE = "/api";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  evidence: {
    collect: (req: EvidenceCollectionRequest) =>
      request<SessionCreatedResponse>("/evidence/collect", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    report: (sessionId: string) =>
      request<Record<string, unknown>>(`/evidence/report/${sessionId}`),
    cancel: (sessionId: string) =>
      request<{ session_id: string; status: string }>(
        `/evidence/cancel/${sessionId}`,
        { method: "POST" }
      ),
  },

  policy: {
    generate: (req: PolicyGenerateRequest) =>
      request<SessionCreatedResponse>("/policy/generate", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    enforce: (req: PolicyEnforceRequest) =>
      request<SessionCreatedResponse>("/policy/enforce", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    result: (sessionId: string) =>
      request<Record<string, unknown>>(`/policy/result/${sessionId}`),
    cancel: (sessionId: string) =>
      request<{ session_id: string; status: string }>(
        `/policy/cancel/${sessionId}`,
        { method: "POST" }
      ),
  },

  chat: {
    send: (req: ChatSendRequest) =>
      request<ChatSessionResponse>("/chat/send", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    history: (sessionId: string) =>
      request<{ session_id: string; messages: Array<{ role: string; content: string }> }>(
        `/chat/history/${sessionId}`
      ),
    explainGap: (req: ExplainGapRequest) =>
      request<ChatSessionResponse>("/chat/explain-gap", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    whatIf: (req: WhatIfRequest) =>
      request<ChatSessionResponse>("/chat/what-if", {
        method: "POST",
        body: JSON.stringify(req),
      }),
  },

  insights: {
    narrateEvidence: (req: NarrateEvidenceRequest) =>
      request<{ control_id: string; narrative: string; context: Record<string, unknown> }>(
        "/insights/narrate-evidence",
        {
          method: "POST",
          body: JSON.stringify(req),
        }
      ),
    driftDetect: (req: DriftDetectionRequest) =>
      request<DriftDetectionResponse>("/insights/drift-detect", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    setDriftBaseline: (req: DriftSnapshotRequest) =>
      request<{ scope: string; baseline_items: number; status: string }>(
        "/insights/drift/baseline",
        {
          method: "POST",
          body: JSON.stringify(req),
        }
      ),
    setDriftCurrent: (req: DriftSnapshotRequest) =>
      request<{ scope: string; current_items: number; status: string }>(
        "/insights/drift/current",
        {
          method: "POST",
          body: JSON.stringify(req),
        }
      ),
    startDriftSchedule: (req: DriftScheduleRequest) =>
      request<DriftScheduleStatus>("/insights/drift/schedule/start", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    stopDriftSchedule: (scope: string) =>
      request<DriftScheduleStatus>(`/insights/drift/schedule/stop/${scope}`, {
        method: "POST",
      }),
    getDriftScheduleStatus: (scope: string) =>
      request<DriftScheduleStatus>(`/insights/drift/schedule/status/${scope}`),
    runDriftNow: (scope: string) =>
      request<DriftDetectionResponse>(`/insights/drift/schedule/run-now/${scope}`, {
        method: "POST",
      }),
    frameworkCompare: (req: FrameworkComparisonRequest) =>
      request<FrameworkComparisonResponse>("/insights/framework-compare", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    regoDebug: (req: RegoDebugRequest) =>
      request<RegoDebugResponse>("/insights/rego-debug", {
        method: "POST",
        body: JSON.stringify(req),
      }),
  },
};
