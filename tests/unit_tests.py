"""T.A.R.O. - Unit Test Suite for Core Modules

Tests core modules for:
- Module importability
- Class instantiation
- Method existence
- Configuration loading
- Safety system components
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


class UnitTestSuite:
    """Unit tests for core modules."""

    def __init__(self):
        self.results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "test_details": []
        }

    def log_test(self, category: str, name: str, passed: bool, message: str = ""):
        """Log a test result."""
        self.results["total_tests"] += 1
        test_result = {
            "category": category,
            "name": name,
            "passed": passed,
            "message": message
        }
        self.results["test_details"].append(test_result)

        if passed:
            self.results["passed"] += 1
            print(f"[PASS] {category:20} | {name:40}")
        else:
            self.results["failed"] += 1
            print(f"[FAIL] {category:20} | {name:40} | {message}")

    def test_core_modules(self):
        """Test core module imports."""
        print("\n=== Core Module Import Tests ===")

        modules = [
            "core.config",
            "core.orchestrator",
            "core.ws.server",
            "core.tools.registry",
            "core.safety.permissions",
            "core.safety.immutable",
            "core.safety.kill_switch",
            "core.model.ollama_client",
            "core.model.ollama_auto_starter",
            "core.summarizer",
            "core.prompt_builder",
        ]

        for module in modules:
            try:
                __import__(module)
                self.log_test("core_imports", module, True)
            except Exception as e:
                self.log_test("core_imports", module, False, str(e))

    def test_voice_modules(self):
        """Test voice module imports."""
        print("\n=== Voice Module Import Tests ===")

        modules = [
            "voice.stt",
            "voice.tts",
            "voice.wake_word",
            "voice.audio_worker",
            "voice.expressions",
        ]

        for module in modules:
            try:
                __import__(module)
                self.log_test("voice_imports", module, True)
            except Exception as e:
                self.log_test("voice_imports", module, False, str(e))

    def test_capability_modules(self):
        """Test capability module imports."""
        print("\n=== Capability Module Import Tests ===")

        modules = [
            "capabilities.files",
            "capabilities.system",
            "capabilities.web",
            "capabilities.office",
            "capabilities.vision",
            "capabilities.memory",
        ]

        for module in modules:
            try:
                __import__(module)
                self.log_test("capability_imports", module, True)
            except Exception as e:
                self.log_test("capability_imports", module, False, str(e))

    def test_config_loading(self):
        """Test configuration loading."""
        print("\n=== Configuration Tests ===")

        try:
            from core.config import cfg
            self.log_test("config", "Config loads", True)

            # Check voice config
            if hasattr(cfg, 'voice'):
                self.log_test("config", "Voice config exists", True)
            else:
                self.log_test("config", "Voice config exists", False)

            # Check model config
            if hasattr(cfg, 'model'):
                self.log_test("config", "Model config exists", True)
            else:
                self.log_test("config", "Model config exists", False)

            # Check orchestrator config
            if hasattr(cfg, 'orchestrator'):
                self.log_test("config", "Orchestrator config exists", True)
            else:
                self.log_test("config", "Orchestrator config exists", False)

        except Exception as e:
            self.log_test("config", "Config loads", False, str(e))

    def test_safety_system(self):
        """Test safety system components."""
        print("\n=== Safety System Tests ===")

        try:
            from core.safety.immutable import generate_core_manifest, verify_core_integrity
            self.log_test("safety", "Immutable functions exist", True)
        except Exception as e:
            self.log_test("safety", "Immutable functions exist", False, str(e))

        try:
            from core.safety.permissions import PermissionManager
            self.log_test("safety", "PermissionManager exists", True)
        except Exception as e:
            self.log_test("safety", "PermissionManager exists", False, str(e))

        try:
            from core.safety.kill_switch import KillSwitch
            self.log_test("safety", "KillSwitch exists", True)
        except Exception as e:
            self.log_test("safety", "KillSwitch exists", False, str(e))

    def test_tool_registry(self):
        """Test tool registry."""
        print("\n=== Tool Registry Tests ===")

        try:
            from core.tools.registry import ToolRegistry
            self.log_test("registry", "ToolRegistry exists", True)
        except Exception as e:
            self.log_test("registry", "ToolRegistry exists", False, str(e))

        try:
            from capabilities import ALL_CAPABILITY_TOOLS
            tool_count = len(ALL_CAPABILITY_TOOLS)
            self.log_test("registry", f"Tools loaded ({tool_count})", tool_count > 0)
        except Exception as e:
            self.log_test("registry", "Tools loaded", False, str(e))

    def test_memory_system(self):
        """Test memory system."""
        print("\n=== Memory System Tests ===")

        try:
            from core.memory.sqlite_store import SQLiteMemoryStore
            self.log_test("memory", "SQLiteMemoryStore exists", True)
        except Exception as e:
            self.log_test("memory", "SQLiteMemoryStore exists", False, str(e))

        try:
            from core.memory.json_store import JSONProceduralStore
            self.log_test("memory", "JSONProceduralStore exists", True)
        except Exception as e:
            self.log_test("memory", "JSONProceduralStore exists", False, str(e))

    def test_model_client(self):
        """Test model client."""
        print("\n=== Model Client Tests ===")

        try:
            from core.model.ollama_client import OllamaClient
            self.log_test("model", "OllamaClient exists", True)
        except Exception as e:
            self.log_test("model", "OllamaClient exists", False, str(e))

        try:
            from core.model.model_manager import ModelManager
            self.log_test("model", "ModelManager exists", True)
        except Exception as e:
            self.log_test("model", "ModelManager exists", False, str(e))

    def run_all_tests(self):
        """Run all unit tests."""
        print("=" * 80)
        print("T.A.R.O. - Unit Test Suite")
        print("=" * 80)

        self.test_core_modules()
        self.test_voice_modules()
        self.test_capability_modules()
        self.test_config_loading()
        self.test_safety_system()
        self.test_tool_registry()
        self.test_memory_system()
        self.test_model_client()

        return self.results

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("Unit Test Summary")
        print("=" * 80)
        print(f"Total Tests: {self.results['total_tests']}")
        print(f"Passed:      {self.results['passed']}")
        print(f"Failed:      {self.results['failed']}")
        print(f"Success:     {(self.results['passed']/self.results['total_tests']*100):.1f}%")
        print("=" * 80)

        if self.results["failed"] > 0:
            print("\nFailed Tests:")
            for test in self.results["test_details"]:
                if not test["passed"]:
                    print(f"  - {test['category']}/{test['name']}: {test['message']}")


def main():
    """Main entry point."""
    suite = UnitTestSuite()
    results = suite.run_all_tests()
    suite.print_summary()

    if results["failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
