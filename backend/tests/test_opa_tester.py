"""Tests for the opa_tester tool."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.tools.opa_tester import opa_eval, opa_test, validate_rego_syntax


SAMPLE_REGO = """
package compliance.encryption

deny[msg] {
    resource := input.resources[_]
    resource.type == "azurerm_storage_account"
    not resource.values.min_tls_version
    msg := sprintf("Storage account '%s' missing min_tls_version", [resource.values.name])
}
"""

SAMPLE_INPUT = {
    "resources": [
        {
            "type": "azurerm_storage_account",
            "values": {
                "name": "mystorage",
                "min_tls_version": "TLS1_2",
            },
        }
    ]
}


def _make_process_mock(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Create a mock subprocess result."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(
        return_value=(stdout.encode(), stderr.encode())
    )
    proc.returncode = returncode
    return proc


@pytest.mark.asyncio
async def test_opa_eval_no_violations():
    """Test opa_eval returns empty violations for compliant input."""
    opa_output = json.dumps({"result": [{"expressions": [{"value": []}]}]})
    with patch("asyncio.create_subprocess_exec", return_value=_make_process_mock(stdout=opa_output)):
        result = await opa_eval(SAMPLE_REGO, SAMPLE_INPUT)

    assert result["success"] is True
    assert result["violations"] == []


@pytest.mark.asyncio
async def test_opa_eval_with_violations():
    """Test opa_eval correctly extracts violations."""
    violations_data = ["Storage account 'test' missing min_tls_version"]
    opa_output = json.dumps(
        {"result": [{"expressions": [{"value": violations_data}]}]}
    )
    with patch("asyncio.create_subprocess_exec", return_value=_make_process_mock(stdout=opa_output)):
        result = await opa_eval(SAMPLE_REGO, SAMPLE_INPUT)

    assert result["success"] is True
    assert len(result["violations"]) == 1


@pytest.mark.asyncio
async def test_opa_eval_timeout():
    """Test opa_eval handles timeout gracefully."""
    import asyncio

    proc = AsyncMock()
    proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    proc.kill = MagicMock()

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await opa_eval(SAMPLE_REGO, SAMPLE_INPUT)

    assert result["success"] is False
    assert "timeout" in result.get("error", "").lower() or result.get("violations") == []


@pytest.mark.asyncio
async def test_opa_eval_command_failure():
    """Test opa_eval handles OPA binary errors."""
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_make_process_mock(stderr="opa: command not found", returncode=1),
    ):
        result = await opa_eval(SAMPLE_REGO, SAMPLE_INPUT)

    assert result["success"] is False


@pytest.mark.asyncio
async def test_opa_test_passing():
    """Test opa_test with all tests passing."""
    opa_output = json.dumps([
        {"name": "test_deny_missing_tls", "package": "compliance.encryption", "fail": False}
    ])
    with patch("asyncio.create_subprocess_exec", return_value=_make_process_mock(stdout=opa_output)):
        result = await opa_test("/tmp/policies")

    assert result["success"] is True


@pytest.mark.asyncio
async def test_opa_test_failures():
    """Test opa_test with failing tests."""
    opa_output = json.dumps([
        {"name": "test_deny_missing_tls", "package": "compliance.encryption", "fail": True}
    ])
    with patch("asyncio.create_subprocess_exec", return_value=_make_process_mock(stdout=opa_output)):
        result = await opa_test("/tmp/policies")

    assert result["success"] is True
    assert result.get("total", 0) >= 1


@pytest.mark.asyncio
async def test_validate_rego_syntax_valid():
    """Test validate_rego_syntax with valid Rego."""
    with patch("asyncio.create_subprocess_exec", return_value=_make_process_mock(returncode=0)):
        result = await validate_rego_syntax(SAMPLE_REGO)

    assert result["valid"] is True


@pytest.mark.asyncio
async def test_validate_rego_syntax_invalid():
    """Test validate_rego_syntax with invalid Rego."""
    with patch(
        "asyncio.create_subprocess_exec",
        return_value=_make_process_mock(stderr="1 error(s): rego_parse_error", returncode=1),
    ):
        result = await validate_rego_syntax("not valid rego {{{}}")

    assert result["valid"] is False
    assert len(result.get("errors", [])) > 0 or "error" in str(result).lower()
