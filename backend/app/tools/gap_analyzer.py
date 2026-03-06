"""Gap Analyzer Tool — deterministic pass/fail evaluation of compliance controls.

This tool compares assembled evidence against control pass criteria defined
in controls.json. It produces structured gap reports with actionable
recommendations. All verdicts are deterministic (code-based, not LLM-based).
"""

from __future__ import annotations

from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


# ── Check Functions ─────────────────────────────────────────────────────
# Each function takes evidence data and check params, returns (bool, str).

def _check_doc_exists(evidence: dict[str, Any], params: dict[str, Any]) -> tuple[bool, str]:
    """Check that at least one document matching keywords exists."""
    keywords = params.get("keywords", [])
    items = evidence.get("evidence_items", [])

    for item in items:
        if item.get("data_type") == "document" and item.get("data"):
            data_str = str(item["data"]).lower()
            for kw in keywords:
                if kw.lower() in data_str:
                    return True, f"Document found matching '{kw}'"

    return False, f"No documents found matching keywords: {keywords}"


def _check_nsg_rules_exist(evidence: dict[str, Any], params: dict[str, Any]) -> tuple[bool, str]:
    """Check that NSG rules exist with at least min_count rules."""
    min_count = params.get("min_count", 1)
    items = evidence.get("evidence_items", [])

    for item in items:
        data = item.get("data")
        if isinstance(data, list) and len(data) >= min_count:
            return True, f"Found {len(data)} NSG rules (minimum: {min_count})"
        elif isinstance(data, dict):
            rules = data.get("rules", data.get("security_rules", []))
            if isinstance(rules, list) and len(rules) >= min_count:
                return True, f"Found {len(rules)} NSG rules (minimum: {min_count})"

    return False, f"Fewer than {min_count} NSG rules found"


def _check_no_overly_permissive_rules(
    evidence: dict[str, Any], params: dict[str, Any]
) -> tuple[bool, str]:
    """Check that no NSG rules allow unrestricted inbound from blocked sources on sensitive ports."""
    blocked_sources = params.get("blocked_sources", ["0.0.0.0/0", "*"])
    sensitive_ports = params.get("sensitive_ports", [22, 3389, 1433, 3306])
    items = evidence.get("evidence_items", [])
    violations: list[str] = []

    for item in items:
        data = item.get("data")
        rules = []
        if isinstance(data, list):
            rules = data
        elif isinstance(data, dict):
            rules = data.get("rules", data.get("security_rules", []))

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            direction = rule.get("direction", "").lower()
            access = rule.get("access", "").lower()
            source = rule.get("source_address_prefix", "")
            port = rule.get("destination_port_range", "")

            if direction == "inbound" and access == "allow" and source in blocked_sources:
                try:
                    port_num = int(port)
                    if port_num in sensitive_ports:
                        violations.append(
                            f"Rule allows {source} inbound on port {port_num}"
                        )
                except (ValueError, TypeError):
                    if port == "*":
                        violations.append(
                            f"Rule allows {source} inbound on all ports"
                        )

    if violations:
        return False, f"Overly permissive rules found: {'; '.join(violations)}"
    return True, "No overly permissive inbound rules detected"


def _check_tls_enforced(evidence: dict[str, Any], params: dict[str, Any]) -> tuple[bool, str]:
    """Check that TLS minimum version meets threshold."""
    min_version = params.get("min_version", "1.2")
    items = evidence.get("evidence_items", [])
    non_compliant: list[str] = []

    for item in items:
        data = item.get("data")
        if isinstance(data, list):
            for resource in data:
                if isinstance(resource, dict):
                    tls = resource.get("min_tls_version", resource.get("minimum_tls_version", ""))
                    name = resource.get("name", "unknown")
                    if tls and not _tls_version_gte(tls, min_version):
                        non_compliant.append(f"{name} (TLS {tls})")

    if non_compliant:
        return False, f"Resources below TLS {min_version}: {', '.join(non_compliant)}"
    return True, f"All resources enforce TLS {min_version}+"


def _check_https_only(evidence: dict[str, Any], params: dict[str, Any]) -> tuple[bool, str]:
    """Check that all storage accounts have HTTPS-only enabled."""
    items = evidence.get("evidence_items", [])
    non_compliant: list[str] = []

    for item in items:
        data = item.get("data")
        if isinstance(data, list):
            for resource in data:
                if isinstance(resource, dict):
                    https_only = resource.get("enable_https_traffic_only", resource.get("https_only", True))
                    name = resource.get("name", "unknown")
                    if not https_only:
                        non_compliant.append(name)

    if non_compliant:
        return False, f"Resources without HTTPS-only: {', '.join(non_compliant)}"
    return True, "All resources enforce HTTPS-only"


