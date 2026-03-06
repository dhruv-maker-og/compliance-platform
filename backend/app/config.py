"""Compliance Platform Backend — configuration module.

Loads settings from environment variables (with .env fallback)
and from Azure Key Vault when running in Azure.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env / Key Vault."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── General ──────────────────────────────────────────────────────────
    app_name: str = "ComplianceRewind & Policy Enforcer"
    environment: str = Field(default="development", description="development | staging | production")
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: str = Field(default="http://localhost:5173", description="Comma-separated origins")

    # ── Agent / Copilot SDK ──────────────────────────────────────────────
    github_token: str = Field(default="", description="GitHub PAT for Copilot CLI / SDK + GitHub MCP")
    copilot_cli_path: str = Field(default="copilot", description="Path to Copilot CLI binary")
    copilot_cli_url: str = Field(default="", description="URL of external Copilot CLI server (e.g. localhost:4321)")
    copilot_model: str = Field(default="gpt-4.1", description="LLM model for Copilot SDK sessions")
    agent_session_timeout_minutes: int = 60
    agent_max_tool_calls: int = 100
    mcp_config_path: str = Field(default="mcp-config/mcp.json")
    skills_base_path: str = Field(default="skills")

    # ── Azure ────────────────────────────────────────────────────────────
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_subscription_id: str = ""
    azure_keyvault_url: Optional[str] = Field(default=None, description="https://<name>.vault.azure.net/")

    # ── Entra ID / Graph API ─────────────────────────────────────────────
    graph_client_id: str = ""
    graph_client_secret: str = ""

    # ── Purview ──────────────────────────────────────────────────────────
    purview_account_name: str = ""
    purview_client_id: str = ""
    purview_client_secret: str = ""

    # ── Observability ────────────────────────────────────────────────────
    applicationinsights_connection_string: str = ""
    otel_service_name: str = "compliance-platform"
    otel_exporter_otlp_endpoint: str = ""

    # ── Session Store ────────────────────────────────────────────────────
    redis_url: Optional[str] = Field(default=None, description="redis://host:6379/0")
    session_ttl_seconds: int = 3600

    # ── Teams Notifications ──────────────────────────────────────────────
    teams_webhook_url: Optional[str] = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance (cached)."""
    return Settings()


async def load_keyvault_secrets(settings: Settings) -> None:
    """Overlay secrets from Azure Key Vault onto settings (production mode).

    Only runs when ``azure_keyvault_url`` is configured.  Secrets in Key Vault
    follow the naming convention ``secret-name`` → ``SECRET_NAME`` env‑var.
    """
    if not settings.azure_keyvault_url:
        return

    from azure.identity.aio import DefaultAzureCredential
    from azure.keyvault.secrets.aio import SecretClient

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=settings.azure_keyvault_url, credential=credential)

    secret_map = {
        "github-token": "GITHUB_TOKEN",
        "azure-client-secret": "AZURE_CLIENT_SECRET",
        "graph-client-secret": "GRAPH_CLIENT_SECRET",
        "purview-client-secret": "PURVIEW_CLIENT_SECRET",
        "appinsights-connection-string": "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "redis-url": "REDIS_URL",
        "teams-webhook-url": "TEAMS_WEBHOOK_URL",
    }

    for kv_name, env_name in secret_map.items():
        try:
            secret = await client.get_secret(kv_name)
            if secret.value:
                os.environ[env_name] = secret.value
        except Exception:
            pass  # secret may not exist; that's fine

    await credential.close()
    await client.close()

    # Bust the settings cache so it picks up new env vars
    get_settings.cache_clear()
