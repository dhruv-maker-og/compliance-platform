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


def _repo_root() -> Path:
    """Return repository root path based on this file location."""
    return Path(__file__).resolve().parents[3]

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


# ── New SDK tools: explain, narrate, what-if ────────────────────────────


class ExplainGapParams(BaseModel):
    """Parameters for the explain_gap tool."""

    control_id: str = Field(description="The control ID that failed (e.g. '8.3').")
    requirement: str = Field(description="The control requirement text.")
    gaps: str = Field(
        description="JSON-encoded list of gap descriptions from the gap_analyzer.",
    )
    recommendations: str = Field(
        default="[]",
        description="JSON-encoded list of recommendations from the gap_analyzer.",
    )
    evidence_summary: str = Field(
        default="",
        description="Brief summary of the evidence that was collected for this control.",
    )


class NarrateEvidenceParams(BaseModel):
    """Parameters for the narrate_evidence tool."""

    control_id: str = Field(description="Control ID being narrated.")
    requirement: str = Field(description="Control requirement text.")
    evidence_items_json: str = Field(
        description=(
            "JSON-encoded list of evidence items for this control. "
            "Each item has 'source', 'data_type', 'data', 'collected_at'."
        ),
    )
    assessment_status: str = Field(
        description="Assessment status: 'passed', 'gap', or 'not_assessed'.",
    )


class PolicySuiteEvalParams(BaseModel):
    """Parameters for the policy_suite_eval tool."""

    terraform_plan_json: str = Field(
        description="JSON-encoded Terraform plan to evaluate.",
    )
    policies_dir: str = Field(
        default="skills/policy-enforcement/rego-examples",
        description="Directory containing .rego policy files.",
    )


class DriftDetectionParams(BaseModel):
    """Parameters for the drift_detection tool."""

    baseline_assessments_json: str = Field(
        description="JSON-encoded list of baseline control assessments.",
    )
    current_assessments_json: str = Field(
        description="JSON-encoded list of current control assessments.",
    )


class FrameworkCompareParams(BaseModel):
    """Parameters for the framework_compare tool."""

    frameworks_json: str = Field(
        description="JSON-encoded list of framework IDs (e.g. ['pci-dss', 'soc2']).",
    )


class RegoDebuggerParams(BaseModel):
    """Parameters for the rego_debugger tool."""

    policy_rego: str = Field(description="The Rego policy source code.")
    terraform_plan_json: str = Field(description="JSON-encoded Terraform plan to evaluate.")
    query: str = Field(default="data.policy.deny", description="OPA query expression.")


@define_tool(description=(
    "Explain WHY a compliance control failed and provide step-by-step "
    "remediation guidance. Include specific Azure portal steps, CLI commands, "
    "and estimated effort. Use this when a user asks 'why did this fail?' "
    "or 'how do I fix this gap?'."
))
async def explain_gap_tool(params: ExplainGapParams) -> str:
    """Return structured remediation guidance for a failed control."""
    gaps = json.loads(params.gaps)
    recommendations = json.loads(params.recommendations)

    # Build a structured explanation that the LLM can enrich
    explanation = {
        "control_id": params.control_id,
        "requirement": params.requirement,
        "gaps_found": gaps,
        "recommendations": recommendations,
        "evidence_summary": params.evidence_summary,
        "remediation_steps": [
            f"Address gap: {g}" for g in gaps
        ],
    }
    return json.dumps(explanation, default=str)


@define_tool(description=(
    "Generate auditor-facing prose narration for a compliance control. "
    "Takes structured evidence and produces a professional narrative "
    "paragraph suitable for audit reports. The narrative describes "
    "what evidence was found, when it was collected, and whether the "
    "control passes. Use this to produce human-readable report sections."
))
async def narrate_evidence_tool(params: NarrateEvidenceParams) -> str:
    """Return a prose narration of the evidence for a control."""
    items = json.loads(params.evidence_items_json)

    narration_context = {
        "control_id": params.control_id,
        "requirement": params.requirement,
        "status": params.assessment_status,
        "evidence_count": len(items),
        "sources": list({item.get("source", "unknown") for item in items}),
        "data_types": list({item.get("data_type", "unknown") for item in items}),
        "collection_dates": [
            item.get("collected_at", "") for item in items if item.get("collected_at")
        ],
    }
    return json.dumps(narration_context, default=str)