def _check_encryption_at_rest_enabled(
    evidence: dict[str, Any], params: dict[str, Any]
) -> tuple[bool, str]:
    """Check that encryption at rest is enabled for storage."""
    items = evidence.get("evidence_items", [])
    for item in items:
        data = item.get("data")
        if isinstance(data, list):
            for resource in data:
                if isinstance(resource, dict):
                    enc = resource.get("encryption", resource.get("infrastructure_encryption_enabled"))
                    if enc is False or enc is None:
                        name = resource.get("name", "unknown")
                        return False, f"Encryption at rest not enabled for: {name}"
    return True, "Encryption at rest enabled for all storage"


def _check_mfa_enforced(evidence: dict[str, Any], params: dict[str, Any]) -> tuple[bool, str]:
    """Check that MFA is enforced for the specified scope."""
    scope = params.get("scope", "all_users")
    items = evidence.get("evidence_items", [])

    for item in items:
        data = item.get("data")
        if isinstance(data, dict):
            mfa_enabled = data.get("mfa_enforced", data.get("mfa_enabled", False))
            if mfa_enabled:
                return True, f"MFA enforced for {scope}"
        elif isinstance(data, list):
            # Check conditional access policies
            for policy in data:
                if isinstance(policy, dict):
                    grant_controls = policy.get("grant_controls", {})
                    if "mfa" in str(grant_controls).lower():
                        return True, f"MFA enforced via conditional access policy"

    return False, f"MFA not enforced for scope: {scope}"


def _check_branch_protection_enabled(
    evidence: dict[str, Any], params: dict[str, Any]
) -> tuple[bool, str]:
    """Check that branch protection is enabled on specified branches."""
    branches = params.get("branches", ["main", "master"])
    items = evidence.get("evidence_items", [])

    protected = []
    for item in items:
        data = item.get("data")
        if isinstance(data, dict):
            if data.get("protected", False):
                branch_name = data.get("name", "unknown")
                protected.append(branch_name)
        elif isinstance(data, list):
            for b in data:
                if isinstance(b, dict) and b.get("protected", False):
                    protected.append(b.get("name", "unknown"))

    missing = [b for b in branches if b not in protected]
    if missing:
        return False, f"Branch protection missing on: {', '.join(missing)}"
    return True, f"Branch protection enabled on: {', '.join(protected)}"


def _check_pr_review_required(evidence: dict[str, Any], params: dict[str, Any]) -> tuple[bool, str]:
    """Check that PR reviews are required."""
    min_reviewers = params.get("min_reviewers", 1)
    items = evidence.get("evidence_items", [])

    for item in items:
        data = item.get("data")
        if isinstance(data, dict):
            reviews = data.get("required_pull_request_reviews", {})
            if reviews:
                count = reviews.get("required_approving_review_count", 0)
                if count >= min_reviewers:
                    return True, f"PR review required ({count} approver(s))"

    return False, f"PR review with {min_reviewers}+ approvers not configured"


def _check_keyvault_exists(evidence: dict[str, Any], params: dict[str, Any]) -> tuple[bool, str]:
    """Check that at least one Key Vault exists."""
    items = evidence.get("evidence_items", [])
    for item in items:
        data = item.get("data")
        if isinstance(data, list) and len(data) > 0:
            return True, f"Found {len(data)} Key Vault(s)"
        elif isinstance(data, dict) and data:
            return True, "Key Vault found"
    return False, "No Key Vault found"


def _check_endpoint_protection_enabled(
    evidence: dict[str, Any], params: dict[str, Any]
) -> tuple[bool, str]:
    """Check Defender recommendations for endpoint protection."""
    items = evidence.get("evidence_items", [])
    for item in items:
        data = item.get("data")
        if isinstance(data, list):
            ep_recs = [
                r for r in data
                if isinstance(r, dict)
                and "endpoint" in str(r.get("name", "")).lower()
            ]
            if not ep_recs:
                return True, "No endpoint protection recommendations (all covered)"
            return False, f"Endpoint protection recommendations found: {len(ep_recs)}"
    return False, "Unable to assess endpoint protection"


def _check_vulnerability_scanning_enabled(
    evidence: dict[str, Any], params: dict[str, Any]
) -> tuple[bool, str]:
    """Check that vulnerability scanning is enabled."""
    items = evidence.get("evidence_items", [])
    for item in items:
        data = item.get("data")
        if isinstance(data, list):
            vuln_recs = [
                r for r in data
                if isinstance(r, dict)
                and "vulnerab" in str(r.get("name", "")).lower()
            ]
            if vuln_recs:
                return True, f"Vulnerability scanning detected ({len(vuln_recs)} findings)"
    return False, "No vulnerability scanning evidence found"


