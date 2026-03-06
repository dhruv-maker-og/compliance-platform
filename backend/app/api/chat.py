"""Chat API endpoints — conversational compliance assistant.

POST /api/chat/send        → Send a message (creates session if needed)
GET  /api/chat/stream/{id} → SSE stream of agent response
GET  /api/chat/history/{id}→ Get chat history for a session
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agent.engine import get_agent_engine
from app.models.schemas import (
    ChatSendRequest,
    ChatSessionResponse,
    ExplainGapRequest,
    WhatIfRequest,
    SessionCreatedResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/send", response_model=ChatSessionResponse)
async def chat_send(request: ChatSendRequest) -> ChatSessionResponse:
    """Send a message to the compliance chat agent.

    If ``session_id`` is omitted a new conversational session is created.
    Returns a stream URL for the agent's response.
    """
    engine = get_agent_engine()

    session_id = request.session_id
    if not session_id:
        session = engine.create_chat_session()
        session_id = session.session_id
    else:
        session = engine.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

    # Store the pending user message so the stream handler can pick it up
    session.metadata.setdefault("pending_messages", []).append(request.message)

    logger.info("chat_message_received", session_id=session_id, length=len(request.message))

    return ChatSessionResponse(
        session_id=session_id,
        stream_url=f"/api/chat/stream/{session_id}",
    )


@router.get("/stream/{session_id}")
async def stream_chat_response(
    session_id: str,
    request: Request,
) -> EventSourceResponse:
    """SSE stream of the agent's response to the latest chat message.

    Events:
    - delta: Incremental text chunk from the agent
    - tool_call: Agent is invoking a tool
    - message: Complete assistant message
    - error: Something went wrong
    """
    engine = get_agent_engine()
    session = engine.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        try:
            async for event in engine.run_chat_turn(session_id):
                if await request.is_disconnected():
                    break

                yield {
                    "event": event.get("type", "delta"),
                    "data": json.dumps(event, default=str),
                }

            yield {"event": "done", "data": "{}"}

        except Exception as exc:
            logger.error("chat_stream_error", session_id=session_id, error=str(exc))
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str) -> dict[str, Any]:
    """Return the full message history for a chat session."""
    engine = get_agent_engine()
    session = engine.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "messages": session.metadata.get("history", []),
    }


@router.post("/explain-gap", response_model=ChatSessionResponse)
async def explain_gap(request: ExplainGapRequest) -> ChatSessionResponse:
    """Start a chat session that explains a specific compliance gap.

    Convenience endpoint: creates a new chat session with a pre-built
    prompt asking the agent to explain why a control failed and how to fix it.
    """
    engine = get_agent_engine()
    session = engine.create_chat_session()

    prompt = (
        f"Explain the following compliance gap and provide step-by-step "
        f"remediation guidance.\n\n"
        f"**Control ID**: {request.control_id}\n"
        f"**Assessment**: {request.assessment_json}\n"
        f"**Evidence**: {request.evidence_json}\n\n"
        f"Be specific: mention exact Azure/Entra ID settings to change, "
        f"CLI commands to run, and estimated effort."
    )

    session.metadata.setdefault("pending_messages", []).append(prompt)

    return ChatSessionResponse(
        session_id=session.session_id,
        stream_url=f"/api/chat/stream/{session.session_id}",
    )


@router.post("/what-if", response_model=ChatSessionResponse)
async def what_if_simulation(request: WhatIfRequest) -> ChatSessionResponse:
    """Run a what-if simulation: evaluate all active policies against a plan.

    Creates a chat session that runs every Rego policy in the repo against
    the provided Terraform plan and summarises the results conversationally.
    """
    engine = get_agent_engine()
    session = engine.create_chat_session()

    prompt = (
        "Run a what-if policy simulation. Evaluate ALL active Rego policies "
        "against the following Terraform plan and summarise which resources "
        "comply and which violate policies. Group results by severity.\n\n"
        f"```json\n{request.terraform_plan_json}\n```"
    )

    session.metadata.setdefault("pending_messages", []).append(prompt)

    return ChatSessionResponse(
        session_id=session.session_id,
        stream_url=f"/api/chat/stream/{session.session_id}",
    )
