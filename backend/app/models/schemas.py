"""Pydantic models for the compliance platform API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────────

class SessionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ControlStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    GAP = "gap"
    NOT_APPLICABLE = "not_applicable"
    NOT_ASSESSED = "not_assessed"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AgentMode(str, Enum):
    COMPLIANCE = "compliance"
    POLICY = "policy"
    CHAT = "chat"


# ── Evidence Collection ─────────────────────────────────────────────────────

class EvidenceCollectionRequest(BaseModel):
    """Request to collect compliance evidence."""
    framework: str = Field(default="pci-dss", description="Compliance framework ID")
    controls: list[str] | str = Field(
        default="all",
        description="List of control IDs to assess, or 'all'",
    )
    target_repos: list[str] = Field(
        default_factory=list,
        description="GitHub repos to scan (org/repo format)",
    )
    target_subscription_id: Optional[str] = Field(
        default=None,
        description="Azure subscription to scan (defaults to configured subscription)",
    )


class EvidenceItem(BaseModel):
    """A single piece of collected evidence."""
    control_id: str
    source: str = Field(description="Tool/MCP that provided this evidence")
    data_type: str = Field(description="Type of evidence (config, document, log, etc.)")
    data: Any = Field(description="The evidence data")
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    summary: str = Field(default="", description="Human-readable summary")


class ControlAssessment(BaseModel):
    """Assessment result for a single control."""
    control_id: str
    requirement: str
    status: ControlStatus
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    details: str = ""


class EvidenceReport(BaseModel):
    """Full compliance evidence report."""
    framework: str
    framework_version: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    assessments: list[ControlAssessment] = Field(default_factory=list)
    summary: ReportSummary | None = None


class ReportSummary(BaseModel):
    """Executive summary of a compliance report."""
    total_controls: int = 0
    passed: int = 0
    failed: int = 0
    gaps: int = 0
    not_applicable: int = 0
    not_assessed: int = 0
    compliance_score: float = Field(
        default=0.0,
        description="Percentage of assessed controls that passed",
    )
    executive_summary: str = ""
    top_risks: list[str] = Field(default_factory=list)


# ── Policy Generation & Enforcement ────────────────────────────────────────

class PolicyGenerateRequest(BaseModel):
    """Request to generate a policy from natural language."""
    intent: str = Field(description="Natural-language policy requirement")
    target: str = Field(default="terraform", description="Target IaC platform")
    severity: Severity = Severity.HIGH
    framework: Optional[str] = Field(default=None, description="Associated compliance framework")
    controls: list[str] = Field(default_factory=list, description="Associated control IDs")


class PolicyGenerateResponse(BaseModel):
    """Result of policy generation."""
    session_id: str
    policy_content: str = Field(description="Generated Rego policy file content")
    test_content: str = Field(description="Generated Rego test file content")
    policy_path: str = Field(description="Suggested path for the policy file")
    test_path: str = Field(description="Suggested path for the test file")
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyEnforceRequest(BaseModel):
    """Request to enforce a policy against infrastructure code."""
    policy_path: str = Field(description="Path to the Rego policy file in the policy repo")
    repo: str = Field(description="GitHub repo to enforce against (org/repo format)")
    branch: str = Field(default="main", description="Branch to scan")
    auto_fix: bool = Field(default=False, description="Automatically create fix PRs")
    plan_json_path: Optional[str] = Field(
        default=None,
        description="Path to a Terraform plan JSON (if pre-generated)",
    )


class PolicyViolation(BaseModel):
    """A single policy violation found during enforcement."""
    resource_name: str
    resource_type: str
    violation_message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    severity: Severity = Severity.HIGH
    fix_applied: bool = False
    fix_description: Optional[str] = None


class PolicyEnforceResult(BaseModel):
    """Result of policy enforcement."""
    session_id: str
    policy_path: str
    repo: str
    branch: str
    violations: list[PolicyViolation] = Field(default_factory=list)
    total_resources_scanned: int = 0
    compliant_resources: int = 0
    pr_url: Optional[str] = Field(default=None, description="URL of fix PR if created")
    summary: str = ""


# ── Agent Session ───────────────────────────────────────────────────────────

class AgentStep(BaseModel):
    """A single step executed by the agent."""
    step_number: int
    action: str = Field(description="Tool name or action type")
    description: str
    status: str = Field(default="pending", description="pending | running | completed | failed")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_summary: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentSession(BaseModel):
    """Tracks the state of an agent session."""
    session_id: str
    mode: AgentMode
    status: SessionStatus = SessionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    steps: list[AgentStep] = Field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── API Responses ───────────────────────────────────────────────────────────

class SessionCreatedResponse(BaseModel):
    """Response when a new session is created."""
    session_id: str
    status: SessionStatus
    stream_url: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "0.1.0"
    environment: str = ""
    copilot_cli_available: bool = False
    mcp_servers_configured: int = 0
    skills_loaded: list[str] = Field(default_factory=list)


# ── Chat ────────────────────────────────────────────────────────────────────

class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """A single chat message."""
    role: ChatRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_name: Optional[str] = None
    tool_result: Optional[dict[str, Any]] = None


class ChatSendRequest(BaseModel):
    """Request to send a chat message."""
    message: str = Field(description="User message text")
    session_id: Optional[str] = Field(
        default=None,
        description="Existing chat session ID. Omit to start a new conversation.",
    )


class ChatSessionResponse(BaseModel):
    """Response after sending a chat message."""
    session_id: str
    stream_url: str


class ExplainGapRequest(BaseModel):
    """Request to explain a specific compliance gap."""
    control_id: str = Field(description="Control ID to explain (e.g. '8.3')")
    assessment_json: str = Field(description="JSON-encoded ControlAssessment")
    evidence_json: str = Field(default="{}", description="JSON-encoded evidence bundle for this control")


class WhatIfRequest(BaseModel):
    """Request for what-if policy simulation."""
    terraform_plan_json: str = Field(description="Terraform plan JSON content")
