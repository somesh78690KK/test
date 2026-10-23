"""T.A.R.O. - Master Test Runner

Runs all test suites and generates a comprehensive test report.
- Capability Validator (77 tools)
- Unit Tests (core modules)
- Command Simulation (safe commands)
- Integration Tests (full application)
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


class MasterTestRunner:
    """Master test runner for all test suites."""

    def __init__(self):
        self.results = {
            "test_suites": {},
            "total_tests": 0,
            "total_passed": 0,
            "total_failed": 0,
            "start_time": None,
            "end_time": None
        }

    def run_test_suite(self, name: str, script_path: str) -> dict:
        """Run a single test suite."""
        print(f"\n{'=' * 80}")
        print(f"Running Test Suite: {name}")
        print(f"{'=' * 80}")

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per suite
            )

            output = result.stdout + result.stderr
            success = result.returncode == 0

            print(output)

            return {
                "name": name,
                "success": success,
                "returncode": result.returncode,
                "output": output
            }

        except subprocess.TimeoutExpired:
            print(f"[TIMEOUT] Test suite {name} timed out after 5 minutes")
            return {
                "name": name,
                "success": False,
                "returncode": -1,
                "output": "TIMEOUT"
            }
        except Exception as e:
            print(f"[ERROR] Failed to run test suite {name}: {e}")
            return {
                "name": name,
                "success": False,
                "returncode": -1,
                "output": str(e)
            }

    def run_all_suites(self):
        """Run all test suites."""
        self.results["start_time"] = datetime.now()

        print("=" * 80)
        print("T.A.R.O. - Master Test Runner")
        print("=" * 80)
        print(f"Started: {self.results['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Define test suites
        test_suites = [
            ("Capability Validator", project_root / "tests" / "capability_validator.py"),
            ("Unit Tests", project_root / "tests" / "unit_tests.py"),
            ("Command Simulation", project_root / "tests" / "command_simulation.py"),
            ("Integration Tests", project_root / "tests" / "integration_test.py"),
        ]

        # Run each suite
        for name, script_path in test_suites:
            if not script_path.exists():
                print(f"[SKIP] {name} - Script not found: {script_path}")
                self.results["test_suites"][name] = {
                    "name": name,
                    "success": False,
                    "returncode": -1,
                    "output": "Script not found"
                }
                continue

            result = self.run_test_suite(name, script_path)
            self.results["test_suites"][name] = result

            if result["success"]:
                self.results["total_passed"] += 1
            else:
                self.results["total_failed"] += 1

            self.results["total_tests"] += 1

        self.results["end_time"] = datetime.now()

    def generate_report(self):
        """Generate comprehensive test report."""
        report_path = project_root / "TEST_REPORT.md"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# T.A.R.O. - Comprehensive Test Report\n\n")
            f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Duration**: {(self.results['end_time'] - self.results['start_time']).total_seconds():.1f} seconds\n\n")

            f.write("## Executive Summary\n\n")
            f.write(f"- **Total Test Suites**: {self.results['total_tests']}\n")
            f.write(f"- **Passed**: {self.results['total_passed']}\n")
            f.write(f"- **Failed**: {self.results['total_failed']}\n")
            f.write(f"- **Success Rate**: {(self.results['total_passed']/self.results['total_tests']*100):.1f}%\n\n")

            f.write("## Test Suite Results\n\n")

            for suite_name, result in self.results["test_suites"].items():
                status = "✅ PASSED" if result["success"] else "❌ FAILED"
                f.write(f"### {suite_name}: {status}\n\n")

                if result["output"]:
                    f.write("```\n")
                    f.write(result["output"][-2000:] if len(result["output"]) > 2000 else result["output"])
                    f.write("\n```\n\n")

            f.write("## Detailed Analysis\n\n")

            # Add analysis for each suite
            if "Capability Validator" in self.results["test_suites"]:
                f.write("### Capability Validator Analysis\n\n")
                f.write("Validates all 77 registered capabilities for:\n")
                f.write("- Tool schema validation\n")
                f.write("- Parameter structure\n")
                f.write("- Required methods existence\n")
                f.write("- Tool instantiation\n\n")

            if "Unit Tests" in self.results["test_suites"]:
                f.write("### Unit Tests Analysis\n\n")
                f.write("Tests core modules for:\n")
                f.write("- Module importability\n")
                f.write("- Class instantiation\n")
                f.write("- Configuration loading\n")
                f.write("- Safety system components\n\n")

            if "Command Simulation" in self.results["test_suites"]:
                f.write("### Command Simulation Analysis\n\n")
                f.write("Tests command processing:\n")
                f.write("- Tool dispatch\n")
                f.write("- Permission system\n")
                f.write("- Memory operations\n")
                f.write("- Config parsing\n\n")

            if "Integration Tests" in self.results["test_suites"]:
                f.write("### Integration Tests Analysis\n\n")
                f.write("Tests full application:\n")
                f.write("- Executable launch\n")
                f.write("- Startup sequence\n")
                f.write("- Voice pipeline\n")
                f.write("- Capability registration\n")
                f.write("- Runtime error monitoring\n\n")

            f.write("## Recommendations\n\n")

            if self.results["total_failed"] > 0:
                f.write("### Issues Found\n\n")
                for suite_name, result in self.results["test_suites"].items():
                    if not result["success"]:
                        f.write(f"- **{suite_name}**: Failed - See output above for details\n\n")
                f.write("### Action Items\n\n")
                f.write("1. Review failed test outputs above\n")
                f.write("2. Fix identified issues\n")
                f.write("3. Re-run test suite to verify fixes\n\n")
            else:
                f.write("### All Tests Passed ✅\n\n")
                f.write("All test suites completed successfully. The application is ready for deployment.\n\n")

            f.write("---\n")
            f.write(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        print(f"\n{'=' * 80}")
        print(f"Test report generated: {report_path}")
        print(f"{'=' * 80}")

    def print_summary(self):
        """Print summary of all test suites."""
        print("\n" + "=" * 80)
        print("Master Test Runner Summary")
        print("=" * 80)
        print(f"Test Suites Run: {self.results['total_tests']}")
        print(f"Passed:          {self.results['total_passed']}")
        print(f"Failed:          {self.results['total_failed']}")
        print(f"Success Rate:    {(self.results['total_passed']/self.results['total_tests']*100):.1f}%")
        print(f"Duration:        {(self.results['end_time'] - self.results['start_time']).total_seconds():.1f} seconds")
        print("=" * 80)

        print("\nTest Suite Results:")
        for suite_name, result in self.results["test_suites"].items():
            status = "[PASS]" if result["success"] else "[FAIL]"
            print(f"  {status} {suite_name}")


def main():
    """Main entry point."""
    runner = MasterTestRunner()
    runner.run_all_suites()
    runner.print_summary()
    runner.generate_report()

    if runner.results["total_failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