def _check_activity_log_enabled(
    evidence: dict[str, Any], params: dict[str, Any]
) -> tuple[bool, str]:
    """Check that Azure Activity Log is enabled."""
    items = evidence.get("evidence_items", [])
    for item in items:
        if item.get("data"):
            return True, "Activity log data available"
    return False, "No activity log data found"


def _check_firewall_exists(evidence: dict[str, Any], params: dict[str, Any]) -> tuple[bool, str]:
    """Check that a firewall or WAF exists."""
    items = evidence.get("evidence_items", [])
    for item in items:
        data = item.get("data")
        if isinstance(data, list):
            fw = [
                r for r in data
                if isinstance(r, dict)
                and any(
                    kw in r.get("type", "").lower()
                    for kw in ["firewall", "waf", "application_gateway"]
                )
            ]
            if fw:
                return True, f"Found {len(fw)} firewall/WAF resource(s)"
    return False, "No firewall or WAF resources found"


def _default_check(evidence: dict[str, Any], params: dict[str, Any]) -> tuple[bool, str]:
    """Default check — passes if any evidence exists."""
    items = evidence.get("evidence_items", [])
    if items:
        return True, "Evidence present (manual review recommended)"
    return False, "No evidence collected for this check"


# ── Check Registry ──────────────────────────────────────────────────────

CHECK_FUNCTIONS: dict[str, Callable[[dict, dict], tuple[bool, str]]] = {
    "doc_exists": _check_doc_exists,
    "nsg_rules_exist": _check_nsg_rules_exist,
    "no_overly_permissive_rules": _check_no_overly_permissive_rules,
    "tls_enforced": _check_tls_enforced,
    "https_only": _check_https_only,
    "encryption_at_rest_enabled": _check_encryption_at_rest_enabled,
    "mfa_enforced": _check_mfa_enforced,
    "mfa_enforced_for_cde": _check_mfa_enforced,
    "branch_protection_enabled": _check_branch_protection_enabled,
    "pr_review_required": _check_pr_review_required,
    "status_checks_required": _default_check,
    "keyvault_exists": _check_keyvault_exists,
    "tde_enabled": _check_encryption_at_rest_enabled,
    "endpoint_protection_enabled": _check_endpoint_protection_enabled,
    "vulnerability_scanning_enabled": _check_vulnerability_scanning_enabled,
    "dependency_scanning_enabled": _default_check,
    "activity_log_enabled": _check_activity_log_enabled,
    "sql_auditing_enabled": _default_check,
    "diagnostic_logging_enabled": _default_check,
    "immutable_storage_configured": _default_check,
    "log_access_restricted": _default_check,
    "log_retention_days": _default_check,
    "recent_logs_available": _default_check,
    "scan_frequency": _default_check,
    "firewall_exists": _check_firewall_exists,
    "default_deny_rule": _default_check,
    "waf_exists": _check_firewall_exists,
    "waf_prevention_mode": _default_check,
    "conditional_access_device_compliance": _default_check,
    "cde_segmentation_exists": _default_check,
    "nsg_restricts_inbound": _default_check,
    "no_critical_defender_recommendations": _default_check,
    "rbac_enabled": _default_check,
    "privileged_roles_limited": _default_check,
    "access_reviews_configured": _default_check,
    "password_policy_compliant": _default_check,
    "service_accounts_inventoried": _default_check,
    "credential_rotation_configured": _default_check,
    "no_interactive_login_for_service_accounts": _default_check,
    "doc_reviewed_recently": _default_check,
    "ir_team_designated": _default_check,
    "ir_plan_tested": _default_check,
}


# ── Main Analyzer ───────────────────────────────────────────────────────

