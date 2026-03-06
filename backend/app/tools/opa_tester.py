"""OPA Tester Tool — runs OPA eval/test against Terraform plan JSON.

This tool wraps the `opa eval` and `opa test` CLI commands to:
1. Evaluate Rego policies against a Terraform plan JSON.
2. Run unit tests for Rego policies.
3. Return structured violation results.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _resolve_opa_binary(opa_binary: str) -> str:
    """Resolve OPA executable path from explicit value, env, PATH, or repo bin."""
    if opa_binary and opa_binary != "opa":
        return opa_binary

    env_binary = os.getenv("OPA_BINARY", "").strip()
    if env_binary:
        return env_binary

    path_binary = shutil.which("opa")
    if path_binary:
        return path_binary

    repo_root = Path(__file__).resolve().parents[3]
    candidates = [
        repo_root / "tools" / "bin" / "opa.exe",
        repo_root / "tools" / "bin" / "opa_windows_amd64.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return opa_binary or "opa"


async def _run_subprocess(
    cmd: list[str],
    *,
    timeout: float,
) -> tuple[int, bytes, bytes]:
    """Run a subprocess with asyncio and a Windows-safe fallback."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return process.returncode, stdout, stderr
    except NotImplementedError:
        # Windows selector event loop does not support subprocesses.
        completed = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        return completed.returncode, completed.stdout, completed.stderr


async def opa_eval(
    policy_rego: str,
    terraform_plan_json: dict[str, Any] | str,
    *,
    query: str = "data.policy.deny",
    opa_binary: str = "opa",
) -> dict[str, Any]:
    """Evaluate a Rego policy against a Terraform plan.

    Args:
        policy_rego: The Rego policy source code.
        terraform_plan_json: Terraform plan output (parsed JSON dict or raw string).
        query: OPA query (default: data.policy.deny).
        opa_binary: Path to the opa binary.

    Returns:
        Dict with "violations" list, "passed" bool, and raw "output".
    """
    logger.info("opa_eval_start", query=query)
    opa_binary = _resolve_opa_binary(opa_binary)

    # Normalize plan data
    if isinstance(terraform_plan_json, dict):
        plan_str = json.dumps(terraform_plan_json)
    else:
        plan_str = terraform_plan_json

    with tempfile.TemporaryDirectory(prefix="opa_eval_") as tmpdir:
        policy_path = Path(tmpdir) / "policy.rego"
        input_path = Path(tmpdir) / "input.json"

        policy_path.write_text(policy_rego, encoding="utf-8")
        input_path.write_text(plan_str, encoding="utf-8")

        cmd = [
            opa_binary,
            "eval",
            "--v0-compatible",
            "--data", str(policy_path),
            "--input", str(input_path),
            "--format", "json",
            query,
        ]

        try:
            return_code, stdout, stderr = await _run_subprocess(cmd, timeout=30.0)
        except asyncio.TimeoutError:
            logger.error("opa_eval_timeout")
            return {
                "violations": [],
                "passed": False,
                "output": None,
                "error": "OPA evaluation timed out after 30 seconds",
            }
        except FileNotFoundError:
            logger.error("opa_binary_not_found", binary=opa_binary)
            return {
                "violations": [],
                "passed": False,
                "output": None,
                "error": f"OPA binary not found: {opa_binary}",
            }

        if return_code != 0:
            err_str = stderr.decode("utf-8", errors="replace").strip()
            if not err_str:
                err_str = stdout.decode("utf-8", errors="replace").strip()
            logger.error("opa_eval_failed", stderr=err_str)
            return {
                "violations": [],
                "passed": False,
                "output": None,
                "error": err_str,
            }

        try:
            result = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as e:
            return {
                "violations": [],
                "passed": False,
                "output": stdout.decode("utf-8", errors="replace"),
                "error": f"Invalid JSON from OPA: {e}",
            }

    violations = _extract_violations(result)

    logger.info(
        "opa_eval_complete",
        violations=len(violations),
        passed=len(violations) == 0,
    )

    return {
        "violations": violations,
        "passed": len(violations) == 0,
        "output": result,
        "error": None,
    }


async def opa_test(
    policy_dir: str,
    *,
    opa_binary: str = "opa",
    verbose: bool = True,
) -> dict[str, Any]:
    """Run OPA test against policy files in a directory.

    Args:
        policy_dir: Path to directory containing .rego files and _test.rego files.
        opa_binary: Path to the opa binary.
        verbose: Enable verbose OPA test output.

    Returns:
        Dict with "test_results", "passed" and "summary".
    """
    logger.info("opa_test_start", policy_dir=policy_dir)
    opa_binary = _resolve_opa_binary(opa_binary)

    cmd = [opa_binary, "test", "--v0-compatible", policy_dir, "--format", "json"]
    if verbose:
        cmd.append("-v")

    try:
        return_code, stdout, stderr = await _run_subprocess(cmd, timeout=60.0)
    except asyncio.TimeoutError:
        logger.error("opa_test_timeout")
        return {
            "test_results": [],
            "passed": False,
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "error": "OPA tests timed out after 60 seconds",
        }
    except FileNotFoundError:
        return {
            "test_results": [],
            "passed": False,
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "error": f"OPA binary not found: {opa_binary}",
        }

    try:
        results = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return {
            "test_results": [],
            "passed": return_code == 0,
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "raw_output": stdout.decode("utf-8", errors="replace"),
            "error": None,
        }

    # Parse test results
    test_results = []
    total_passed = 0
    total_failed = 0

    if isinstance(results, list):
        for entry in results:
            name = entry.get("name", "unknown")
            success = entry.get("pass", entry.get("fail") is None)
            duration = entry.get("duration", 0)

            test_results.append({
                "name": name,
                "passed": bool(success),
                "duration_ns": duration,
                "package": entry.get("package", ""),
            })

            if success:
                total_passed += 1
            else:
                total_failed += 1

    total = total_passed + total_failed

    logger.info(
        "opa_test_complete",
        total=total,
        passed=total_passed,
        failed=total_failed,
    )

    return {
        "test_results": test_results,
        "passed": total_failed == 0,
        "summary": {
            "total": total,
            "passed": total_passed,
            "failed": total_failed,
        },
        "error": None,
    }


