"""Copilot SDK session runner — executes compliance & policy workflows.

This module replaces the placeholder ``_execute_agent()`` in engine.py with
real Copilot SDK calls. It:

1. Creates a Copilot session with compliance tools + hooks
2. Sends the workflow prompt and collects streaming events
3. Extracts structured results from the agent's response
4. Emits ``AgentStep`` updates back to the caller
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import structlog

from app.copilot.client import get_copilot_client_manager
from app.copilot.hooks import get_compliance_hooks
from app.copilot.tools import get_compliance_tools

logger = structlog.get_logger(__name__)

# ── System prompts ──────────────────────────────────────────────────────

_COMPLIANCE_SYSTEM_PROMPT = """\
You are a compliance evidence-collection agent for the ComplianceRewind \
platform. You operate under strict guardrails defined in AGENTS.md:

RULES:
- You MUST use the provided tools (evidence_assembler, gap_analyzer, \
  compliance_report) for your work.
- NEVER make compliance pass/fail verdicts using your own reasoning. \
  Always delegate to the gap_analyzer tool for deterministic evaluation.
- NEVER execute destructive commands.
- NEVER expose raw secrets, tokens, or passwords in your responses.
- If you are uncertain about a control verdict, flag it for human review.

AVAILABLE MCP SERVERS (read-only):
- azure: Azure resource queries, NSG rules, Defender recommendations
- github: Repository settings, branch protections, code search
- entra-id: Entra ID directory roles, conditional access, MFA status
- purview: Data classifications, sensitivity labels, scan results

WORKFLOW:
1. Collect evidence from MCP servers for each control
2. Call evidence_assembler_tool to structure findings by control ID
3. Call gap_analyzer_tool to get deterministic pass/fail verdicts
4. Call compliance_report_tool to generate the final report
5. Return the completed report JSON
"""

_POLICY_SYSTEM_PROMPT = """\
You are a policy-as-code generation agent for the Policy Enforcer \
platform. You follow the skill instructions and guardrails in AGENTS.md:

RULES:
- Generate valid OPA Rego policies from natural-language intent.
- Always generate a corresponding test file with positive & negative cases.
- Use opa_eval_tool and opa_test_tool to validate generated policies.
- NEVER execute destructive commands or modify production infrastructure.
- Create pull requests for any policy fixes (via the GitHub MCP server).

WORKFLOW:
1. Parse the user's policy intent
2. Generate a Rego policy file following OPA best practices
3. Generate a test file with coverage for the policy
4. Validate with opa_test_tool
5. Return the policy content, test content, and suggested file paths
"""


# ── Session runner ──────────────────────────────────────────────────────


async def run_copilot_session(
    prompt: str,
    *,
    mode: str = "compliance",
    model: str = "gpt-4.1",
    on_event: Any | None = None,
) -> dict[str, Any]:
    """Execute a full Copilot SDK session and return structured results.

    Args:
        prompt: The workflow prompt (built by engine.py).
        mode: ``"compliance"`` or ``"policy"``.
        model: LLM model to use.
        on_event: Optional callback ``(event) -> None`` for streaming.

    Returns:
        Dict with the agent's structured output (evidence, report, etc.).
    """
    manager = get_copilot_client_manager()

    if not manager.is_running:
        await manager.start()

    system_message = (
        _COMPLIANCE_SYSTEM_PROMPT if mode == "compliance"
        else _POLICY_SYSTEM_PROMPT
    )

    tools = get_compliance_tools()
    hooks = get_compliance_hooks()

    session = await manager.create_session(
        tools=tools,
        system_message=system_message,
        model=model,
        streaming=True,
        hooks=hooks,
    )

    collected_content: list[str] = []
    done = asyncio.Event()

    def _handle_event(event: Any) -> None:
        event_type = getattr(event, "type", None)
        if event_type is None:
            return

        event_type_str = event_type.value if hasattr(event_type, "value") else str(event_type)

        if event_type_str == "assistant.message_delta":
            delta = getattr(event.data, "delta_content", "") or ""
            collected_content.append(delta)
            if on_event:
                on_event(event)

        elif event_type_str == "assistant.message":
            content = getattr(event.data, "content", "") or ""
            if content and not collected_content:
                collected_content.append(content)
            if on_event:
                on_event(event)

        elif event_type_str == "session.idle":
            done.set()

        elif on_event:
            on_event(event)

    session.on(_handle_event)

    logger.info("copilot_session_send", mode=mode, prompt_length=len(prompt))
    await session.send({"prompt": prompt})

    # Wait for completion (with timeout)
    try:
        await asyncio.wait_for(done.wait(), timeout=300.0)
    except asyncio.TimeoutError:
        logger.warning("copilot_session_timeout", mode=mode)

    await session.destroy()

    # Parse the agent's final output
    full_response = "".join(collected_content)
    result = _parse_agent_response(full_response)

    logger.info(
        "copilot_session_complete",
        mode=mode,
        response_length=len(full_response),
    )

    return result


def _parse_agent_response(response: str) -> dict[str, Any]:
    """Extract structured JSON from the agent's free-text response.

    The agent is instructed to return JSON, but may wrap it in markdown
    code fences. This function extracts the first valid JSON object.
    """
    # Try direct parse
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from markdown code fence
    import re
    json_match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Return the raw response wrapped in a result dict
    return {
        "raw_response": response,
        "evidence": {},
        "assessments": [],
        "report": {},
        "policy_content": "",
        "test_content": "",
        "policy_path": "",
        "test_path": "",
        "summary": response[:500] if response else "No response from agent",
    }


async def run_copilot_streaming(
    prompt: str,
    *,
    mode: str = "compliance",
    model: str = "gpt-4.1",
) -> AsyncIterator[dict[str, Any]]:
    """Execute a Copilot session and yield streaming events.

    Yields dicts with ``{"type": str, "content": str}`` for each
    event received from the agent.
    """
    manager = get_copilot_client_manager()

    if not manager.is_running:
        await manager.start()

    system_message = (
        _COMPLIANCE_SYSTEM_PROMPT if mode == "compliance"
        else _POLICY_SYSTEM_PROMPT
    )

    tools = get_compliance_tools()
    hooks = get_compliance_hooks()

    session = await manager.create_session(
        tools=tools,
        system_message=system_message,
        model=model,
        streaming=True,
        hooks=hooks,
    )

    event_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    def _handle_event(event: Any) -> None:
        event_type = getattr(event, "type", None)
        if event_type is None:
            return

        event_type_str = event_type.value if hasattr(event_type, "value") else str(event_type)

        if event_type_str == "assistant.message_delta":
            delta = getattr(event.data, "delta_content", "") or ""
            event_queue.put_nowait({"type": "delta", "content": delta})

        elif event_type_str == "assistant.message":
            content = getattr(event.data, "content", "") or ""
            event_queue.put_nowait({"type": "message", "content": content})

        elif event_type_str == "session.idle":
            event_queue.put_nowait(None)  # sentinel

        elif event_type_str.startswith("tool."):
            event_queue.put_nowait({
                "type": "tool",
                "content": event_type_str,
            })

    session.on(_handle_event)
    await session.send({"prompt": prompt})

    while True:
        try:
            item = await asyncio.wait_for(event_queue.get(), timeout=300.0)
        except asyncio.TimeoutError:
            break

        if item is None:
            break

        yield item

    await session.destroy()
