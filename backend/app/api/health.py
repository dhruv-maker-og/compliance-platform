"""Health check endpoint."""

from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter

from app.agent.engine import get_agent_engine
from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Return platform health status."""
    settings = get_settings()
    engine = get_agent_engine()

    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.environment,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "components": {
            "agent_engine": "ready" if engine._initialized else "not_initialized",
            "skills_loaded": len(engine._skills) if engine._initialized else 0,
            "active_sessions": len(engine._sessions),
        },
    }