async def gap_analyzer(
    evidence_bundle: dict[str, Any],
    controls: list[dict[str, Any]],
) -> dict[str, Any]:
    """Analyze evidence against controls and produce a gap report.

    Args:
        evidence_bundle: Structured evidence keyed by control ID
            (output of evidence_assembler).
        controls: Control definitions from controls.json.

    Returns:
        Dict with "assessments" list and "summary" stats.
    """
    logger.info(
        "gap_analyzer_start",
        evidence_controls=len(evidence_bundle),
        target_controls=len(controls),
    )

    assessments: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    gaps = 0
    not_assessed = 0

    for control in controls:
        control_id = control["id"]
        requirement = control.get("requirement", "")
        pass_criteria = control.get("pass_criteria", [])

        evidence = evidence_bundle.get(control_id, {})

        if not evidence or evidence.get("status") == "missing":
            # No evidence collected at all
            assessments.append({
                "control_id": control_id,
                "requirement": requirement,
                "status": "not_assessed",
                "evidence_items": [],
                "gaps": ["No evidence collected"],
                "recommendations": ["Collect evidence for this control"],
                "check_results": [],
            })
            not_assessed += 1
            continue

        # Run each check in pass_criteria
        check_results: list[dict[str, Any]] = []
        all_passed = True

        for criterion in pass_criteria:
            check_name = criterion.get("check", "")
            check_params = criterion.get("params", {})
            check_func = CHECK_FUNCTIONS.get(check_name, _default_check)

            result, detail = check_func(evidence, check_params)
            check_results.append({
                "check": check_name,
                "passed": result,
                "detail": detail,
            })
            if not result:
                all_passed = False

        # Determine overall status
        if all_passed:
            status = "passed"
            passed += 1
        else:
            failed_checks = [cr for cr in check_results if not cr["passed"]]
            status = "gap"
            gaps += 1

        gap_details = [
            cr["detail"] for cr in check_results if not cr["passed"]
        ]
        recommendations = _generate_recommendations(control_id, gap_details)

        assessments.append({
            "control_id": control_id,
            "requirement": requirement,
            "status": status,
            "evidence_items": evidence.get("evidence_items", []),
            "gaps": gap_details,
            "recommendations": recommendations,
            "check_results": check_results,
        })

    total = len(controls)
    assessed = passed + gaps
    compliance_score = (passed / assessed * 100) if assessed > 0 else 0.0

    summary = {
        "total_controls": total,
        "passed": passed,
        "failed": failed,
        "gaps": gaps,
        "not_assessed": not_assessed,
        "compliance_score": round(compliance_score, 1),
    }

    logger.info(
        "gap_analyzer_complete",
        passed=passed,
        gaps=gaps,
        not_assessed=not_assessed,
        score=summary["compliance_score"],
    )

    return {
        "assessments": assessments,
        "summary": summary,
    }


def _generate_recommendations(control_id: str, gap_details: list[str]) -> list[str]:
    """Generate actionable recommendations based on identified gaps."""
    recommendations: list[str] = []

    for detail in gap_details:
        detail_lower = detail.lower()

        if "no documents found" in detail_lower or "no evidence collected" in detail_lower:
            recommendations.append(
                f"Create and maintain documentation for control {control_id}. "
                "Store in the repository with regular review cycles."
            )
        elif "overly permissive" in detail_lower:
            recommendations.append(
                "Restrict NSG rules to specific IP ranges. Remove 0.0.0.0/0 "
                "inbound rules on sensitive ports (22, 3389, 1433, 3306)."
            )
        elif "tls" in detail_lower:
            recommendations.append(
                "Upgrade all resources to TLS 1.2 minimum. Update "
                "min_tls_version configuration on affected resources."
            )
        elif "https" in detail_lower:
            recommendations.append(
                "Enable HTTPS-only on all storage accounts and web endpoints."
            )
        elif "mfa" in detail_lower:
            recommendations.append(
                "Enable MFA for all users via Conditional Access policy. "
                "Ensure CDE access requires MFA."
            )
        elif "branch protection" in detail_lower:
            recommendations.append(
                "Enable branch protection on main/master branches. "
                "Require pull request reviews before merging."
            )
        elif "key vault" in detail_lower:
            recommendations.append(
                "Deploy Azure Key Vault for centralized key and secret management. "
                "Rotate credentials on a regular schedule."
            )
        elif "firewall" in detail_lower or "waf" in detail_lower:
            recommendations.append(
                "Deploy Azure Firewall or WAF for perimeter security. "
                "Enable prevention mode with OWASP rule sets."
            )
        elif "endpoint" in detail_lower:
            recommendations.append(
                "Ensure endpoint protection (Defender for Endpoint) is deployed "
                "on all applicable compute resources."
            )
        else:
            recommendations.append(
                f"Review and remediate gap for control {control_id}: {detail}"
            )

    return recommendations


# ── Helpers ─────────────────────────────────────────────────────────────

def _tls_version_gte(actual: str, minimum: str) -> bool:
    """Compare TLS version strings (e.g., '1.2' >= '1.2')."""
    def parse(v: str) -> tuple[int, ...]:
        cleaned = v.replace("TLS", "").replace("tls", "").replace("_", ".").strip()
        try:
            return tuple(int(x) for x in cleaned.split("."))
        except ValueError:
            return (0,)

    return parse(actual) >= parse(minimum)