@define_tool(description=(
    "Evaluate ALL active Rego policies against a Terraform plan. "
    "Scans the policies directory for .rego files, runs opa eval "
    "for each policy, and returns a consolidated list of violations "
    "grouped by policy. Use this for what-if simulation before "
    "deploying infrastructure."
))
async def policy_suite_eval_tool(params: PolicySuiteEvalParams) -> str:
    """Run all policies against a plan and return consolidated violations."""
    from app.tools.opa_tester import opa_eval

    plan = json.loads(params.terraform_plan_json)
    policies_dir = Path(params.policies_dir)
    if not policies_dir.is_absolute():
        policies_dir = _repo_root() / policies_dir

    results: list[dict[str, Any]] = []

    if policies_dir.exists():
        for rego_file in sorted(policies_dir.glob("*.rego")):
            if rego_file.name.endswith("_test.rego"):
                continue
            policy_rego = rego_file.read_text(encoding="utf-8")
            try:
                eval_result = await opa_eval(
                    policy_rego=policy_rego,
                    terraform_plan_json=plan,
                )
                results.append({
                    "policy_file": rego_file.name,
                    "violations": eval_result.get("violations", []),
                    "passed": eval_result.get("passed", True),
                })
            except Exception as exc:
                results.append({
                    "policy_file": rego_file.name,
                    "error": str(exc),
                    "passed": False,
                })

    total_violations = sum(len(r.get("violations", [])) for r in results)

    return json.dumps({
        "policies_evaluated": len(results),
        "total_violations": total_violations,
        "all_passed": total_violations == 0,
        "results": results,
    }, default=str)


@define_tool(description=(
    "Detect drift by comparing baseline and current control assessments. "
    "Returns regressions, improvements, and changed controls for continuous "
    "compliance monitoring."
))
async def drift_detection_tool(params: DriftDetectionParams) -> str:
    """Compare baseline vs current assessments and return drift summary."""
    baseline = json.loads(params.baseline_assessments_json)
    current = json.loads(params.current_assessments_json)

    baseline_map = {item.get("control_id"): item for item in baseline}
    current_map = {item.get("control_id"): item for item in current}
    control_ids = sorted(set(baseline_map.keys()) | set(current_map.keys()))

    changed_controls: list[dict[str, Any]] = []
    regressions = 0
    improvements = 0

    for control_id in control_ids:
        old_status = (baseline_map.get(control_id) or {}).get("status", "not_assessed")
        new_status = (current_map.get(control_id) or {}).get("status", "not_assessed")

        if old_status == new_status:
            continue

        if old_status == "passed" and new_status in {"failed", "gap"}:
            change_type = "regression"
            regressions += 1
        elif old_status in {"failed", "gap", "not_assessed"} and new_status == "passed":
            change_type = "improvement"
            improvements += 1
        else:
            change_type = "changed"

        changed_controls.append({
            "control_id": control_id,
            "baseline_status": old_status,
            "current_status": new_status,
            "change_type": change_type,
        })

    return json.dumps({
        "total_controls_compared": len(control_ids),
        "drift_count": len(changed_controls),
        "regressions": regressions,
        "improvements": improvements,
        "changed_controls": changed_controls,
    }, default=str)


@define_tool(description=(
    "Compare multiple compliance frameworks by loading controls.json from each "
    "framework skill and identifying common/unique control IDs."
))
async def framework_compare_tool(params: FrameworkCompareParams) -> str:
    """Compare controls across frameworks based on control IDs."""
    frameworks = json.loads(params.frameworks_json)
    base_path = _repo_root() / "skills"

    found: dict[str, list[str]] = {}
    not_found: list[str] = []

    for framework in frameworks:
        controls_path = base_path / framework / "controls.json"
        if not controls_path.exists():
            not_found.append(framework)
            continue

        controls_data = json.loads(controls_path.read_text(encoding="utf-8"))
        ids = [str(c.get("id", "")) for c in controls_data.get("controls", []) if c.get("id")]
        found[framework] = sorted(set(ids))

    if found:
        common_ids = sorted(set.intersection(*(set(ids) for ids in found.values())))
    else:
        common_ids = []

    unique_control_ids: dict[str, list[str]] = {}
    for framework, ids in found.items():
        others = set().union(*(set(v) for k, v in found.items() if k != framework))
        unique_control_ids[framework] = sorted([cid for cid in ids if cid not in others])

    return json.dumps({
        "frameworks_requested": frameworks,
        "frameworks_found": sorted(found.keys()),
        "frameworks_missing": sorted(not_found),
        "total_controls_by_framework": {k: len(v) for k, v in found.items()},
        "common_control_ids": common_ids,
        "unique_control_ids": unique_control_ids,
    }, default=str)


@define_tool(description=(
    "Run interactive Rego debugging using 'opa eval --explain full' and return "
    "both violations and explain trace output for root-cause analysis."
))
async def rego_debugger_tool(params: RegoDebuggerParams) -> str:
    """Return violations and explain trace for a Rego policy evaluation."""
    from app.tools.opa_tester import opa_eval, opa_eval_explain

    plan = json.loads(params.terraform_plan_json)
    eval_result = await opa_eval(
        policy_rego=params.policy_rego,
        terraform_plan_json=plan,
        query=params.query,
    )
    explain_result = await opa_eval_explain(
        policy_rego=params.policy_rego,
        terraform_plan_json=plan,
        query=params.query,
        explain_level="full",
    )

    return json.dumps({
        "passed": eval_result.get("passed", False),
        "violations": eval_result.get("violations", []),
        "explain_trace": explain_result.get("explain_trace", ""),
        "error": eval_result.get("error") or explain_result.get("error"),
    }, default=str)


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
        explain_gap_tool,
        narrate_evidence_tool,
        policy_suite_eval_tool,
        drift_detection_tool,
        framework_compare_tool,
        rego_debugger_tool,
    ]
