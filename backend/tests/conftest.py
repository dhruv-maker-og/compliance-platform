"""Shared test fixtures and configuration."""

import pytest


@pytest.fixture
def sample_controls():
    """PCI-DSS sample controls for testing."""
    return [
        {
            "id": "1.1",
            "requirement": "Install and maintain network security controls",
            "goal": 1,
            "evidence_sources": ["azure_nsgs"],
            "pass_criteria": [
                {"check": "nsg_rules_exist", "params": {"min_count": 1}},
            ],
        },
        {
            "id": "2.1",
            "requirement": "Apply secure configurations to all system components",
            "goal": 2,
            "evidence_sources": ["azure_configs"],
            "pass_criteria": [
                {"check": "default_credentials_changed", "params": {}},
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
