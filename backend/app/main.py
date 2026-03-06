"""FastAPI Application — main entry point for the ComplianceRewind platform."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.agent.engine import get_agent_engine
from app.agent.hooks import setup_telemetry
from app.api.chat import router as chat_router
from app.api.evidence import router as evidence_router
from app.api.health import router as health_router
from app.api.policy import router as policy_router
from app.config import get_settings, load_keyvault_secrets
from app.copilot.client import get_copilot_client_manager
from app.mcp.entra_id import EntraIdMCPServer
from app.mcp.purview import PurviewMCPServer

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup & shutdown hooks."""
    settings = get_settings()

    # ── Startup ─────────────────────────────────────────────────────────
    logger.info("starting_compliance_platform", environment=settings.environment)

    # Load Key Vault secrets in production
    if settings.environment == "production" and settings.azure_keyvault_url:
        await load_keyvault_secrets()
        logger.info("keyvault_secrets_loaded")

    # Initialize telemetry
    setup_telemetry()
    logger.info("telemetry_initialized")

    # Initialize MCP servers
    entra_server = EntraIdMCPServer()
    purview_server = PurviewMCPServer()

    try:
        await entra_server.initialize()
        logger.info("entra_id_mcp_ready")
    except Exception as e:
        logger.warning("entra_id_mcp_init_failed", error=str(e))

    try:
        await purview_server.initialize()
        logger.info("purview_mcp_ready")
    except Exception as e:
        logger.warning("purview_mcp_init_failed", error=str(e))

    # Store MCP servers in app state
    app.state.entra_server = entra_server
    app.state.purview_server = purview_server

    # Initialize agent engine
    engine = get_agent_engine()
    logger.info("agent_engine_ready")

    # Initialize Copilot SDK client
    copilot_manager = get_copilot_client_manager()
    try:
        await copilot_manager.start()
        app.state.copilot_manager = copilot_manager
        logger.info("copilot_sdk_ready")
    except Exception as e:
        logger.warning("copilot_sdk_init_failed", error=str(e), hint="Agent will use fallback mode")
        app.state.copilot_manager = None

    logger.info("compliance_platform_started")

    yield

    # ── Shutdown ────────────────────────────────────────────────────────
    logger.info("shutting_down_compliance_platform")

    # Stop Copilot SDK client
    if getattr(app.state, "copilot_manager", None):
        await app.state.copilot_manager.stop()

    await entra_server.close()
    await purview_server.close()
    engine.cleanup_expired_sessions()

    logger.info("compliance_platform_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ComplianceRewind & Policy Enforcer",
        description=(
            "Continuous compliance evidence collection and policy-as-code "
            "enforcement platform powered by GitHub Copilot CLI SDK."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url="/api/redoc" if settings.environment != "production" else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # OpenTelemetry auto-instrumentation
    FastAPIInstrumentor.instrument_app(app)

    # Register routers
    app.include_router(health_router, prefix="/api", tags=["health"])
    app.include_router(evidence_router, prefix="/api/evidence", tags=["evidence"])
    app.include_router(policy_router, prefix="/api/policy", tags=["policy"])
    app.include_router(chat_router, prefix="/api/chat", tags=["chat"])

    return app


app = create_app()
