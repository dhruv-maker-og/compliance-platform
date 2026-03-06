"""Advanced compliance insight endpoints.

POST /api/insights/narrate-evidence  -> Auditor-ready evidence narration
POST /api/insights/drift-detect      -> Baseline vs current drift detection
POST /api/insights/framework-compare -> Multi-framework control comparison
POST /api/insights/rego-debug        -> Rego explain trace + violations
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    DriftDetectionRequest,
    DriftDetectionResponse,
    DriftItem,
    DriftScheduleRequest,
    DriftScheduleStatus,
    DriftSnapshotRequest,
    FrameworkComparisonRequest,
    FrameworkComparisonResponse,
    NarrateEvidenceRequest,
    RegoDebugRequest,
    RegoDebugResponse,
)
from app.tools.opa_tester import opa_eval, opa_eval_explain

router = APIRouter()

_DRIFT_BASELINE_SNAPSHOTS: dict[str, list[dict[str, Any]]] = {}
_DRIFT_CURRENT_SNAPSHOTS: dict[str, list[dict[str, Any]]] = {}
_DRIFT_LAST_RESULTS: dict[str, DriftDetectionResponse] = {}
_DRIFT_LAST_RUN_AT: dict[str, datetime] = {}
_DRIFT_TASKS: dict[str, asyncio.Task[None]] = {}
_DRIFT_INTERVALS: dict[str, int] = {}


def _calculate_drift(
    scope: str,
    baseline: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> DriftDetectionResponse:
    """Calculate drift between two snapshots."""
    baseline_map = {item.get("control_id"): item for item in baseline}
    current_map = {item.get("control_id"): item for item in current}
    control_ids = sorted(set(baseline_map.keys()) | set(current_map.keys()))

    changed_controls_payload: list[dict[str, str]] = []
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

        changed_controls_payload.append({
            "control_id": str(control_id),
            "baseline_status": str(old_status),
            "current_status": str(new_status),
            "change_type": change_type,
        })

    changed_controls = [
        DriftItem(
            control_id=item.get("control_id", ""),
            baseline_status=item.get("baseline_status", "not_assessed"),
            current_status=item.get("current_status", "not_assessed"),
            change_type=item.get("change_type", "changed"),
            details=item.get("details", ""),
        )
        for item in changed_controls_payload
    ]

    return DriftDetectionResponse(
        scope=scope,
        total_controls_compared=len(control_ids),
        drift_count=len(changed_controls),
        regressions=regressions,
        improvements=improvements,
        changed_controls=changed_controls,
    )


async def _drift_scheduler_loop(scope: str, interval_seconds: int) -> None:
    """Run drift checks at fixed interval for one scope."""
    while True:
        baseline = _DRIFT_BASELINE_SNAPSHOTS.get(scope)
        current = _DRIFT_CURRENT_SNAPSHOTS.get(scope)
        if baseline is not None and current is not None:
            result = _calculate_drift(scope=scope, baseline=baseline, current=current)
            _DRIFT_LAST_RESULTS[scope] = result
            _DRIFT_LAST_RUN_AT[scope] = datetime.utcnow()
        await asyncio.sleep(interval_seconds)


def _status_for_scope(scope: str) -> DriftScheduleStatus:
    """Build schedule status response for scope."""
    last_result = _DRIFT_LAST_RESULTS.get(scope)
    task = _DRIFT_TASKS.get(scope)
    running = bool(task and not task.done() and not task.cancelled())
    return DriftScheduleStatus(
        scope=scope,
        running=running,
        interval_seconds=_DRIFT_INTERVALS.get(scope),
        has_baseline=scope in _DRIFT_BASELINE_SNAPSHOTS,
        has_current=scope in _DRIFT_CURRENT_SNAPSHOTS,
        last_run_at=_DRIFT_LAST_RUN_AT.get(scope),
        last_result=last_result,
    )


@router.post("/narrate-evidence")
async def narrate_evidence(request: NarrateEvidenceRequest) -> dict[str, Any]:
    """Generate auditor-facing evidence narrative text for one control."""
    items = json.loads(request.evidence_items_json)
    context = {
        "control_id": request.control_id,
        "requirement": request.requirement,
        "status": request.assessment_status.value,
        "evidence_count": len(items),
        "sources": sorted({item.get("source", "unknown") for item in items}),
        "data_types": sorted({item.get("data_type", "unknown") for item in items}),
        "collection_dates": [
            item.get("collected_at", "") for item in items if item.get("collected_at")
        ],
    }
    status = str(context.get("status", "not_assessed"))
    status_label = {
        "passed": "satisfies",
        "failed": "does not satisfy",
        "gap": "partially satisfies",
    }.get(status, "has unknown compliance status for")

    narrative = (
        f"Control {context.get('control_id', request.control_id)} {status_label} "
        f"the stated requirement: {context.get('requirement', request.requirement)}. "
        f"A total of {context.get('evidence_count', 0)} evidence artifacts were collected "
        f"from sources {', '.join(context.get('sources', [])) or 'N/A'} with data types "
        f"{', '.join(context.get('data_types', [])) or 'N/A'}."
    )

    return {
        "control_id": request.control_id,
        "narrative": narrative,
        "context": context,
    }


@router.post("/drift-detect", response_model=DriftDetectionResponse)
async def drift_detect(request: DriftDetectionRequest) -> DriftDetectionResponse:
    """Compare baseline and current assessments to detect compliance drift."""
    baseline = json.loads(request.baseline_assessments_json)
    current = json.loads(request.current_assessments_json)
    result = _calculate_drift(scope=request.scope, baseline=baseline, current=current)
    _DRIFT_LAST_RESULTS[request.scope] = result
    _DRIFT_LAST_RUN_AT[request.scope] = datetime.utcnow()
    return result


@router.post("/drift/baseline")
async def set_drift_baseline(request: DriftSnapshotRequest) -> dict[str, Any]:
    """Set baseline snapshot for continuous drift checks."""
    _DRIFT_BASELINE_SNAPSHOTS[request.scope] = json.loads(request.assessments_json)
    return {
        "scope": request.scope,
        "baseline_items": len(_DRIFT_BASELINE_SNAPSHOTS[request.scope]),
        "status": "baseline_saved",
    }


@router.post("/drift/current")
async def set_drift_current(request: DriftSnapshotRequest) -> dict[str, Any]:
    """Set current snapshot for continuous drift checks."""
    _DRIFT_CURRENT_SNAPSHOTS[request.scope] = json.loads(request.assessments_json)
    return {
        "scope": request.scope,
        "current_items": len(_DRIFT_CURRENT_SNAPSHOTS[request.scope]),
        "status": "current_saved",
    }


@router.post("/drift/schedule/start", response_model=DriftScheduleStatus)
async def start_drift_schedule(request: DriftScheduleRequest) -> DriftScheduleStatus:
    """Start periodic drift checks for a scope."""
    existing = _DRIFT_TASKS.get(request.scope)
    if existing and not existing.done():
        existing.cancel()

    task = asyncio.create_task(
        _drift_scheduler_loop(scope=request.scope, interval_seconds=request.interval_seconds)
    )
    _DRIFT_TASKS[request.scope] = task
    _DRIFT_INTERVALS[request.scope] = request.interval_seconds
    return _status_for_scope(request.scope)


@router.post("/drift/schedule/stop/{scope}", response_model=DriftScheduleStatus)
async def stop_drift_schedule(scope: str) -> DriftScheduleStatus:
    """Stop periodic drift checks for a scope."""
    task = _DRIFT_TASKS.get(scope)
    if task and not task.done():
        task.cancel()
    _DRIFT_TASKS.pop(scope, None)
    _DRIFT_INTERVALS.pop(scope, None)
    return _status_for_scope(scope)


@router.get("/drift/schedule/status/{scope}", response_model=DriftScheduleStatus)
async def get_drift_schedule_status(scope: str) -> DriftScheduleStatus:
    """Get drift schedule status for a scope."""
    return _status_for_scope(scope)


@router.post("/drift/schedule/run-now/{scope}", response_model=DriftDetectionResponse)
async def run_drift_now(scope: str) -> DriftDetectionResponse:
    """Run one immediate drift check using saved baseline/current snapshots."""
    baseline = _DRIFT_BASELINE_SNAPSHOTS.get(scope)
    current = _DRIFT_CURRENT_SNAPSHOTS.get(scope)
    if baseline is None or current is None:
        raise HTTPException(
            status_code=409,
            detail="Baseline and current snapshots must be set before running drift",
        )

    result = _calculate_drift(scope=scope, baseline=baseline, current=current)
    _DRIFT_LAST_RESULTS[scope] = result
    _DRIFT_LAST_RUN_AT[scope] = datetime.utcnow()
    return result


@router.post("/framework-compare", response_model=FrameworkComparisonResponse)
async def framework_compare(request: FrameworkComparisonRequest) -> FrameworkComparisonResponse:
    """Compare control IDs between requested frameworks."""
    base_path = Path(__file__).resolve().parents[3] / "skills"
    found: dict[str, list[str]] = {}

    for framework in request.frameworks:
        controls_path = base_path / framework / "controls.json"
        if not controls_path.exists():
            continue
        controls_data = json.loads(controls_path.read_text(encoding="utf-8"))
        ids = [str(c.get("id", "")) for c in controls_data.get("controls", []) if c.get("id")]
        found[framework] = sorted(set(ids))

    if found:
        common_control_ids = sorted(set.intersection(*(set(ids) for ids in found.values())))
    else:
        common_control_ids = []

    unique_control_ids: dict[str, list[str]] = {}
    for framework, ids in found.items():
        others = set().union(*(set(v) for k, v in found.items() if k != framework))
        unique_control_ids[framework] = sorted([cid for cid in ids if cid not in others])

    return FrameworkComparisonResponse(
        frameworks_requested=request.frameworks,
        frameworks_found=sorted(found.keys()),
        total_controls_by_framework={k: len(v) for k, v in found.items()},
        common_control_ids=common_control_ids,
        unique_control_ids=unique_control_ids,
    )


@router.post("/rego-debug", response_model=RegoDebugResponse)
async def rego_debug(request: RegoDebugRequest) -> RegoDebugResponse:
    """Run OPA evaluation and return explain trace for interactive debugging."""
    eval_result = await opa_eval(
        policy_rego=request.policy_rego,
        terraform_plan_json=request.terraform_plan_json,
        query=request.query,
    )
    explain_result = await opa_eval_explain(
        policy_rego=request.policy_rego,
        terraform_plan_json=request.terraform_plan_json,
        query=request.query,
        explain_level="full",
    )

    error = eval_result.get("error") or explain_result.get("error")
    if error:
        if "OPA binary not found" in str(error):
            error = (
                "OPA binary not found. Install OPA and ensure it is on PATH, "
                "or set OPA_BINARY env var, or place opa.exe in tools/bin/"
            )
        raise HTTPException(status_code=400, detail=error)

    violations = eval_result.get("violations", [])
    summary = (
        "No violations found."
        if eval_result.get("passed", False)
        else f"Found {len(violations)} policy violation(s)."
    )

    return RegoDebugResponse(
        passed=bool(eval_result.get("passed", False)),
        violations=violations,
        explain_trace=str(explain_result.get("explain_trace", "")),
        summary=summary,
    )
