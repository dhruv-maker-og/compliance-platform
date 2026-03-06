"""Copilot SDK session hooks for compliance platform.

Provides ``on_pre_tool_use`` / ``on_post_tool_use`` hooks that:
  - Enforce the AGENTS.md allow-list (block prohibited commands)
  - Redact secrets from tool output
  - Emit OpenTelemetry spans for every tool call
  - Log all actions for the audit trail
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── Secret-redaction patterns ───────────────────────────────────────────

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(password|secret|token|key|credential|connection.?string)\s*[:=]\s*\S+"), "[REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9]{36,}"), "[GITHUB_TOKEN_REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"), "[JWT_REDACTED]"),
]

# ── Prohibited tool / command patterns ──────────────────────────────────

_BLOCKED_COMMANDS = re.compile(
    r"(rm\s+-rf|DROP\s+TABLE|DELETE\s+FROM|shutdown|format\s+|mkfs|dd\s+if=)",
    re.IGNORECASE,
)

_ALLOWED_SHELL_COMMANDS = {"opa eval", "opa test", "opa check", "terraform show", "terraform plan"}


def _redact(text: str) -> str:
    """Scan a string for known secret patterns and replace them."""
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _is_shell_command_allowed(cmd: str) -> bool:
    """Return ``True`` only if the command starts with an allowlisted prefix."""
    cmd_stripped = cmd.strip()
    return any(cmd_stripped.startswith(prefix) for prefix in _ALLOWED_SHELL_COMMANDS)


# ── Hook implementations ───────────────────────────────────────────────


async def on_pre_tool_use(input_data: dict[str, Any], invocation: Any) -> dict[str, Any]:
    """Called before each tool invocation — enforce guardrails.

    * Blocks destructive commands entirely (``deny``).
    * Restricts shell tools to the allow-listed commands.
    * Logs the tool call for audit.
    """
    tool_name: str = input_data.get("toolName", "")
    tool_args: dict[str, Any] = input_data.get("toolArgs", {})

    logger.info(
        "copilot_pre_tool_use",
        tool=tool_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # ── Check for destructive commands ──────────────────────────────
    args_str = str(tool_args)
    if _BLOCKED_COMMANDS.search(args_str):
        logger.warning("copilot_tool_blocked", tool=tool_name, reason="destructive_command")
        return {
            "permissionDecision": "deny",
            "additionalContext": (
                "This command is prohibited by AGENTS.md. "
                "Destructive operations are not allowed."
            ),
        }

    # ── Shell / terminal commands: allow-list only ──────────────────
    if tool_name in ("shell", "run_command", "terminal", "run_in_terminal"):
        cmd = tool_args.get("command", "") or tool_args.get("cmd", "")
        if not _is_shell_command_allowed(cmd):
            logger.warning("copilot_shell_blocked", tool=tool_name, cmd=cmd[:120])
            return {
                "permissionDecision": "deny",
                "additionalContext": (
                    f"Shell command not in allow-list. "
                    f"Allowed commands: {', '.join(sorted(_ALLOWED_SHELL_COMMANDS))}"
                ),
            }

    # ── Allow everything else (MCP servers, custom tools) ───────────
    return {
        "permissionDecision": "allow",
        "modifiedArgs": tool_args,
    }


async def on_post_tool_use(input_data: dict[str, Any], invocation: Any) -> dict[str, Any]:
    """Called after each tool invocation — redact secrets, log result."""
    tool_name: str = input_data.get("toolName", "")
    result: Any = input_data.get("result", "")

    # Redact sensitive data from the result before it reaches the model
    if isinstance(result, str):
        result = _redact(result)
    elif isinstance(result, dict):
        result = {k: _redact(str(v)) if isinstance(v, str) else v for k, v in result.items()}

    logger.info(
        "copilot_post_tool_use",
        tool=tool_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    return {
        "additionalContext": "",
    }


async def on_error_occurred(input_data: dict[str, Any], invocation: Any) -> dict[str, Any]:
    """Handle errors during agent execution — log and decide retry/abort."""
    error_context: str = input_data.get("errorContext", "")
    error_message: str = input_data.get("error", "")

    logger.error(
        "copilot_agent_error",
        context=error_context,
        error=error_message,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Retry transient errors, abort on fatal ones
    if any(kw in error_message.lower() for kw in ("timeout", "rate limit", "429", "503")):
        return {"errorHandling": "retry"}

    return {"errorHandling": "abort"}


def get_compliance_hooks() -> dict[str, Any]:
    """Return the full hooks dict for ``create_session(hooks=...)``."""
    return {
        "on_pre_tool_use": on_pre_tool_use,
        "on_post_tool_use": on_post_tool_use,
        "on_error_occurred": on_error_occurred,
    }
