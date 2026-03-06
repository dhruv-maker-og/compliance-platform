"""Policy generation & enforcement API endpoints.

POST /api/policy/generate       → Generate Rego policy from natural language
POST /api/policy/enforce        → Enforce policy against Terraform plan
GET  /api/policy/stream/{id}    → SSE stream of policy workflow progress
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.engine import get_agent_engine
from app.models.schemas import (
    PolicyEnforceRequest,
    PolicyGenerateRequest,
    SessionCreatedResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/generate", response_model=SessionCreatedResponse)
async def generate_policy(
    request: PolicyGenerateRequest,
) -> SessionCreatedResponse:
    """Generate a Rego policy from a natural language description.

    The agent translates the intent into OPA Rego, generates tests,
    and validates syntax before returning.
    """
    engine = get_agent_engine()

    try:
        session = await engine.create_session(mode="policy")
        # Store request params in session metadata
        session.metadata.update({
            "intent": request.intent,
            "target_resources": request.target_resources,
            "severity": request.severity.value if request.severity else "high",
        })
    except Exception as e:
        logger.error("policy_session_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create session")

    logger.info(
        "policy_generation_started",
        session_id=session.session_id,
        intent=request.intent[:100],
    )

    return SessionCreatedResponse(
        session_id=session.session_id,
        status=session.status,
        stream_url=f"/api/policy/stream/{session.session_id}",
    )


@router.post("/enforce", response_model=SessionCreatedResponse)
async def enforce_policy(
    request: PolicyEnforceRequest,
) -> SessionCreatedResponse:
    """Enforce a Rego policy against a Terraform plan.

    The agent evaluates the policy, reports violations, and optionally
    generates fix suggestions with auto-remediation.
    """
    engine = get_agent_engine()

    try:
        session = await engine.create_session(mode="enforcement")
        session.metadata.update({
            "policy_path": request.policy_path,
            "terraform_plan_path": request.terraform_plan_path,
            "auto_fix": request.auto_fix,
        })
    except Exception as e:
        logger.error("enforcement_session_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create session")

    logger.info(
        "policy_enforcement_started",
        session_id=session.session_id,
        policy=request.policy_path,
    )

    return SessionCreatedResponse(
        session_id=session.session_id,
        status=session.status,
        stream_url=f"/api/policy/stream/{session.session_id}",
    )


@router.get("/stream/{session_id}")
async def stream_policy_progress(
    session_id: str,
    request: Request,
) -> EventSourceResponse:
    """SSE stream of agent progress for policy generation or enforcement.

    Events:
    - step: Agent progress step
    - complete: Final results
    - error: Error occurred
    """
    engine = get_agent_engine()
    session = engine.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        try:
            mode = session.metadata.get("mode", "policy")

            if mode == "enforcement":
                gen = engine.run_policy_enforcement(
                    session_id=session_id,
                    policy_path=session.metadata.get("policy_path", ""),
                    terraform_plan_path=session.metadata.get("terraform_plan_path", ""),
                    auto_fix=session.metadata.get("auto_fix", False),
                )
            else:
                gen = engine.run_policy_generation(
                    session_id=session_id,
                    intent=session.metadata.get("intent", ""),
                    target_resources=session.metadata.get("target_resources", []),
                    severity=session.metadata.get("severity", "high"),
                )

            async for step in gen:
                if await request.is_disconnected():
                    logger.info("client_disconnected", session_id=session_id)
                    break

                yield {
                    "event": "step",
                    "data": json.dumps(step.model_dump(), default=str),
                }

            completed_session = engine.get_session(session_id)
            yield {
                "event": "complete",
                "data": json.dumps({
                    "session_id": session_id,
                    "status": completed_session.status.value if completed_session else "unknown",
                    "result": completed_session.result if completed_session else None,
                }, default=str),
            }

        except Exception as e:
            logger.error("policy_stream_error", session_id=session_id, error=str(e))
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/result/{session_id}")
async def get_policy_result(session_id: str) -> dict[str, Any]:
    """Get the final result of a policy generation or enforcement session."""
    engine = get_agent_engine()
    session = engine.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status.value not in ("completed", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Session is still {session.status.value}",
        )

    return {
        "session_id": session_id,
        "status": session.status.value,
        "result": session.result,
        "steps": [step.model_dump() for step in session.steps],
    }


@router.post("/cancel/{session_id}")
async def cancel_policy_session(session_id: str) -> dict[str, str]:
    """Cancel a running policy session."""
    engine = get_agent_engine()

    try:
        await engine.cancel_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"session_id": session_id, "status": "cancelled"}
