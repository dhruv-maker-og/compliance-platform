"""Copilot SDK client wrapper — manages CopilotClient lifecycle.

Provides a singleton ``CopilotClientManager`` that:
  - Starts / stops the Copilot CLI server process via the SDK
  - Creates sessions with the compliance-specific tools and hooks
  - Handles authentication (GitHub token or BYOK)
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


class CopilotClientManager:
    """Manages the lifecycle of the Copilot SDK ``CopilotClient``.

    The class wraps ``copilot.CopilotClient`` and exposes convenience
    methods for the compliance platform's agent workflows.
    """

    def __init__(self) -> None:
        self._client: Any | None = None
        self._started = False
        self._settings = get_settings()

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the Copilot CLI server (or connect to an external one)."""
        if self._started:
            return

        try:
            from copilot import CopilotClient  # type: ignore[import-untyped]
        except ImportError:
            logger.error(
                "copilot_sdk_not_installed",
                msg=(
                    "github-copilot-sdk is not installed. "
                    "Install with: pip install github-copilot-sdk"
                ),
            )
            raise RuntimeError(
                "github-copilot-sdk is required. "
                "Install it with: pip install github-copilot-sdk"
            )

        client_opts: dict[str, Any] = {
            "log_level": self._settings.log_level.lower(),
        }

        # CLI path override
        if self._settings.copilot_cli_path and self._settings.copilot_cli_path != "copilot":
            client_opts["cli_path"] = self._settings.copilot_cli_path

        # External CLI server
        if self._settings.copilot_cli_url:
            client_opts["cli_url"] = self._settings.copilot_cli_url

        # GitHub token for authentication
        if self._settings.github_token:
            client_opts["github_token"] = self._settings.github_token

        self._client = CopilotClient(client_opts)
        await self._client.start()
        self._started = True
        logger.info("copilot_client_started", cli_path=client_opts.get("cli_path", "copilot"))

    async def stop(self) -> None:
        """Stop the Copilot CLI server."""
        if self._client and self._started:
            await self._client.stop()
            self._started = False
            logger.info("copilot_client_stopped")

    @property
    def client(self) -> Any:
        """Return the underlying ``CopilotClient`` instance.

        Raises ``RuntimeError`` if not started.
        """
        if not self._started or self._client is None:
            raise RuntimeError("CopilotClient has not been started. Call start() first.")
        return self._client

    @property
    def is_running(self) -> bool:
        return self._started

    # ── Session Helpers ─────────────────────────────────────────────────

    async def create_session(
        self,
        *,
        tools: list[Any] | None = None,
        system_message: str | None = None,
        model: str = "gpt-4.1",
        streaming: bool = True,
        hooks: dict[str, Any] | None = None,
    ) -> Any:
        """Create a new Copilot session with compliance-specific defaults.

        Args:
            tools: List of ``@define_tool``-decorated functions or ``Tool()`` objects.
            system_message: Optional system prompt override.
            model: LLM model name (default: ``"gpt-4.1"``).
            streaming: Enable streaming delta events (default: ``True``).
            hooks: Optional session hook handlers.

        Returns:
            A Copilot ``Session`` object.
        """
        session_config: dict[str, Any] = {
            "model": model,
            "streaming": streaming,
        }

        if tools:
            session_config["tools"] = tools

        if system_message:
            session_config["system_message"] = {"content": system_message}

        if hooks:
            session_config["hooks"] = hooks

        # Connect to MCP servers configured in mcp.json
        mcp_config_path = self._settings.mcp_config_path
        # Note: The SDK can auto-discover MCP servers from configuration.
        # For explicit HTTP-based MCP servers, use mcpServers config.

        session = await self.client.create_session(session_config)
        logger.info("copilot_session_created", model=model, streaming=streaming)
        return session

    async def send_and_wait(
        self,
        session: Any,
        prompt: str,
    ) -> Any:
        """Send a prompt and wait for the full response.

        Args:
            session: An active Copilot session.
            prompt: The user prompt string.

        Returns:
            The final ``assistant.message`` event (or ``None`` on timeout).
        """
        response = await session.send_and_wait({"prompt": prompt})
        return response


# ── Singleton ───────────────────────────────────────────────────────────

_manager: Optional[CopilotClientManager] = None


def get_copilot_client_manager() -> CopilotClientManager:
    """Get or create the singleton ``CopilotClientManager``."""
    global _manager
    if _manager is None:
        _manager = CopilotClientManager()
    return _manager
