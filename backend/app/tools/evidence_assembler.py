"""Evidence Assembler Tool — structures raw evidence by compliance control.

This tool takes raw evidence data collected from various MCP servers and tools,
and organizes it into a structured evidence bundle keyed by control ID.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def evidence_assembler(
    raw_evidence: dict[str, Any],
    controls: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble raw evidence into a structured bundle by control ID.

    Args:
        raw_evidence: Dict of evidence collected from various sources.
            Keys are source identifiers (e.g., "azure:nsg_rules"),
            values are the raw data from those sources.
        controls: List of control definitions from controls.json.

    Returns:
        Dict keyed by control ID, with structured evidence for each.
    """
    logger.info(
        "evidence_assembler_start",
        raw_sources=len(raw_evidence),
        target_controls=len(controls),
    )

    evidence_bundle: dict[str, dict[str, Any]] = {}

    for control in controls:
        control_id = control["id"]
        requirement = control.get("requirement", "")
        evidence_sources = control.get("evidence_sources", [])

        # Collect relevant evidence for this control
        collected_items: list[dict[str, Any]] = []
        for source in evidence_sources:
            # Match raw evidence keys to control's expected sources
            matching_data = _find_matching_evidence(source, raw_evidence)
            if matching_data is not None:
                collected_items.append({
                    "source": source,
                    "data": matching_data,
                    "collected_at": datetime.utcnow().isoformat(),
                    "data_type": _classify_data_type(source),
                })

        evidence_bundle[control_id] = {
            "control_id": control_id,
            "requirement": requirement,
            "evidence_items": collected_items,
            "evidence_count": len(collected_items),
            "expected_sources": len(evidence_sources),
            "coverage": (
                len(collected_items) / len(evidence_sources)
                if evidence_sources
                else 0.0
            ),
            "status": "collected" if collected_items else "missing",
        }

    logger.info(
        "evidence_assembler_complete",
        controls_with_evidence=sum(
            1 for v in evidence_bundle.values() if v["status"] == "collected"
        ),
        total_controls=len(controls),
    )

    return evidence_bundle


def _find_matching_evidence(
    source_key: str, raw_evidence: dict[str, Any]
) -> Any | None:
    """Find raw evidence matching a given source key.

    Supports partial matching (e.g., "azure:nsg_rules" matches
    raw evidence key "azure_nsg_rules" or "azure:nsg_rules").
    """
    # Direct match
    if source_key in raw_evidence:
        return raw_evidence[source_key]

    # Normalized match (replace : with _)
    normalized = source_key.replace(":", "_")
    if normalized in raw_evidence:
        return raw_evidence[normalized]

    # Partial match (source suffix)
    suffix = source_key.split(":")[-1] if ":" in source_key else source_key
    for k, v in raw_evidence.items():
        if k.endswith(suffix):
            return v

    return None


def _classify_data_type(source: str) -> str:
    """Classify the type of evidence based on its source."""
    source_lower = source.lower()

    if any(kw in source_lower for kw in ["doc", "search", "policy_doc"]):
        return "document"
    elif any(kw in source_lower for kw in ["log", "activity", "audit"]):
        return "log"
    elif any(kw in source_lower for kw in ["config", "rule", "setting", "nsg", "branch"]):
        return "configuration"
    elif any(kw in source_lower for kw in ["scan", "vulnerability", "defender"]):
        return "scan_result"
    elif any(kw in source_lower for kw in ["role", "mfa", "access", "principal"]):
        return "identity"
    elif any(kw in source_lower for kw in ["classification", "label", "purview"]):
        return "data_governance"
    else:
        return "other"
