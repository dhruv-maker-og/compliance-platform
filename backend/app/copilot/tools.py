"""Copilot SDK tool definitions for compliance workflows.

Exposes the platform's internal tools (evidence_assembler, gap_analyzer,
opa_tester, report_generator) as Copilot SDK tools using the ``@define_tool``
decorator so the Copilot agent can invoke them during sessions.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy import of the decorator so the module can still be imported when the
# SDK package is not installed (tests, linting, etc.).
# ---------------------------------------------------------------------------

try:
    from copilot import define_tool  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    # Provide a no-op fallback so the module doesn't crash on import.
    def define_tool(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
        def _wrapper(fn: Any) -> Any:
            return fn
        if args and callable(args[0]):
            return args[0]
        return _wrapper


# ── Parameter schemas ───────────────────────────────────────────────────


class EvidenceAssemblerParams(BaseModel):
    """Parameters for the evidence_assembler tool."""

    raw_evidence_json: str = Field(
        description=(
            "JSON-encoded dict of raw evidence collected from various "
            "MCP servers. Keys are source identifiers (e.g. 'azure:nsg_rules'), "
            "values are the raw data from those sources."
        ),
    )
    controls_json: str = Field(
        description=(
            "JSON-encoded list of control definitions from controls.json. "
            "Each control has 'id', 'requirement', and 'evidence_sources'."
        ),
    )


class GapAnalyzerParams(BaseModel):
    """Parameters for the gap_analyzer tool."""

    evidence_bundle_json: str = Field(
        description=(
            "JSON-encoded evidence bundle (output of evidence_assembler). "
            "Dict keyed by control ID."
        ),
    )
    controls_json: str = Field(
        description="JSON-encoded list of control definitions from controls.json.",
    )


class OpaEvalParams(BaseModel):
    """Parameters for the opa_eval tool."""

    policy_rego: str = Field(
        description="The Rego policy source code (complete file content).",
    )
    terraform_plan_json: str = Field(
        description=(
            "JSON-encoded Terraform plan output (the result of "
            "'terraform show -json tfplan')."
        ),
    )
    query: str = Field(
        default="data.policy.deny",
        description="OPA query expression (default: data.policy.deny).",
    )


class OpaTestParams(BaseModel):
    """Parameters for the opa_test tool."""

    policy_rego: str = Field(
        description="The Rego policy source code.",
    )
    test_rego: str = Field(
        description="The Rego test file source code.",
    )


class ReportGeneratorParams(BaseModel):
    """Parameters for the report_generator tool (compliance report)."""

    gap_analysis_json: str = Field(
        description="JSON-encoded gap analysis results (output of gap_analyzer).",
    )
    framework: str = Field(
        default="PCI-DSS v4.0",
        description="Compliance framework name.",
    )
    scope: str = Field(
        default="Azure Subscription",
        description="Assessment scope description.",
    )
    report_format: str = Field(
        default="markdown",
        description="Output format: 'markdown' or 'structured'.",
    )


class PolicyReportParams(BaseModel):
    """Parameters for the report_generator tool (policy enforcement report)."""

    opa_result_json: str = Field(
        description="JSON-encoded OPA eval result (output of opa_eval).",
    )
    policy_name: str = Field(
        default="unnamed",
        description="Name of the policy evaluated.",
    )
    terraform_path: str = Field(
        default="",
        description="Path to the Terraform configuration evaluated.",
    )


# ── Tool implementations ────────────────────────────────────────────────


@define_tool(description=(
    "Assemble raw evidence into a structured evidence bundle organised "
    "by compliance control ID. Call this after collecting evidence from "
    "Azure, GitHub, Entra ID, and Purview MCP servers."
))
async def evidence_assembler_tool(params: EvidenceAssemblerParams) -> str:
    """Copilot SDK wrapper around :func:`evidence_assembler`."""
    from app.tools.evidence_assembler import evidence_assembler

    raw_evidence = json.loads(params.raw_evidence_json)
    controls = json.loads(params.controls_json)
    result = await evidence_assembler(raw_evidence=raw_evidence, controls=controls)
    return json.dumps(result, default=str)


@define_tool(description=(
    "Run deterministic pass/fail gap analysis against compliance "
    "controls. Uses code-based checks (not LLM reasoning) as required "
    "by AGENTS.md. Returns assessments with status, gaps, and "
    "recommendations for each control."
))
async def gap_analyzer_tool(params: GapAnalyzerParams) -> str:
    """Copilot SDK wrapper around :func:`gap_analyzer`."""
    from app.tools.gap_analyzer import gap_analyzer

    evidence_bundle = json.loads(params.evidence_bundle_json)
    controls = json.loads(params.controls_json)
    result = await gap_analyzer(evidence_bundle=evidence_bundle, controls=controls)
    return json.dumps(result, default=str)


@define_tool(description=(
    "Evaluate an OPA Rego policy against a Terraform plan JSON. "
    "Returns a list of violations. Only 'opa eval' and 'opa test' "
    "are whitelisted shell commands."
))
async def opa_eval_tool(params: OpaEvalParams) -> str:
    """Copilot SDK wrapper around :func:`opa_eval`."""
    from app.tools.opa_tester import opa_eval

    plan = json.loads(params.terraform_plan_json)
    result = await opa_eval(
        policy_rego=params.policy_rego,
        terraform_plan_json=plan,
        query=params.query,
    )
    return json.dumps(result, default=str)


@define_tool(description=(
    "Run OPA unit tests for a Rego policy. Provide the policy source "
    "and a corresponding test file. Returns test pass/fail results."
))
async def opa_test_tool(params: OpaTestParams) -> str:
    """Copilot SDK wrapper around :func:`opa_test`.

    Writes the policy and test Rego strings to a temporary directory
    and passes that directory to ``opa_test()``.
    """
    from app.tools.opa_tester import opa_test

    with tempfile.TemporaryDirectory(prefix="opa_test_") as tmpdir:
        policy_path = Path(tmpdir) / "policy.rego"
        test_path = Path(tmpdir) / "policy_test.rego"
        policy_path.write_text(params.policy_rego, encoding="utf-8")
        test_path.write_text(params.test_rego, encoding="utf-8")

        result = await opa_test(policy_dir=tmpdir)

    return json.dumps(result, default=str)


@define_tool(description=(
    "Generate a Markdown compliance report from gap analysis results. "
    "Includes executive summary, per-control assessments, and "
    "remediation recommendations."
))
async def compliance_report_tool(params: ReportGeneratorParams) -> str:
    """Copilot SDK wrapper around :func:`generate_compliance_report`."""
    from app.tools.report_generator import generate_compliance_report

    gap_analysis = json.loads(params.gap_analysis_json)
    result = await generate_compliance_report(
        gap_analysis=gap_analysis,
        framework=params.framework,
        scope=params.scope,
        report_format=params.report_format,
    )
    return json.dumps(result, default=str)


@define_tool(description=(
    "Generate a policy enforcement report from OPA evaluation results. "
    "Lists violations, affected resources, and (optionally) fix descriptions."
))
async def policy_report_tool(params: PolicyReportParams) -> str:
    """Copilot SDK wrapper around :func:`generate_policy_report`."""
    from app.tools.report_generator import generate_policy_report

    opa_result = json.loads(params.opa_result_json)
    result = await generate_policy_report(
        opa_result=opa_result,
        policy_name=params.policy_name,
        terraform_path=params.terraform_path,
    )
    return json.dumps(result, default=str)


# ── Helper: collect all tools into a list ───────────────────────────────


def get_compliance_tools() -> list[Any]:
    """Return all compliance-related Copilot SDK tools.

    Use this when creating a Copilot session:

        session = await client.create_session({
            "model": "gpt-4.1",
            "tools": get_compliance_tools(),
        })
    """
    return [
        evidence_assembler_tool,
        gap_analyzer_tool,
        opa_eval_tool,
        opa_test_tool,
        compliance_report_tool,
        policy_report_tool,
    ]
