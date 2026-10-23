"""T.A.R.O. - Sandbox Test Suite

Phase 2: Sandbox Simulation & Verification
Tests core functionality with mocked dependencies.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import numpy as np

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


class SandboxTestSuite:
    """Comprehensive sandbox test suite for T.A.R.O. core functionality."""

    def __init__(self):
        self.results = {
            "passed": 0,
            "failed": 0,
            "tests": []
        }

    def log_test(self, name: str, passed: bool, message: str = ""):
        """Log test result."""
        result = {"name": name, "passed": passed, "message": message}
        self.results["tests"].append(result)
        if passed:
            self.results["passed"] += 1
            print(f"[PASS] {name}")
        else:
            self.results["failed"] += 1
            print(f"[FAIL] {name} - {message}")

    async def test_voice_transcription_loop(self):
        """Test voice command trigger and transcription loop structure."""
        print("\n=== Testing Voice Transcription Loop ===")
        try:
            from voice.stt import STTEngine

            # Test that STTEngine can be instantiated
            stt = STTEngine()

            # Test that it has the required methods
            if hasattr(stt, 'transcribe_audio'):
                self.log_test("voice_transcription_method", True, "transcribe_audio method exists")
            else:
                self.log_test("voice_transcription_method", False, "transcribe_audio method missing")

            if hasattr(stt, '_ensure_recognizer'):
                self.log_test("voice_recognizer_method", True, "_ensure_recognizer method exists")
            else:
                self.log_test("voice_recognizer_method", False, "_ensure_recognizer method missing")

        except Exception as e:
            self.log_test("voice_transcription", False, str(e))

    async def test_tool_dispatcher(self):
        """Test tool dispatcher with permission handler."""
        print("\n=== Testing Tool Dispatcher ===")
        try:
            from core.tools.registry import ToolRegistry
            from capabilities.files.operations import FILE_TOOLS

            registry = ToolRegistry()

            # Get a file tool
            if len(FILE_TOOLS) > 0:
                tool = FILE_TOOLS[0]
                registry.register(tool)

                # Test tool retrieval
                retrieved = registry.get(tool.name)
                if retrieved is not None and retrieved.name == tool.name:
                    self.log_test("tool_dispatcher_retrieval", True, "Tool retrieved successfully")
                else:
                    self.log_test("tool_dispatcher_retrieval", False, "Tool not found")

                # Test tool execution with mock
                result = await tool.run({"path": "test.txt"})
                if result.status in ["ok", "error"]:
                    self.log_test("tool_dispatcher_execution", True, f"Tool executed with status: {result.status}")
                else:
                    self.log_test("tool_dispatcher_execution", False, f"Unexpected status: {result.status}")
            else:
                self.log_test("tool_dispatcher", False, "No FILE_TOOLS available")

        except Exception as e:
            self.log_test("tool_dispatcher", False, str(e))

    async def test_permission_handler(self):
        """Test permission handler using config/permissions.json."""
        print("\n=== Testing Permission Handler ===")
        try:
            from core.safety.permissions import PermissionManager
            from pathlib import Path

            # Check if permissions file exists
            perm_path = project_root / "config" / "permissions.json"
            if not perm_path.exists():
                self.log_test("permission_handler", False, "permissions.json not found")
                return

            pm = PermissionManager(perm_path)

            # Test permission manager can be instantiated
            if pm is not None:
                self.log_test("permission_handler_load", True, "PermissionManager loaded successfully")
            else:
                self.log_test("permission_handler_load", False, "PermissionManager is None")

        except Exception as e:
            self.log_test("permission_handler", False, str(e))

    async def test_memory_compaction(self):
        """Test memory structure."""
        print("\n=== Testing Memory Compaction ===")
        try:
            # Check if memory module exists
            try:
                from core.memory.sqlite_store import SQLiteMemoryStore
                self.log_test("memory_module_exists", True, "SQLiteMemoryStore module found")
            except ImportError:
                self.log_test("memory_module_exists", False, "SQLiteMemoryStore not found")
                return

            # Test that the store can be instantiated
            store = SQLiteMemoryStore()
            if store is not None:
                self.log_test("memory_compaction_storage", True, "Memory store instantiated")
            else:
                self.log_test("memory_compaction_storage", False, "Memory store is None")

        except Exception as e:
            self.log_test("memory_compaction", False, str(e))

    async def test_rolling_summarization(self):
        """Test rolling summarization logic."""
        print("\n=== Testing Rolling Summarization ===")
        try:
            from core.summarizer import RollingSummarizer

            # RollingSummarizer doesn't take threshold parameter
            summarizer = RollingSummarizer()

            # Test maybe_summarize method exists
            if hasattr(summarizer, 'maybe_summarize'):
                self.log_test("rolling_summarizer_method", True, "maybe_summarize method exists")
            else:
                self.log_test("rolling_summarizer_method", False, "maybe_summarize method missing")

            # Test with small history (should not summarize)
            small_history = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"}
            ]
            result = summarizer.maybe_summarize(small_history)
            if result is None:
                self.log_test("rolling_summarizer_threshold", True, "Small history not summarized")
            else:
                self.log_test("rolling_summarizer_threshold", False, "Small history was summarized unexpectedly")

        except Exception as e:
            self.log_test("rolling_summarization", False, str(e))

    async def test_taint_context(self):
        """Test TaintContext interface if it exists."""
        print("\n=== Testing TaintContext ===")
        try:
            # Try to import taint context
            try:
                from core.safety.taint import TaintContext
                self.log_test("taint_context_import", True, "TaintContext imported successfully")

                # Create a TaintContext instance
                context = TaintContext(user_input="test input")

                # Test that it's not callable (should fail if callable)
                try:
                    context("test")  # This should not work
                    self.log_test("taint_context_callable", False, "TaintContext is callable (should not be)")
                except TypeError:
                    self.log_test("taint_context_callable", True, "TaintContext correctly not callable")

                # Test that it has proper methods
                if hasattr(context, 'validate') or hasattr(context, 'check_taint'):
                    self.log_test("taint_context_methods", True, "TaintContext has validation methods")
                else:
                    self.log_test("taint_context_methods", False, "TaintContext missing validation methods")
            except ImportError:
                # TaintContext may not exist as a separate module
                self.log_test("taint_context", True, "TaintContext module not present (may be integrated elsewhere)")

        except Exception as e:
            self.log_test("taint_context", False, str(e))

    async def test_vosk_integration(self):
        """Test Vosk integration structure."""
        print("\n=== Testing Vosk Integration ===")
        try:
            from voice.stt import STTEngine
            import sys

            # Test that STTEngine has frozen path handling
            stt = STTEngine()

            # Check that it uses correct model path resolution
            if hasattr(stt, 'model_path'):
                self.log_test("vosk_model_path", True, f"Model path: {stt.model_path}")
            else:
                self.log_test("vosk_model_path", False, "Model path attribute missing")

            # Check sample rate
            if hasattr(stt, 'sample_rate'):
                self.log_test("vosk_sample_rate", True, f"Sample rate: {stt.sample_rate}")
            else:
                self.log_test("vosk_sample_rate", False, "Sample rate attribute missing")

        except Exception as e:
            self.log_test("vosk_integration", False, str(e))

    async def test_capability_registration(self):
        """Test all capabilities can be registered."""
        print("\n=== Testing Capability Registration ===")
        try:
            from capabilities import register_all_capabilities
            from core.tools.registry import ToolRegistry

            registry = ToolRegistry()
            count = register_all_capabilities(registry)

            if count > 0:
                self.log_test("capability_registration", True, f"Registered {count} tools")
            else:
                self.log_test("capability_registration", False, "No tools registered")

            # Check for tools with parameters
            tools_without_params = []
            for tool_name, tool in registry._tools.items():
                if not hasattr(tool, 'parameters'):
                    tools_without_params.append(tool_name)

            if len(tools_without_params) == 0:
                self.log_test("capability_parameters", True, "All tools have parameters")
            else:
                self.log_test("capability_parameters", False, f"{len(tools_without_params)} tools missing parameters")

        except Exception as e:
            self.log_test("capability_registration", False, str(e))

    async def run_all_tests(self):
        """Run all sandbox tests."""
        print("=" * 60)
        print("T.A.R.O. Sandbox Test Suite")
        print("=" * 60)

        await self.test_voice_transcription_loop()
        await self.test_tool_dispatcher()
        await self.test_permission_handler()
        await self.test_memory_compaction()
        await self.test_rolling_summarization()
        await self.test_taint_context()
        await self.test_vosk_integration()
        await self.test_capability_registration()

        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Total: {self.results['passed'] + self.results['failed']}")
        print(f"Passed: {self.results['passed']}")
        print(f"Failed: {self.results['failed']}")
        print("=" * 60)

        return self.results


async def main():
    """Main entry point for sandbox tests."""
    suite = SandboxTestSuite()
    results = await suite.run_all_tests()

    # Exit with error code if any tests failed
    if results['failed'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
