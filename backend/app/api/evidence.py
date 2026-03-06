"""Evidence collection API endpoints.

POST /api/evidence/collect   → Start a compliance evidence collection session
GET  /api/evidence/stream/{id} → SSE stream of agent progress steps
GET  /api/evidence/report/{id} → Get final compliance report
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.engine import get_agent_engine
from app.models.schemas import (
    EvidenceCollectionRequest,
    SessionCreatedResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/collect", response_model=SessionCreatedResponse)
async def start_evidence_collection(
    request: EvidenceCollectionRequest,
) -> SessionCreatedResponse:
    """Start a new compliance evidence collection session.

    The agent will begin gathering evidence in the background.
    Use the SSE stream endpoint to track progress in real-time.
    """
    engine = get_agent_engine()

    try:
        session = await engine.create_session(mode="compliance")
    except Exception as e:
        logger.error("session_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create session")

    logger.info(
        "evidence_collection_started",
        session_id=session.session_id,
        framework=request.framework,
        scope=request.scope,
    )

    return SessionCreatedResponse(
        session_id=session.session_id,
        status=session.status,
        stream_url=f"/api/evidence/stream/{session.session_id}",
    )


@router.get("/stream/{session_id}")
async def stream_evidence_progress(
    session_id: str,
    request: Request,
) -> EventSourceResponse:
    """SSE stream of agent progress for an evidence collection session.

    Events:
    - step: Agent progress step (tool call, result, status)
    - complete: Final results
    - error: Error occurred
    """
    engine = get_agent_engine()
    session = engine.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        try:
            # Get the original request params from session
            framework = session.metadata.get("framework", "PCI-DSS v4.0")
            scope = session.metadata.get("scope", "")
            controls = session.metadata.get("controls", [])

            async for step in engine.run_compliance_session(
                session_id=session_id,
                framework=framework,
                scope=scope,
                controls=controls,
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("client_disconnected", session_id=session_id)
                    break

                yield {
                    "event": "step",
                    "data": json.dumps(step.model_dump(), default=str),
                }

            # Send completion event
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
            logger.error("stream_error", session_id=session_id, error=str(e))
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/report/{session_id}")
async def get_evidence_report(session_id: str) -> dict[str, Any]:
    """Get the final compliance report for a completed session."""
    engine = get_agent_engine()
    session = engine.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status.value not in ("completed", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Session is still {session.status.value}. Wait for completion.",
        )

    return {
        "session_id": session_id,
        "status": session.status.value,
        "result": session.result,
        "steps": [step.model_dump() for step in session.steps],
        "started_at": session.created_at.isoformat() if session.created_at else None,
    }


@router.post("/cancel/{session_id}")
async def cancel_evidence_collection(session_id: str) -> dict[str, str]:
    """Cancel a running evidence collection session."""
    engine = get_agent_engine()

    try:
        await engine.cancel_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"session_id": session_id, "status": "cancelled"}
