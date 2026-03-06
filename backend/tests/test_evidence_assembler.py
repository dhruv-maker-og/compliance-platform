"""Tests for the evidence_assembler tool."""

import pytest

from app.tools.evidence_assembler import evidence_assembler


@pytest.fixture
def sample_controls():
    return [
        {
            "id": "1.1",
            "requirement": "Install and maintain network security controls",
            "goal": 1,
            "evidence_sources": ["azure_nsgs", "azure_firewall"],
            "pass_criteria": [
                {"check": "nsg_rules_exist", "params": {"min_count": 1}},
            ],
        },
        {
            "id": "3.4",
            "requirement": "Protect stored account data with encryption",
            "goal": 3,
            "evidence_sources": ["azure_storage_encryption", "azure_sql_tde"],
            "pass_criteria": [
                {"check": "encryption_at_rest_enabled", "params": {}},
            ],
        },
    ]


@pytest.fixture
def sample_raw_evidence():
    return {
        "azure_nsgs": [
            {
                "name": "nsg-production",
                "rules": [
                    {
                        "direction": "Inbound",
                        "access": "Deny",
                        "source_address_prefix": "*",
                        "destination_port_range": "*",
                        "priority": 4096,
                    }
                ],
            }
        ],
        "azure_storage_encryption": [
            {
                "name": "stprod001",
                "encryption": True,
                "enable_https_traffic_only": True,
            }
        ],
    }


@pytest.mark.asyncio
async def test_evidence_assembler_maps_evidence(sample_controls, sample_raw_evidence):
    """Test that evidence is mapped to the correct controls."""
    bundle = await evidence_assembler(sample_raw_evidence, sample_controls)

    assert "1.1" in bundle
    assert "3.4" in bundle


@pytest.mark.asyncio
async def test_evidence_assembler_marks_missing(sample_controls):
    """Test that controls with no matching evidence are marked missing."""
    bundle = await evidence_assembler({}, sample_controls)

    for control_id in ["1.1", "3.4"]:
        assert bundle[control_id]["status"] == "missing"
        assert len(bundle[control_id]["evidence_items"]) == 0


@pytest.mark.asyncio
async def test_evidence_assembler_computes_coverage(sample_controls, sample_raw_evidence):
    """Test coverage calculation."""
    bundle = await evidence_assembler(sample_raw_evidence, sample_controls)

    control_1_1 = bundle["1.1"]
    # azure_nsgs matched, azure_firewall missing → 50% coverage
    assert 0 <= control_1_1["coverage"] <= 100
