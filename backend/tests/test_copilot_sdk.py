"""Tests for Copilot SDK integration — client, tools, hooks, session."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Hooks tests
# ---------------------------------------------------------------------------


class TestCopilotHooks:
    """Tests for the pre/post tool-use hooks and guardrails."""

    @pytest.mark.asyncio
    async def test_pre_tool_use_allows_normal_tools(self):
        from app.copilot.hooks import on_pre_tool_use

        result = await on_pre_tool_use(
            {"toolName": "evidence_assembler_tool", "toolArgs": {"raw": "{}"}},
            None,
        )
        assert result["permissionDecision"] == "allow"

    @pytest.mark.asyncio
    async def test_pre_tool_use_blocks_destructive_commands(self):
        from app.copilot.hooks import on_pre_tool_use

        result = await on_pre_tool_use(
            {"toolName": "shell", "toolArgs": {"command": "rm -rf /"}},
            None,
        )
        assert result["permissionDecision"] == "deny"

    @pytest.mark.asyncio
    async def test_pre_tool_use_blocks_sql_drop(self):
        from app.copilot.hooks import on_pre_tool_use

        result = await on_pre_tool_use(
            {"toolName": "run_command", "toolArgs": {"command": "DROP TABLE users"}},
            None,
        )
        assert result["permissionDecision"] == "deny"

    @pytest.mark.asyncio
    async def test_pre_tool_use_allows_opa_eval(self):
        from app.copilot.hooks import on_pre_tool_use

        result = await on_pre_tool_use(
            {"toolName": "shell", "toolArgs": {"command": "opa eval data.policy.deny"}},
            None,
        )
        assert result["permissionDecision"] == "allow"

    @pytest.mark.asyncio
    async def test_pre_tool_use_blocks_non_allowlisted_shell(self):
        from app.copilot.hooks import on_pre_tool_use

        result = await on_pre_tool_use(
            {"toolName": "shell", "toolArgs": {"command": "curl http://evil.com"}},
            None,
        )
        assert result["permissionDecision"] == "deny"

    @pytest.mark.asyncio
    async def test_post_tool_use_redacts_secrets(self):
        from app.copilot.hooks import on_post_tool_use

        # The hook should not crash and should return a dict
        result = await on_post_tool_use(
            {"toolName": "read_file", "result": "password=SuperSecret123"},
            None,
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_error_hook_retries_on_timeout(self):
        from app.copilot.hooks import on_error_occurred

        result = await on_error_occurred(
            {"errorContext": "tool_call", "error": "Request timeout after 30s"},
            None,
        )
        assert result["errorHandling"] == "retry"

    @pytest.mark.asyncio
    async def test_error_hook_aborts_on_fatal(self):
        from app.copilot.hooks import on_error_occurred

        result = await on_error_occurred(
            {"errorContext": "session", "error": "Authentication failed"},
            None,
        )
        assert result["errorHandling"] == "abort"

    def test_get_compliance_hooks_returns_dict(self):
        from app.copilot.hooks import get_compliance_hooks

        hooks = get_compliance_hooks()
        assert "on_pre_tool_use" in hooks
        assert "on_post_tool_use" in hooks
        assert "on_error_occurred" in hooks


# ---------------------------------------------------------------------------
# Tools tests
# ---------------------------------------------------------------------------


class TestCopilotTools:
    """Tests for the Copilot SDK tool wrappers."""

    def test_get_compliance_tools_returns_list(self):
        from app.copilot.tools import get_compliance_tools

        tools = get_compliance_tools()
        assert isinstance(tools, list)
        assert len(tools) == 6

    @pytest.mark.asyncio
    async def test_evidence_assembler_tool_calls_assembler(self):
        from app.copilot.tools import EvidenceAssemblerParams

        params = EvidenceAssemblerParams(
            raw_evidence_json=json.dumps({"azure:nsg_rules": [{"rule": 1}]}),
            controls_json=json.dumps([
                {"id": "1.1", "requirement": "test", "evidence_sources": ["azure:nsg_rules"]},
            ]),
        )

        with patch("app.tools.evidence_assembler.evidence_assembler", new_callable=AsyncMock) as mock:
            mock.return_value = {"1.1": {"status": "collected"}}
            from app.copilot.tools import evidence_assembler_tool
            result = await evidence_assembler_tool(params)

        parsed = json.loads(result)
        assert "1.1" in parsed

    @pytest.mark.asyncio
    async def test_gap_analyzer_tool_calls_analyzer(self):
        from app.copilot.tools import GapAnalyzerParams

        params = GapAnalyzerParams(
            evidence_bundle_json=json.dumps({"1.1": {"evidence_items": []}}),
            controls_json=json.dumps([{"id": "1.1", "requirement": "test"}]),
        )

        with patch("app.tools.gap_analyzer.gap_analyzer", new_callable=AsyncMock) as mock:
            mock.return_value = {"assessments": [], "summary": {}}
            from app.copilot.tools import gap_analyzer_tool
            result = await gap_analyzer_tool(params)

        parsed = json.loads(result)
        assert "assessments" in parsed


# ---------------------------------------------------------------------------
# Client tests
# ---------------------------------------------------------------------------


class TestCopilotClientManager:
    """Tests for the CopilotClientManager wrapper."""

    def test_singleton_returns_same_instance(self):
        from app.copilot.client import get_copilot_client_manager

        m1 = get_copilot_client_manager()
        m2 = get_copilot_client_manager()
        assert m1 is m2

    def test_client_raises_when_not_started(self):
        from app.copilot.client import CopilotClientManager

        manager = CopilotClientManager()
        with pytest.raises(RuntimeError, match="not been started"):
            _ = manager.client

    def test_is_running_initially_false(self):
        from app.copilot.client import CopilotClientManager

        manager = CopilotClientManager()
        assert manager.is_running is False


# ---------------------------------------------------------------------------
# Session runner tests
# ---------------------------------------------------------------------------


class TestSessionRunner:
    """Tests for the session runner — parse_agent_response."""

    def test_parse_json_response(self):
        from app.copilot.session import _parse_agent_response

        raw = json.dumps({"evidence": {"ctrl1": {}}, "report": "ok"})
        result = _parse_agent_response(raw)
        assert result["evidence"] == {"ctrl1": {}}

    def test_parse_markdown_fenced_json(self):
        from app.copilot.session import _parse_agent_response

        raw = 'Here is the result:\n```json\n{"status": "done"}\n```\nDone!'
        result = _parse_agent_response(raw)
        assert result["status"] == "done"

    def test_parse_fallback_for_plain_text(self):
        from app.copilot.session import _parse_agent_response

        raw = "I could not complete the task."
        result = _parse_agent_response(raw)
        assert "raw_response" in result
        assert result["raw_response"] == raw