async def validate_rego_syntax(
    policy_rego: str,
    *,
    opa_binary: str = "opa",
) -> dict[str, Any]:
    """Check Rego policy for syntax errors.

    Args:
        policy_rego: The Rego policy source code.
        opa_binary: Path to the opa binary.

    Returns:
        Dict with "valid" bool and optional "errors".
    """
    with tempfile.TemporaryDirectory(prefix="opa_check_") as tmpdir:
        opa_binary = _resolve_opa_binary(opa_binary)
        policy_path = Path(tmpdir) / "policy.rego"
        policy_path.write_text(policy_rego, encoding="utf-8")

        cmd = [opa_binary, "check", "--v0-compatible", str(policy_path), "--format", "json"]

        try:
            return_code, stdout, stderr = await _run_subprocess(cmd, timeout=15.0)
        except asyncio.TimeoutError:
            return {"valid": False, "errors": ["Syntax check timed out"]}
        except FileNotFoundError:
            return {"valid": False, "errors": [f"OPA binary not found: {opa_binary}"]}

        if return_code == 0:
            return {"valid": True, "errors": []}

        try:
            result = json.loads(stdout.decode("utf-8"))
            errors = result.get("errors", [])
            return {"valid": False, "errors": errors}
        except json.JSONDecodeError:
            return {
                "valid": False,
                "errors": [stderr.decode("utf-8", errors="replace")],
            }


async def opa_eval_explain(
    policy_rego: str,
    terraform_plan_json: dict[str, Any] | str,
    *,
    query: str = "data.policy.deny",
    opa_binary: str = "opa",
    explain_level: str = "full",
) -> dict[str, Any]:
    """Evaluate a Rego policy and return OPA explain trace output.

    Args:
        policy_rego: The Rego policy source code.
        terraform_plan_json: Terraform plan output (parsed JSON dict or raw string).
        query: OPA query (default: data.policy.deny).
        opa_binary: Path to the opa binary.
        explain_level: Explain verbosity (full, notes, fails).

    Returns:
        Dict with explain trace output and optional error.
    """
    logger.info("opa_eval_explain_start", query=query, explain_level=explain_level)
    opa_binary = _resolve_opa_binary(opa_binary)

    if isinstance(terraform_plan_json, dict):
        plan_str = json.dumps(terraform_plan_json)
    else:
        plan_str = terraform_plan_json

    with tempfile.TemporaryDirectory(prefix="opa_explain_") as tmpdir:
        policy_path = Path(tmpdir) / "policy.rego"
        input_path = Path(tmpdir) / "input.json"

        policy_path.write_text(policy_rego, encoding="utf-8")
        input_path.write_text(plan_str, encoding="utf-8")

        cmd = [
            opa_binary,
            "eval",
            "--v0-compatible",
            "--data", str(policy_path),
            "--input", str(input_path),
            "--explain", explain_level,
            query,
        ]

        try:
            return_code, stdout, stderr = await _run_subprocess(cmd, timeout=30.0)
        except asyncio.TimeoutError:
            return {"explain_trace": "", "error": "OPA explain timed out after 30 seconds"}
        except FileNotFoundError:
            return {"explain_trace": "", "error": f"OPA binary not found: {opa_binary}"}

        if return_code != 0:
            err_str = stderr.decode("utf-8", errors="replace").strip()
            if not err_str:
                err_str = stdout.decode("utf-8", errors="replace").strip()
            return {
                "explain_trace": "",
                "error": err_str,
            }

    return {
        "explain_trace": stdout.decode("utf-8", errors="replace"),
        "error": None,
    }


def _extract_violations(opa_output: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract violation messages from OPA eval output.

    OPA eval returns results in the format:
    {
      "result": [
        {
          "expressions": [
            {
              "value": [...],  # set of deny messages
              "text": "data.policy.deny"
            }
          ]
        }
      ]
    }
    """
    violations: list[dict[str, Any]] = []

    results = opa_output.get("result", [])
    for result in results:
        expressions = result.get("expressions", [])
        for expr in expressions:
            value = expr.get("value")
            if isinstance(value, list):
                for item in value:
                    violations.append(_normalize_violation(item))
            elif isinstance(value, set):
                for item in value:
                    violations.append(_normalize_violation(item))
            elif value and value is not True:
                violations.append(_normalize_violation(value))

    return violations


def _normalize_violation(item: Any) -> dict[str, Any]:
    """Normalize a violation into a structured dict."""
    if isinstance(item, dict):
        return {
            "message": item.get("msg", item.get("message", str(item))),
            "resource": item.get("resource", item.get("resource_name", "")),
            "severity": item.get("severity", "high"),
            "raw": item,
        }
    elif isinstance(item, str):
        return {
            "message": item,
            "resource": "",
            "severity": "high",
            "raw": item,
        }
    else:
        return {
            "message": str(item),
            "resource": "",
            "severity": "high",
            "raw": item,
        }
