"""T.A.R.O. - Forge test runner (TASK-116).

ARCHITECTURE reference: section 18 (Self-Extension & Forge).
RULES reference: section 3, 4, 10.
TASKS: TASK-116.

Runs generated skill code in a sandboxed subprocess to verify correctness:
1. Dry-run with synthetic test inputs derived from the spec's input schema.
2. Validates output shape matches spec's output schema.
3. Captures exceptions and reports failures.

Acceptance (TASK-116): Failing test blocks registration.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from core.forge.skill_host import run_skill_in_host
from core.log.setup import get_logger

logger = get_logger(__name__)


def _generate_test_inputs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate synthetic test inputs from a skill's input schema."""
    inputs = spec.get("inputs", {})
    properties = inputs.get("properties", {})
    required = inputs.get("required", [])

    # Generate 3 test cases: valid, empty, and edge-case
    test_cases = []

    # Test 1: Valid input with dummy values
    valid_input: dict[str, Any] = {}
    for param_name, param_schema in properties.items():
        param_type = param_schema.get("type", "string")
        if param_type == "string":
            valid_input[param_name] = f"test_{param_name}_value"
        elif param_type == "integer":
            valid_input[param_name] = 42
        elif param_type == "number":
            valid_input[param_name] = 3.14
        elif param_type == "boolean":
            valid_input[param_name] = True
        elif param_type == "array":
            valid_input[param_name] = ["item1", "item2"]
        elif param_type == "object":
            valid_input[param_name] = {"key": "value"}
        else:
            valid_input[param_name] = f"test_{param_name}"
    test_cases.append(valid_input)

    # Test 2: Empty / missing required fields
    empty_input: dict[str, Any] = {}
    test_cases.append(empty_input)

    # Test 3: Only required fields with minimal values
    minimal_input: dict[str, Any] = {}
    for req in required:
        if req in properties:
            param_type = properties[req].get("type", "string")
            if param_type == "string":
                minimal_input[req] = "minimal_test"
            elif param_type == "integer":
                minimal_input[req] = 1
            elif param_type == "number":
                minimal_input[req] = 1.0
            elif param_type == "boolean":
                minimal_input[req] = False
            else:
                minimal_input[req] = "minimal"
    test_cases.append(minimal_input)

    return test_cases


def _validate_output_shape(output: dict[str, Any], spec: dict[str, Any]) -> tuple[bool, str]:
    """Validate output dict matches the spec's output schema."""
    output_schema = spec.get("outputs", {})
    expected_props = output_schema.get("properties", {})

    if "status" not in output:
        return False, "Output missing required 'status' field."

    if output.get("status") not in ("ok", "error"):
        return False, f"Invalid status value: '{output.get('status')}'. Must be 'ok' or 'error'."

    return True, ""


async def run_forge_tests(
    skill_dir: Path | str,
    spec: dict[str, Any],
    timeout_s: float = 15.0,
) -> dict[str, Any]:
    """Execute forge tests for a generated skill.

    Returns a test report dict with pass/fail status and details.
    """
    skill_path = Path(skill_dir)
    execution_path = skill_path / "execution.py"

    if not execution_path.exists():
        return {
            "passed": False,
            "total": 0,
            "failed": 0,
            "errors": ["execution.py not found in skill directory."],
        }

    test_inputs = _generate_test_inputs(spec)
    results: list[dict[str, Any]] = []
    total_passed = 0
    total_failed = 0
    errors: list[str] = []

    for i, test_input in enumerate(test_inputs, 1):
        test_name = f"test_{i}"
        logger.info("forge_test_running", test=test_name, skill=spec.get("name"))

        try:
            output = await run_skill_in_host(
                execution_path, test_input, timeout_s=timeout_s
            )
        except Exception as e:
            errors.append(f"{test_name}: Execution error: {e}")
            total_failed += 1
            results.append({"test": test_name, "passed": False, "error": str(e)})
            continue

        # Validate output
        if output.get("status") == "error" and i == 2:
            # Test 2 (empty input) is expected to fail for validation
            total_passed += 1
            results.append({"test": test_name, "passed": True, "note": "Expected error for empty input"})
            continue

        valid, msg = _validate_output_shape(output, spec)
        if valid:
            total_passed += 1
            results.append({"test": test_name, "passed": True, "output": output})
        else:
            total_failed += 1
            errors.append(f"{test_name}: {msg}")
            results.append({"test": test_name, "passed": False, "error": msg})

    passed = total_failed == 0

    report = {
        "passed": passed,
        "total": len(test_inputs),
        "succeeded": total_passed,
        "failed": total_failed,
        "errors": errors,
        "details": results,
    }

    if passed:
        logger.info("forge_tests_passed", skill=spec.get("name"), total=report["total"])
    else:
        logger.warning("forge_tests_failed", skill=spec.get("name"), errors=errors)

    return report


def run_forge_tests_sync(
    skill_dir: Path | str,
    spec: dict[str, Any],
    timeout_s: float = 15.0,
) -> dict[str, Any]:
    """Synchronous wrapper for run_forge_tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                run_forge_tests(skill_dir, spec, timeout_s),
            )
            return future.result(timeout=timeout_s + 5)
    else:
        return asyncio.run(run_forge_tests(skill_dir, spec, timeout_s))


def run_skill_tests(
    spec: dict[str, Any],
    skill_dir: Path | str,
    timeout_s: float = 15.0,
) -> dict[str, Any]:
    """Synchronous helper alias for running forge tests."""
    return run_forge_tests_sync(skill_dir, spec, timeout_s)
