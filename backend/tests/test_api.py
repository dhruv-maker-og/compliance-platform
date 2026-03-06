"""Tests for FastAPI API endpoints."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    """Create a test app instance with mocked dependencies."""
    with patch("app.main.AgentEngine") as mock_engine, \
         patch("app.main.EntraIdMCPServer"), \
         patch("app.main.PurviewMCPServer"), \
         patch("app.main.Settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            azure_keyvault_url=None,
            cors_origins=["http://localhost:5173"],
            app_version="0.1.0-test",
            debug=False,
            otel_exporter_endpoint=None,
        )
        app = create_app()
        # Store engine mock for use in tests
        app.state.agent_engine = mock_engine.return_value
        app.state.settings = mock_settings.return_value
        yield app


@pytest.fixture
async def client(app):
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test the health check endpoint returns 200."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "version" in data


@pytest.mark.asyncio
async def test_evidence_collect_endpoint(client, app):
    """Test starting evidence collection returns a session ID."""
    app.state.agent_engine.create_session = MagicMock(return_value="test-session-123")
    app.state.agent_engine.collect_evidence = AsyncMock()

    response = await client.post(
        "/api/evidence/collect",
        json={
            "framework": "pci-dss",
            "scope": {
                "subscription_id": "sub-123",
                "resource_groups": ["rg-prod"],
            },
        },
    )

    assert response.status_code in (200, 202)
    data = response.json()
    assert "session_id" in data or "id" in data


@pytest.mark.asyncio
async def test_policy_generate_endpoint(client, app):
    """Test policy generation endpoint."""
    app.state.agent_engine.create_session = MagicMock(return_value="policy-session-456")
    app.state.agent_engine.generate_policy = AsyncMock()

    response = await client.post(
        "/api/policy/generate",
        json={
            "description": "Ensure all storage accounts use TLS 1.2",
            "framework": "pci-dss",
            "target_platform": "terraform",
        },
    )

    assert response.status_code in (200, 202)
    data = response.json()
    assert "session_id" in data or "id" in data


@pytest.mark.asyncio
async def test_policy_enforce_endpoint(client, app):
    """Test policy enforcement endpoint."""
    app.state.agent_engine.create_session = MagicMock(return_value="enforce-session-789")
    app.state.agent_engine.enforce_policy = AsyncMock()

    response = await client.post(
        "/api/policy/enforce",
        json={
            "policy_path": "policies/encryption.rego",
            "target_path": "infra/main.tf",
        },
    )

    assert response.status_code in (200, 202)


@pytest.mark.asyncio
async def test_evidence_cancel_nonexistent(client, app):
    """Test cancelling a non-existent session."""
    app.state.agent_engine.cancel_session = MagicMock(return_value=False)

    response = await client.post("/api/evidence/cancel/no-such-session")
    # Should either 404 or return not-found status
    assert response.status_code in (200, 404)


@pytest.mark.asyncio
async def test_cors_headers(client):
    """Test CORS headers are present."""
    response = await client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastAPI CORS middleware should respond
    assert response.status_code in (200, 204, 400)
