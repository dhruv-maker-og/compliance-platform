"""Tests for the report_generator tool."""

import pytest

from app.tools.report_generator import (
    generate_compliance_report,
    generate_policy_report,
)


@pytest.fixture
def sample_gap_analysis():
    return {
        "assessments": [
            {
                "control_id": "1.1",
                "requirement": "Install and maintain network security controls",
                "status": "passed",
                "checks_passed": ["nsg_rules_exist", "no_overly_permissive_rules"],
                "checks_failed": [],
                "recommendations": [],
            },
            {
                "control_id": "4.1",
                "requirement": "Protect data in transit with strong cryptography",
                "status": "gap",
                "checks_passed": [],
                "checks_failed": ["tls_enforced"],
                "recommendations": [
                    "Upgrade all resources to TLS 1.2 or higher",
                    "Enforce minimum TLS version in Azure policy",
                ],
            },
        ],
        "summary": {
            "total_controls": 2,
            "passed": 1,
            "gaps": 1,
            "not_assessed": 0,
            "compliance_score": 50.0,
        },
    }


@pytest.fixture
def sample_policy_result():
    return {
        "success": True,
        "violations": [
            {
                "rule": "deny",
                "message": "Storage account 'test' missing min_tls_version",
                "resource": "azurerm_storage_account.test",
            }
        ],
        "policy_name": "encryption_at_rest",
        "total_resources_evaluated": 5,
    }


@pytest.mark.asyncio
async def test_compliance_report_markdown(sample_gap_analysis):
    """Test Markdown compliance report generation."""
    report = await generate_compliance_report(
        gap_analysis=sample_gap_analysis,
        framework="PCI-DSS v4.0",
        output_format="markdown",
    )

    assert isinstance(report, str)
    assert "PCI-DSS" in report
    assert "50.0" in report or "50%" in report
    assert "1.1" in report
    assert "4.1" in report
    assert "TLS" in report or "tls" in report


@pytest.mark.asyncio
async def test_compliance_report_structured(sample_gap_analysis):
    """Test structured compliance report generation."""
    report = await generate_compliance_report(
        gap_analysis=sample_gap_analysis,
        framework="PCI-DSS v4.0",
        output_format="structured",
    )

    assert isinstance(report, dict)
    assert "framework" in report
    assert "summary" in report
    assert report["summary"]["compliance_score"] == 50.0


@pytest.mark.asyncio
async def test_compliance_report_contains_gaps(sample_gap_analysis):
    """Test that compliance report highlights gaps."""
    report = await generate_compliance_report(
        gap_analysis=sample_gap_analysis,
        framework="PCI-DSS v4.0",
        output_format="markdown",
    )

    # Gap section should mention the failed control
    assert "4.1" in report
    assert any(
        keyword in report.lower()
        for keyword in ["gap", "fail", "non-compliant", "remediation", "recommendation"]
    )


@pytest.mark.asyncio
async def test_policy_report_generation(sample_policy_result):
    """Test policy enforcement report generation."""
    report = await generate_policy_report(
        policy_result=sample_policy_result,
        policy_name="encryption_at_rest",
        output_format="markdown",
    )

    assert isinstance(report, str)
    assert "encryption_at_rest" in report or "encryption" in report.lower()
    assert "violation" in report.lower() or "deny" in report.lower()


@pytest.mark.asyncio
async def test_policy_report_no_violations():
    """Test policy report when there are no violations."""
    clean_result = {
        "success": True,
        "violations": [],
        "policy_name": "network_security",
        "total_resources_evaluated": 3,
    }

    report = await generate_policy_report(
        policy_result=clean_result,
        policy_name="network_security",
        output_format="markdown",
    )

    assert isinstance(report, str)
    assert "0" in report or "no violation" in report.lower() or "pass" in report.lower()
