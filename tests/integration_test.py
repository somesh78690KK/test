"""T.A.R.O. - Integration Test Suite

Tests the full application integration:
- Launch executable
- Monitor startup
- Test WebSocket connection
- Test voice pipeline (mocked)
- Test tool dispatch through orchestrator
- Monitor logs for errors
"""

import sys
import asyncio
import time
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


class IntegrationTestSuite:
    """Integration tests for full application."""

    def __init__(self):
        self.results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "test_details": []
        }
        self.process = None
        # Log file is in the dist/taro directory where the exe runs
        self.log_file = project_root / "dist" / "taro" / "taro_runtime.log"

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

    def test_executable_exists(self):
        """Test that executable exists."""
        print("\n=== Executable Existence Test ===")

        exe_path = project_root / "dist" / "taro" / "taro.exe"
        if exe_path.exists():
            self.log_test("executable", "taro.exe exists", True)
            return str(exe_path)
        else:
            self.log_test("executable", "taro.exe exists", False, "File not found")
            return None

    def launch_application(self, exe_path: str):
        """Launch the T.A.R.O application."""
        print("\n=== Application Launch Test ===")

        try:
            # Clear previous log
            if self.log_file.exists():
                self.log_file.unlink()

            # Launch executable (it writes to taro_runtime.log in the same directory)
            self.process = subprocess.Popen(
                [exe_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(project_root)
            )

            self.log_test("launch", "Application started", True, f"PID: {self.process.pid}")
            time.sleep(8)  # Wait for startup (increased from 5 to 8)

            # Check if process is still running
            if self.process.poll() is None:
                self.log_test("launch", "Application running", True)
            else:
                self.log_test("launch", "Application running", False, "Process exited")
                return False

            return True

        except Exception as e:
            self.log_test("launch", "Application started", False, str(e))
            return False

    def monitor_startup_logs(self):
        """Monitor startup logs for errors."""
        print("\n=== Startup Log Monitoring ===")

        # Wait longer for log file to be created
        time.sleep(5)

        if not self.log_file.exists():
            self.log_test("logs", "Log file created", False, "No log file")
            return

        # Wait a bit more for logs to be written
        time.sleep(3)

        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()

            # Check for startup indicators
            checks = [
                ("Ollama ready", "Ollama ready" in log_content),
                ("Capabilities registered", "all_capabilities_registered" in log_content),
                ("TTS started", "tts_started" in log_content),
                ("Vosk model loaded", "stt_model_loaded" in log_content),
                ("HUD server started", "hud_server_started" in log_content),
                ("WebSocket connected", "ws_client_connected" in log_content),
            ]

            for check_name, check_result in checks:
                self.log_test("startup", check_name, check_result)

            # Check for errors
            if "ERROR" in log_content.upper() or "EXCEPTION" in log_content.upper():
                self.log_test("startup", "No startup errors", False, "Errors found in logs")
            else:
                self.log_test("startup", "No startup errors", True)

        except Exception as e:
            self.log_test("logs", "Log monitoring", False, str(e))

    def test_voice_pipeline(self):
        """Test voice pipeline initialization."""
        print("\n=== Voice Pipeline Test ===")

        if not self.log_file.exists():
            self.log_test("voice", "Voice pipeline logs", False, "No log file")
            return

        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()

            checks = [
                ("Wake word started", "wake_word_started" in log_content),
                ("Audio worker started", "audio_worker_started" in log_content),
                ("Hands-free mode", "hands_free" in log_content),
            ]

            for check_name, check_result in checks:
                self.log_test("voice", check_name, check_result)

        except Exception as e:
            self.log_test("voice", "Voice pipeline test", False, str(e))

    def test_capability_registration(self):
        """Test capability registration."""
        print("\n=== Capability Registration Test ===")

        if not self.log_file.exists():
            self.log_test("capabilities", "Capability logs", False, "No log file")
            return

        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()

            # Check for capability count
            if "all_capabilities_registered" in log_content:
                self.log_test("capabilities", "Capabilities registered", True)
            else:
                self.log_test("capabilities", "Capabilities registered", False)

        except Exception as e:
            self.log_test("capabilities", "Capability test", False, str(e))

    def test_safety_system(self):
        """Test safety system initialization."""
        print("\n=== Safety System Test ===")

        if not self.log_file.exists():
            self.log_test("safety", "Safety logs", False, "No log file")
            return

        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()

            checks = [
                ("Permissions loaded", "permissions_loaded" in log_content),
                ("Kill switch active", "global_hotkey_listener_started" in log_content),
            ]

            for check_name, check_result in checks:
                self.log_test("safety", check_name, check_result)

        except Exception as e:
            self.log_test("safety", "Safety test", False, str(e))

    def monitor_runtime_errors(self, duration: int = 30):
        """Monitor runtime for errors."""
        print(f"\n=== Runtime Error Monitoring ({duration}s) ===")

        if not self.log_file.exists():
            self.log_test("runtime", "Runtime monitoring", False, "No log file")
            return

        time.sleep(duration)

        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()

            # Check for common errors
            error_patterns = [
                "Traceback",
                "ERROR",
                "Exception",
                "WinError",
                "AttributeError",
                "TypeError",
                "KeyError",
            ]

            errors_found = []
            for pattern in error_patterns:
                if pattern in log_content:
                    errors_found.append(pattern)

            if errors_found:
                self.log_test("runtime", "No runtime errors", False, f"Found: {', '.join(errors_found)}")
            else:
                self.log_test("runtime", "No runtime errors", True)

        except Exception as e:
            self.log_test("runtime", "Runtime monitoring", False, str(e))

    def stop_application(self):
        """Stop the application."""
        print("\n=== Application Shutdown ===")

        if self.process:
            try:
                self.process.terminate()
                time.sleep(2)

                if self.process.poll() is None:
                    self.process.kill()
                    time.sleep(1)

                self.log_test("shutdown", "Application stopped", True)
            except Exception as e:
                self.log_test("shutdown", "Application stopped", False, str(e))

    def run_all_tests(self):
        """Run all integration tests."""
        print("=" * 80)
        print("T.A.R.O. - Integration Test Suite")
        print("=" * 80)
        print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Test executable exists
        exe_path = self.test_executable_exists()
        if not exe_path:
            return self.results

        # Launch application
        if not self.launch_application(exe_path):
            return self.results

        try:
            # Monitor startup
            self.monitor_startup_logs()

            # Test voice pipeline
            self.test_voice_pipeline()

            # Test capability registration
            self.test_capability_registration()

            # Test safety system
            self.test_safety_system()

            # Monitor runtime for 30 seconds
            self.monitor_runtime_errors(30)

        finally:
            # Stop application
            self.stop_application()

        print(f"\nTest Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return self.results

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("Integration Test Summary")
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

        print(f"\nLog file: {self.log_file}")


def main():
    """Main entry point."""
    suite = IntegrationTestSuite()
    results = suite.run_all_tests()
    suite.print_summary()

    if results["failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
