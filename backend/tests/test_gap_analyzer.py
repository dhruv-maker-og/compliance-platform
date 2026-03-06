"""Tests for the gap_analyzer tool."""

import pytest

from app.tools.gap_analyzer import gap_analyzer


@pytest.fixture
def sample_controls():
    return [
        {
            "id": "1.1",
            "requirement": "Install and maintain network security controls",
            "goal": 1,
            "evidence_sources": ["azure_nsgs"],
            "pass_criteria": [
                {"check": "nsg_rules_exist", "params": {"min_count": 1}},
                {
                    "check": "no_overly_permissive_rules",
                    "params": {
                        "blocked_sources": ["0.0.0.0/0", "*"],
                        "sensitive_ports": [22, 3389],
                    },
                },
            ],
        },
        {
            "id": "4.1",
            "requirement": "Protect data in transit with strong cryptography",
            "goal": 4,
            "evidence_sources": ["azure_tls_config"],
            "pass_criteria": [
                {"check": "tls_enforced", "params": {"min_version": "1.2"}},
            ],
        },
    ]


@pytest.fixture
def passing_evidence():
    return {
        "1.1": {
            "status": "collected",
            "evidence_items": [
                {
                    "source": "azure_nsgs",
                    "data_type": "config",
                    "data": [
                        {
                            "direction": "inbound",
                            "access": "deny",
                            "source_address_prefix": "10.0.0.0/8",
                            "destination_port_range": "443",
                        },
                        {
                            "direction": "inbound",
                            "access": "allow",
                            "source_address_prefix": "10.1.0.0/16",
                            "destination_port_range": "443",
                        },
                    ],
                }
            ],
        },
        "4.1": {
            "status": "collected",
            "evidence_items": [
                {
                    "source": "azure_tls_config",
                    "data_type": "config",
                    "data": [
                        {"name": "webapp-prod", "min_tls_version": "1.2"},
                        {"name": "api-prod", "min_tls_version": "1.3"},
                    ],
                }
            ],
        },
    }


@pytest.fixture
def failing_evidence():
    return {
        "1.1": {
            "status": "collected",
            "evidence_items": [
                {
                    "source": "azure_nsgs",
                    "data_type": "config",
                    "data": [
                        {
                            "direction": "inbound",
                            "access": "allow",
                            "source_address_prefix": "0.0.0.0/0",
                            "destination_port_range": "22",
                        }
                    ],
                }
            ],
        },
        "4.1": {
            "status": "collected",
            "evidence_items": [
                {
                    "source": "azure_tls_config",
                    "data_type": "config",
                    "data": [
                        {"name": "old-webapp", "min_tls_version": "1.0"},
                    ],
                }
            ],
        },
    }


@pytest.mark.asyncio
async def test_gap_analyzer_all_passing(sample_controls, passing_evidence):
    """Test that compliant evidence produces all-passed results."""
    result = await gap_analyzer(passing_evidence, sample_controls)

    assert result["summary"]["passed"] == 2
    assert result["summary"]["gaps"] == 0
    assert result["summary"]["compliance_score"] == 100.0

    for assessment in result["assessments"]:
        assert assessment["status"] == "passed"


@pytest.mark.asyncio
async def test_gap_analyzer_detects_gaps(sample_controls, failing_evidence):
    """Test that non-compliant evidence produces gap findings."""
    result = await gap_analyzer(failing_evidence, sample_controls)

    assert result["summary"]["gaps"] > 0
    assert result["summary"]["compliance_score"] < 100.0

    gap_controls = [a for a in result["assessments"] if a["status"] == "gap"]
    assert len(gap_controls) > 0

    # Check gaps have recommendations
    for ga in gap_controls:
        assert len(ga["recommendations"]) > 0


@pytest.mark.asyncio
async def test_gap_analyzer_missing_evidence(sample_controls):
    """Test that missing evidence results in not_assessed."""
    result = await gap_analyzer({}, sample_controls)

    assert result["summary"]["not_assessed"] == 2
    assert result["summary"]["passed"] == 0


@pytest.mark.asyncio
async def test_gap_analyzer_summary_structure(sample_controls, passing_evidence):
    """Test summary has all required fields."""
    result = await gap_analyzer(passing_evidence, sample_controls)
    summary = result["summary"]

    assert "total_controls" in summary
    assert "passed" in summary
    assert "gaps" in summary
    assert "not_assessed" in summary
    assert "compliance_score" in summary
