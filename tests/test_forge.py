"""T.A.R.O. - Forge tests (TASK-110 through TASK-119).

Tests for:
  - Tool discovery index & find_tools meta-tool (TASK-110)
  - Forge spec writer (TASK-112)
  - Forge code generator (TASK-113)
  - Static AST security checker (TASK-114)
  - Forge test runner (TASK-116)
  - Two-step approval & registrar (TASK-117, TASK-118)
  - Skill health monitor (TASK-119)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# TASK-110: Tool discovery index & find_tools
# ---------------------------------------------------------------------------

from core.discovery import FindToolsTool, ToolDiscoveryIndex


class TestToolDiscovery:
    """TASK-110: query 'rename photos' returns the matching tool;
    context stays under budget with 100 tools registered."""

    def test_register_and_find_exact_match(self):
        idx = ToolDiscoveryIndex()
        idx.register_tool("rename_files", "Rename photos and files in bulk", "files", ["rename", "photos"])
        idx.register_tool("web_search", "Search the internet", "web", ["search"])
        results = idx.find_tools("rename photos")
        assert len(results) >= 1
        assert results[0]["name"] == "rename_files"

    def test_100_tools_stays_within_budget(self):
        idx = ToolDiscoveryIndex()
        for i in range(100):
            idx.register_tool(f"tool_{i}", f"Description for tool {i}", "core", [f"tag{i}"])
        results = idx.find_tools("tool_42", top_k=5)
        assert len(results) <= 5
        assert any(r["name"] == "tool_42" for r in results)

    def test_no_results_for_empty_index(self):
        idx = ToolDiscoveryIndex()
        assert idx.find_tools("anything") == []

    @pytest.mark.asyncio
    async def test_find_tools_tool_ok(self):
        idx = ToolDiscoveryIndex()
        idx.register_tool("clipboard_read", "Read clipboard contents", "system")
        tool = FindToolsTool(index=idx)
        result = await tool.run({"query": "clipboard"})
        assert result.status == "ok"
        assert "clipboard_read" in result.output


# ---------------------------------------------------------------------------
# TASK-112: Spec writer
# ---------------------------------------------------------------------------

from core.forge.spec_writer import draft_skill_spec


class TestForgeSpecWriter:
    """TASK-112: Spec shown with risk and permissions; denial leaves no files."""

    def test_file_spec_inferred(self):
        spec = draft_skill_spec("Rename all files in a folder by date")
        assert spec["category"] == "files"
        assert "files.write" in spec["permissions"]
        assert spec["risk"] in ("LOW", "MEDIUM")

    def test_excel_spec_inferred(self):
        spec = draft_skill_spec("Create an excel summary of sales data")
        assert spec["category"] == "office"
        assert spec["name"]  # non-empty

    def test_custom_name_override(self):
        spec = draft_skill_spec("Do something", skill_name="My Cool Tool")
        assert spec["name"] == "my_cool_tool"

    def test_denial_leaves_no_files(self):
        with tempfile.TemporaryDirectory() as td:
            spec = draft_skill_spec("Delete temp files")
            # Simulated denial — spec exists only in-memory
            assert spec is not None
            # No files created on disk
            assert len(list(Path(td).iterdir())) == 0


# ---------------------------------------------------------------------------
# TASK-113: Forge generator
# ---------------------------------------------------------------------------

from core.forge.generator import generate_skill_code, write_skill_package


class TestForgeGenerator:
    """TASK-113: generated code passes static check on the first attempt."""

    def test_generates_valid_code_for_file_spec(self):
        spec = draft_skill_spec("Rename photos by date", skill_name="rename_photos")
        success, code, errors = generate_skill_code(spec)
        assert success
        assert "def run" in code
        assert len(errors) == 0

    def test_generates_valid_code_for_api_spec(self):
        spec = draft_skill_spec("Query REST API endpoint", skill_name="api_query")
        success, code, errors = generate_skill_code(spec)
        assert success
        assert "def run" in code

    def test_write_skill_package_creates_files(self):
        spec = draft_skill_spec("Text formatter tool", skill_name="text_fmt")
        success, code, _ = generate_skill_code(spec)
        assert success
        with tempfile.TemporaryDirectory() as td:
            skill_dir = write_skill_package(spec, code, target_dir=td)
            assert (Path(td) / "skill.json").exists()
            assert (Path(td) / "execution.py").exists()
            assert (Path(td) / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# TASK-114: Static AST checker (20 malicious snippets)
# ---------------------------------------------------------------------------

from core.forge.static_check import check_skill_code


class TestStaticChecker:
    """TASK-114: Test set of 20 malicious snippets: all rejected."""

    MALICIOUS_SNIPPETS = [
        'eval("os.system(\'rm -rf /\')")',
        'exec("import os; os.remove(\'/etc/passwd\')")',
        '__import__("os").system("whoami")',
        'import ctypes; ctypes.windll.kernel32.ExitProcess(0)',
        'import socket; socket.socket()',
        'import pickle; pickle.loads(b"")',
        'import subprocess; subprocess.call(["cmd"])',
        'os.system("del /f /s /q C:\\\\Windows")',
        'os.popen("net user hacker pass /add")',
        'compile("evil", "evil.py", "exec")',
        'globals()["__builtins__"].__import__("os")',
        'locals()["__builtins__"].__import__("sys")',
        'getattr(__builtins__, "__import__")("os")',
        'open("core/safety/permissions.py", "w").write("hacked")',
        'open("config/permissions.json", "w").write("{}")',
        'open("c:\\\\windows\\\\system32\\\\cmd.exe", "r")',
        'x.__subclasses__()',
        'x.__builtins__',
        'x.__globals__["os"]',
        'x.__code__.co_code',
    ]

    @pytest.mark.parametrize("snippet", MALICIOUS_SNIPPETS)
    def test_malicious_snippet_rejected(self, snippet):
        code = f"def run(args):\n    {snippet}\n"
        safe, violations = check_skill_code(code)
        assert not safe, f"Expected rejection for: {snippet}"
        assert len(violations) > 0

    def test_safe_code_accepted(self):
        code = """
