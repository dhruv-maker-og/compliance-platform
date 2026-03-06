"""Report Generator Tool — produces structured compliance reports.

Generates Markdown compliance reports from gap analysis results. Supports
executive summary, detailed control assessments, and remediation tracking.
"""

from __future__ import annotations

import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def generate_compliance_report(
    gap_analysis: dict[str, Any],
    *,
    framework: str = "PCI-DSS v4.0",
    scope: str = "Azure Subscription",
    report_format: str = "markdown",
) -> dict[str, Any]:
    """Generate a compliance report from gap analysis results.

    Args:
        gap_analysis: Output from gap_analyzer (assessments + summary).
        framework: Compliance framework name.
        scope: Assessment scope description.
        report_format: Output format ("markdown" or "structured").

    Returns:
        Dict with "report" (Markdown string or structured data) and metadata.
    """
    logger.info(
        "report_generation_start",
        framework=framework,
        format=report_format,
    )

    assessments = gap_analysis.get("assessments", [])
    summary = gap_analysis.get("summary", {})
    timestamp = datetime.datetime.now(datetime.timezone.utc)

    metadata = {
        "framework": framework,
        "scope": scope,
        "generated_at": timestamp.isoformat(),
        "total_controls": summary.get("total_controls", 0),
        "compliance_score": summary.get("compliance_score", 0.0),
    }

    if report_format == "structured":
        report = _build_structured_report(assessments, summary, metadata)
    else:
        report = _build_markdown_report(assessments, summary, metadata)

    logger.info(
        "report_generation_complete",
        format=report_format,
        controls=len(assessments),
    )

    return {
        "report": report,
        "metadata": metadata,
    }


async def generate_policy_report(
    opa_result: dict[str, Any],
    *,
    policy_name: str = "unnamed",
    terraform_path: str = "",
) -> dict[str, Any]:
    """Generate a policy enforcement report from OPA eval results.

    Args:
        opa_result: Output from opa_tester (violations, passed, output).
        policy_name: Name of the policy evaluated.
        terraform_path: Path to the Terraform plan evaluated.

    Returns:
        Dict with "report" string and metadata.
    """
    logger.info("policy_report_start", policy=policy_name)

    violations = opa_result.get("violations", [])
    passed = opa_result.get("passed", False)
    error = opa_result.get("error")
    timestamp = datetime.datetime.now(datetime.timezone.utc)

    lines: list[str] = []
    lines.append(f"# Policy Enforcement Report: {policy_name}")
    lines.append("")
    lines.append(f"**Generated:** {timestamp.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Terraform Path:** `{terraform_path}`")
    lines.append(f"**Status:** {'✅ PASSED' if passed else '❌ VIOLATIONS FOUND'}")
    lines.append("")

    if error:
        lines.append("## Error")
        lines.append("")
        lines.append(f"```\n{error}\n```")
        lines.append("")

    if violations:
        lines.append(f"## Violations ({len(violations)})")
        lines.append("")
        lines.append("| # | Severity | Resource | Message |")
        lines.append("|---|----------|----------|---------|")

        for i, v in enumerate(violations, 1):
            sev = v.get("severity", "high").upper()
            resource = v.get("resource", "—")
            msg = v.get("message", "—")
            lines.append(f"| {i} | {sev} | `{resource}` | {msg} |")

        lines.append("")
        lines.append("### Remediation Steps")
        lines.append("")
        for i, v in enumerate(violations, 1):
            lines.append(f"{i}. Fix: {v.get('message', 'Review configuration')}")
        lines.append("")
    else:
        lines.append("## Results")
        lines.append("")
        lines.append("No policy violations detected. All resources comply.")
        lines.append("")

    report = "\n".join(lines)

    return {
        "report": report,
        "metadata": {
            "policy_name": policy_name,
            "terraform_path": terraform_path,
            "generated_at": timestamp.isoformat(),
            "violation_count": len(violations),
            "passed": passed,
        },
    }


