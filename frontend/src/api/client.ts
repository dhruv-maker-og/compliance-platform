/** API client for the ComplianceRewind backend. */

import type {
  ChatSendRequest,
  ChatSessionResponse,
  EvidenceCollectionRequest,
  ExplainGapRequest,
  HealthResponse,
  PolicyEnforceRequest,
  PolicyGenerateRequest,
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
};