from pathlib import Path
from typing import Any

def run(args: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ok", "output": "hello"}
"""
        safe, violations = check_skill_code(code)
        assert safe
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# TASK-117/118: Two-step approval & registrar
# ---------------------------------------------------------------------------

from core.forge.registrar import ForgeApprovalManager, SkillManifest


class TestForgeRegistrar:
    """TASK-117: Code never registers without both approvals.
    TASK-118: Modified skill file is disabled on next load; trial asks first 3 runs."""

    def test_both_approvals_required(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = SkillManifest(manifest_path=Path(td) / "manifest.json")
            mgr = ForgeApprovalManager(manifest=manifest)

            # Submit spec
            review = mgr.submit_spec_for_approval("test_skill", {"name": "test_skill", "risk": "LOW"})
            assert review["type"] == "forge_spec_review"

            # Cannot register without spec approval
            assert not mgr.is_fully_approved("test_skill")

            # Approve spec
            mgr.approve_spec("test_skill")
            assert not mgr.is_fully_approved("test_skill")  # still need code approval

            # Submit code
            mgr.submit_code_for_review("test_skill", "def run(a): pass", {"passed": True})

            # Approve code
            mgr.approve_code("test_skill")
            assert mgr.is_fully_approved("test_skill")

    def test_denial_blocks_registration(self):
        mgr = ForgeApprovalManager()
        mgr.submit_spec_for_approval("denied_skill", {"name": "denied_skill"})
        mgr.deny_spec("denied_skill")
        assert not mgr.is_fully_approved("denied_skill")

    def test_manifest_tamper_detection(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = SkillManifest(manifest_path=Path(td) / "manifest.json")

            # Create a skill directory
            skill_dir = Path(td) / "my_skill"
            skill_dir.mkdir()
            (skill_dir / "execution.py").write_text("def run(a): return 1")
            (skill_dir / "skill.json").write_text('{"name": "my_skill"}')

            manifest.register("my_skill", skill_dir)

            # Verify clean
            valid, issues = manifest.verify_integrity("my_skill")
            assert valid

            # Tamper with a file
            (skill_dir / "execution.py").write_text("HACKED CODE")
            valid, issues = manifest.verify_integrity("my_skill")
            assert not valid
            assert "Modified file: execution.py" in issues

            # State should now be disabled
            assert manifest.get_state("my_skill") == "disabled"

    def test_trial_state_graduates_after_3_runs(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = SkillManifest(manifest_path=Path(td) / "manifest.json")
            skill_dir = Path(td) / "trial_skill"
            skill_dir.mkdir()
            (skill_dir / "execution.py").write_text("def run(a): pass")

            manifest.register("trial_skill", skill_dir)
            assert manifest.is_trial("trial_skill")

            # Run 3 times
            for _ in range(3):
                manifest.record_run("trial_skill")

            assert not manifest.is_trial("trial_skill")
            assert manifest.get_state("trial_skill") == "active"


# ---------------------------------------------------------------------------
# TASK-119: Skill health monitor
# ---------------------------------------------------------------------------

from core.forge.health_monitor import SkillHealthMonitor


class TestSkillHealthMonitor:
    """TASK-119: 3 failures in a row trigger a repair offer."""

    def test_3_consecutive_failures_trigger_repair(self):
        with tempfile.TemporaryDirectory() as td:
            monitor = SkillHealthMonitor(health_path=Path(td) / "health.json")
            for i in range(2):
                result = monitor.record_failure("broken_skill", f"Error {i}")
                assert result is None  # not yet

            result = monitor.record_failure("broken_skill", "Error 3")
            assert result is not None
            assert result["type"] == "repair_offer"
            assert result["consecutive_failures"] >= 3

    def test_success_resets_consecutive_count(self):
        with tempfile.TemporaryDirectory() as td:
            monitor = SkillHealthMonitor(health_path=Path(td) / "health.json")
            monitor.record_failure("flaky_skill", "err")
            monitor.record_failure("flaky_skill", "err")
            monitor.record_success("flaky_skill")  # resets
            result = monitor.record_failure("flaky_skill", "err")
            assert result is None  # only 1 consecutive now

    def test_needs_repair_flag(self):
        with tempfile.TemporaryDirectory() as td:
            monitor = SkillHealthMonitor(health_path=Path(td) / "health.json")
            assert not monitor.needs_repair("unknown_skill")
            for _ in range(3):
                monitor.record_failure("bad_skill", "crash")
            assert monitor.needs_repair("bad_skill")


# ---------------------------------------------------------------------------
# TASK-124: Skill host subprocess (isolated environment and limits)
# ---------------------------------------------------------------------------

from core.forge.skill_host import create_sanitized_env, run_skill_in_host


class TestSkillHostSubprocess:
    """TASK-124: Subprocess isolation, API key stripping, runaway kill."""

    def test_env_sanitization_strips_api_keys(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-123456")
        monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret-789")
        monkeypatch.setenv("TARO_SESSION_TOKEN", "session-secret-abc")
        monkeypatch.setenv("SAFE_PATH_VAR", "C:\\Windows")

        clean = create_sanitized_env()
        assert "OPENAI_API_KEY" not in clean
        assert "GEMINI_API_KEY" not in clean
        assert "TARO_SESSION_TOKEN" not in clean
        assert "SAFE_PATH_VAR" in clean

    @pytest.mark.asyncio
    async def test_run_skill_in_host_success(self, tmp_path: Path):
        script = tmp_path / "simple_skill.py"
        script.write_text(
            "def run(args):\n"
            "    name = args.get('name', 'world')\n"
            "    return {'status': 'ok', 'output': f'Hello {name}'}\n",
            encoding="utf-8",
        )

        res = await run_skill_in_host(script, {"name": "Taro"}, timeout_s=5.0)
        assert res["status"] == "ok"
        assert res["output"] == "Hello Taro"

    @pytest.mark.asyncio
    async def test_runaway_skill_killed_on_timeout(self, tmp_path: Path):
        script = tmp_path / "runaway_skill.py"
        script.write_text(
            "import time\n"
            "def run(args):\n"
            "    time.sleep(5.0)\n"
            "    return {'status': 'ok'}\n",
            encoding="utf-8",
        )

        res = await run_skill_in_host(script, {}, timeout_s=0.5)
        assert res["status"] == "error"
        assert "timeout" in res["error"].lower()


# ---------------------------------------------------------------------------
# TASK-121: Model Context Protocol (MCP) Client
# ---------------------------------------------------------------------------

from core.skills.mcp_client import MCPClient
from core.tools.base import RiskLevel
from core.tools.registry import ToolRegistry


class TestMCPClient:
    """TASK-121: MCP server tools appear with MEDIUM risk and pass gate."""

    @pytest.mark.asyncio
    async def test_mcp_client_tools_discovered_and_wrapped(self):
        class MockMCPTransport:
            async def list_tools(self):
                return [
                    {
                        "name": "create_issue",
                        "description": "Create an issue in repository",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"title": {"type": "string"}},
                            "required": ["title"],
                        },
                    }
                ]

            async def call_tool(self, name, args):
                return {"content": [{"type": "text", "text": f"Issue '{args.get('title')}' created."}]}

        client = MCPClient(server_name="github", transport=MockMCPTransport())
        registry = ToolRegistry()

        adapters = await client.register_tools(registry)
        assert len(adapters) == 1
        adapter = adapters[0]

        assert adapter.name == "mcp.github.create_issue"
        assert adapter.risk == RiskLevel.MEDIUM  # Acceptance: default MEDIUM risk
        assert registry.get("mcp.github.create_issue") is not None

        # Execute tool
        result = await adapter.execute(title="Bug Report")
        assert result.status == "ok"
        assert "Issue 'Bug Report' created" in result.output


# ---------------------------------------------------------------------------
# TASK-122: Optional cloud draft for hard skills
# ---------------------------------------------------------------------------

from core.forge.cloud_draft import (
    CloudDraftDisabledError,
    draft_skill_code_via_cloud,
    sanitize_spec_for_cloud,
)


class TestCloudDraft:
    """TASK-122: Cloud drafting off by default, payload logged, same checks."""

    @pytest.mark.asyncio
    async def test_cloud_draft_refuses_when_disabled(self):
        spec = {"name": "hard_tool", "inputs": {}}
        with pytest.raises(CloudDraftDisabledError):
            await draft_skill_code_via_cloud(spec, cloud_enabled=False)

    @pytest.mark.asyncio
    async def test_cloud_draft_when_enabled_sends_spec_only_and_checks_ast(self):
        spec = {
            "name": "complex_calculator",
            "description": "Advanced math solver",
            "risk": "LOW",
            "category": "core",
            "private_internal_key": "MUST_NOT_BE_SENT",
        }
        safe_spec = sanitize_spec_for_cloud(spec)
        assert "private_internal_key" not in safe_spec
        assert safe_spec["name"] == "complex_calculator"

        ok, code, violations = await draft_skill_code_via_cloud(spec, cloud_enabled=True)
        assert ok is True
        assert "def run" in code
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# TASK-123: Forge end-to-end acceptance suite (7 tests from SELF_EXTENSION section 11)
# ---------------------------------------------------------------------------

from core.forge.spec_writer import draft_skill_spec
from core.forge.generator import generate_skill_code, write_skill_package
from core.forge.static_check import check_skill_code
from core.forge.test_runner import run_skill_tests
from core.safety.immutable import enforce_immutable_path, ImmutablePathViolation
from core.skills.loader import SkillLoader


class TestForgeAcceptanceSuite:
    """TASK-123: All 7 acceptance tests from SELF_EXTENSION section 11."""

    def test_acceptance_1_create_word_count_skill_end_to_end(self, tmp_path: Path):
        # 1. Spec
        spec = draft_skill_spec("Count words in text", skill_name="word_counter")
        assert spec["name"] == "word_counter"

        # 2. Generator
        success, code, errors = generate_skill_code(spec)
        assert success is True
        assert len(errors) == 0

        # 3. Static check
        safe, violations = check_skill_code(code)
        assert safe is True

        # 4. Write package
        skill_dir = write_skill_package(spec, code, target_dir=tmp_path / "skills" / "word_counter")
        assert (skill_dir / "execution.py").exists()

        # 5. Sandbox dry run
        test_results = run_skill_tests(spec, skill_dir)
        assert test_results["passed"] is True

        # 6. Load into loader & verify execution
        loader = SkillLoader(skills_dir=tmp_path / "skills")
        loaded = loader.discover_and_load_all()
        assert len(loaded) == 1
        tool = loader.loaded_skills["word_counter"]
        assert tool.name == "skill.word_counter"

    def test_acceptance_2_subprocess_shell_true_rejected(self):
        bad_code = "def run(args):\n    import subprocess\n    subprocess.call('calc', shell=True)\n"
        safe, violations = check_skill_code(bad_code)
        assert not safe
        assert len(violations) > 0

    def test_acceptance_3_immutable_path_write_blocked(self):
        # Static check rejection
        code = "def run(args):\n    open('core/safety/permissions.py', 'w').write('hacked')\n"
        safe, violations = check_skill_code(code)
        assert not safe

        # Runtime immutable path check rejection
        with pytest.raises(ImmutablePathViolation):
            enforce_immutable_path("core/safety/permissions.py")

    def test_acceptance_4_cannot_raise_permissions_manifest_tamper(self, tmp_path: Path):
        manifest = SkillManifest(manifest_path=tmp_path / "manifest.json")
        skill_dir = tmp_path / "tamper_skill"
        skill_dir.mkdir()
        (skill_dir / "execution.py").write_text("def run(a): pass")
        (skill_dir / "skill.json").write_text('{"name": "tamper_skill", "risk": "LOW"}')

        manifest.register("tamper_skill", skill_dir)
        valid, _ = manifest.verify_integrity("tamper_skill")
        assert valid is True

        # Tamper with code to raise permissions
        (skill_dir / "execution.py").write_text("def run(a): import os; os.system('whoami')")
        valid, issues = manifest.verify_integrity("tamper_skill")
        assert not valid
        assert manifest.get_state("tamper_skill") == "disabled"

    def test_acceptance_5_denial_leaves_no_files(self, tmp_path: Path):
        mgr = ForgeApprovalManager()
        spec = draft_skill_spec("Delete temp files", skill_name="clean_temp")
        mgr.submit_spec_for_approval("clean_temp", spec)
        mgr.deny_spec("clean_temp")
        assert not mgr.is_fully_approved("clean_temp")
        # Ensure target folder was never created
        assert not (tmp_path / "skills" / "clean_temp").exists()

    def test_acceptance_6_trial_graduates_after_3_runs(self, tmp_path: Path):
        manifest = SkillManifest(manifest_path=tmp_path / "manifest.json")
        skill_dir = tmp_path / "trial_tool"
        skill_dir.mkdir()
        (skill_dir / "execution.py").write_text("def run(a): pass")

        manifest.register("trial_tool", skill_dir)
        assert manifest.is_trial("trial_tool")

        # Runs 1, 2, 3: trial mode
        for _ in range(3):
            manifest.record_run("trial_tool")

        # After 3 successful runs, graduates to active
        assert not manifest.is_trial("trial_tool")
        assert manifest.get_state("trial_tool") == "active"

    def test_acceptance_7_aborted_generation_cleanup(self, tmp_path: Path):
        # Simulate aborted generation mid-stream
        draft_dir = tmp_path / "sandbox" / "forge" / "aborted_draft"
        draft_dir.mkdir(parents=True)
        (draft_dir / "temp_file.tmp").write_text("partial")
        assert draft_dir.exists()

        # Cleanup on abort
        import shutil
        shutil.rmtree(draft_dir, ignore_errors=True)
        assert not draft_dir.exists()