def _build_markdown_report(
    assessments: list[dict[str, Any]],
    summary: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    """Build a Markdown compliance report."""
    lines: list[str] = []

    # Title
    lines.append(f"# {metadata['framework']} Compliance Assessment Report")
    lines.append("")

    # Metadata
    lines.append("## Report Information")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| **Framework** | {metadata['framework']} |")
    lines.append(f"| **Scope** | {metadata['scope']} |")
    lines.append(f"| **Generated** | {metadata['generated_at'][:19]} UTC |")
    lines.append(f"| **Compliance Score** | {summary.get('compliance_score', 0)}% |")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    score = summary.get("compliance_score", 0)
    passed = summary.get("passed", 0)
    gaps = summary.get("gaps", 0)
    not_assessed = summary.get("not_assessed", 0)
    total = summary.get("total_controls", 0)

    risk_level = _risk_level(score)
    lines.append(
        f"This assessment evaluated **{total}** controls under the "
        f"**{metadata['framework']}** framework. The overall compliance "
        f"score is **{score}%** ({risk_level} risk)."
    )
    lines.append("")

    # Summary table
    lines.append("| Status | Count | Percentage |")
    lines.append("|--------|-------|------------|")
    assessed = passed + gaps
    lines.append(
        f"| ✅ Passed | {passed} | "
        f"{(passed/total*100) if total else 0:.0f}% |"
    )
    lines.append(
        f"| ❌ Gaps | {gaps} | "
        f"{(gaps/total*100) if total else 0:.0f}% |"
    )
    lines.append(
        f"| ⚪ Not Assessed | {not_assessed} | "
        f"{(not_assessed/total*100) if total else 0:.0f}% |"
    )
    lines.append(f"| **Total** | **{total}** | **100%** |")
    lines.append("")

    # Gaps Requiring Attention
    gap_assessments = [a for a in assessments if a.get("status") == "gap"]
    if gap_assessments:
        lines.append("## Gaps Requiring Remediation")
        lines.append("")

        for ga in gap_assessments:
            lines.append(f"### {ga['control_id']}: {ga['requirement']}")
            lines.append("")

            lines.append("**Gaps:**")
            for gap in ga.get("gaps", []):
                lines.append(f"- {gap}")
            lines.append("")

            lines.append("**Recommendations:**")
            for rec in ga.get("recommendations", []):
                lines.append(f"- {rec}")
            lines.append("")

    # Passed Controls
    passed_assessments = [a for a in assessments if a.get("status") == "passed"]
    if passed_assessments:
        lines.append("## Passed Controls")
        lines.append("")
        lines.append("| Control ID | Requirement |")
        lines.append("|-----------|-------------|")
        for pa in passed_assessments:
            lines.append(f"| {pa['control_id']} | {pa['requirement']} |")
        lines.append("")

    # Not Assessed
    na_assessments = [a for a in assessments if a.get("status") == "not_assessed"]
    if na_assessments:
        lines.append("## Not Assessed Controls")
        lines.append("")
        lines.append("| Control ID | Requirement | Reason |")
        lines.append("|-----------|-------------|--------|")
        for na in na_assessments:
            reason = ", ".join(na.get("gaps", ["No evidence collected"]))
            lines.append(f"| {na['control_id']} | {na['requirement']} | {reason} |")
        lines.append("")

    # Detailed Check Results
    lines.append("## Detailed Check Results")
    lines.append("")

    for assessment in assessments:
        lines.append(f"### {assessment['control_id']}")
        lines.append("")
        status_icon = {
            "passed": "✅",
            "gap": "❌",
            "not_assessed": "⚪",
        }.get(assessment["status"], "❓")
        lines.append(f"**Status:** {status_icon} {assessment['status'].upper()}")
        lines.append(f"**Requirement:** {assessment['requirement']}")
        lines.append("")

        crs = assessment.get("check_results", [])
        if crs:
            lines.append("| Check | Result | Detail |")
            lines.append("|-------|--------|--------|")
            for cr in crs:
                icon = "✅" if cr["passed"] else "❌"
                lines.append(f"| {cr['check']} | {icon} | {cr['detail']} |")
            lines.append("")

    # Appendix
    lines.append("---")
    lines.append("")
    lines.append(
        "*Report generated by ComplianceRewind & Policy Enforcer platform. "
        "This report is generated from automated evidence collection and "
        "deterministic analysis. Manual review is recommended for all gaps.*"
    )

    return "\n".join(lines)


def _build_structured_report(
    assessments: list[dict[str, Any]],
    summary: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Build a structured JSON-serializable report."""
    gap_assessments = [a for a in assessments if a.get("status") == "gap"]
    passed_assessments = [a for a in assessments if a.get("status") == "passed"]
    na_assessments = [a for a in assessments if a.get("status") == "not_assessed"]

    return {
        "metadata": metadata,
        "summary": {
            **summary,
            "risk_level": _risk_level(summary.get("compliance_score", 0)),
        },
        "gaps": [
            {
                "control_id": a["control_id"],
                "requirement": a["requirement"],
                "gaps": a.get("gaps", []),
                "recommendations": a.get("recommendations", []),
                "check_results": a.get("check_results", []),
            }
            for a in gap_assessments
        ],
        "passed": [
            {
                "control_id": a["control_id"],
                "requirement": a["requirement"],
            }
            for a in passed_assessments
        ],
        "not_assessed": [
            {
                "control_id": a["control_id"],
                "requirement": a["requirement"],
                "reason": ", ".join(a.get("gaps", ["No evidence collected"])),
            }
            for a in na_assessments
        ],
        "detailed_results": assessments,
    }


def _risk_level(score: float) -> str:
    """Map compliance score to risk level."""
    if score >= 90:
        return "LOW"
    elif score >= 70:
        return "MEDIUM"
    elif score >= 50:
        return "HIGH"
    else:
        return "CRITICAL"
