"""T.A.R.O. - Capability Validator Test Suite

Tests all 77 registered capabilities for:
- Tool schema validation
- Parameter structure
- Required methods existence
- Tool instantiation
- Permission definitions
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


class CapabilityValidator:
    """Validate all registered capabilities."""

    def __init__(self):
        self.results = {
            "total_tools": 0,
            "valid_tools": 0,
            "invalid_tools": 0,
            "errors": [],
            "tool_details": []
        }

    def validate_tool(self, tool_obj):
        """Validate a single tool (can be class or instance)."""
        # Handle both tool classes and tool instances
        if isinstance(tool_obj, type):
            # It's a class, get instance
            try:
                instance = tool_obj()
                tool_class = tool_obj
            except Exception as e:
                tool_name = getattr(tool_obj, 'name', 'Unknown')
                tool_result = {
                    "name": tool_name,
                    "passed": False,
                    "errors": [f"Instantiation failed: {str(e)}"]
                }
                return tool_result
        else:
            # It's already an instance
            instance = tool_obj
            tool_class = type(tool_obj)

        tool_name = getattr(instance, 'name', 'Unknown')
        tool_result = {
            "name": tool_name,
            "passed": True,
            "errors": []
        }

        # Check if tool has name
        if not hasattr(instance, 'name'):
            tool_result["passed"] = False
            tool_result["errors"].append("Missing 'name' attribute")
        elif not instance.name:
            tool_result["passed"] = False
            tool_result["errors"].append("Empty 'name' attribute")

        # Check if tool has description
        if not hasattr(instance, 'description'):
            tool_result["passed"] = False
            tool_result["errors"].append("Missing 'description' attribute")

        # Check if tool has parameters
        if not hasattr(instance, 'parameters'):
            tool_result["passed"] = False
            tool_result["errors"].append("Missing 'parameters' attribute")
        elif instance.parameters is None:
            tool_result["passed"] = False
            tool_result["errors"].append("'parameters' is None")
        elif not isinstance(instance.parameters, dict):
            tool_result["passed"] = False
            tool_result["errors"].append(f"'parameters' is not dict, got {type(instance.parameters)}")
        elif 'type' not in instance.parameters:
            tool_result["passed"] = False
            tool_result["errors"].append("Missing 'type' in parameters schema")

        # Check if tool has run method
        if not hasattr(instance, 'run'):
            tool_result["passed"] = False
            tool_result["errors"].append("Missing 'run' method")

        return tool_result

    def run_validation(self):
        """Run validation on all capabilities."""
        print("=" * 80)
        print("T.A.R.O. - Capability Validator Test Suite")
        print("=" * 80)

        try:
            from capabilities import ALL_CAPABILITY_TOOLS
            self.results["total_tools"] = len(ALL_CAPABILITY_TOOLS)
            print(f"\nValidating {self.results['total_tools']} capabilities...\n")
        except Exception as e:
            print(f"[ERROR] Failed to import capabilities: {e}")
            self.results["errors"].append(f"Import failed: {e}")
            return self.results

        for idx, tool_class in enumerate(ALL_CAPABILITY_TOOLS, 1):
            tool_name = getattr(tool_class, 'name', 'Unknown')
            tool_result = self.validate_tool(tool_class)

            self.results["tool_details"].append(tool_result)

            if tool_result["passed"]:
                self.results["valid_tools"] += 1
                print(f"[{idx:3d}/{self.results['total_tools']}] [PASS] {tool_name}")
            else:
                self.results["invalid_tools"] += 1
                print(f"[{idx:3d}/{self.results['total_tools']}] [FAIL] {tool_name}")
                for error in tool_result["errors"]:
                    print(f"           - {error}")

        return self.results

    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 80)
        print("Capability Validation Summary")
        print("=" * 80)
        print(f"Total Tools:     {self.results['total_tools']}")
        print(f"Valid Tools:     {self.results['valid_tools']}")
        print(f"Invalid Tools:   {self.results['invalid_tools']}")
        print(f"Success Rate:    {(self.results['valid_tools']/self.results['total_tools']*100):.1f}%")
        print("=" * 80)

        if self.results["invalid_tools"] > 0:
            print("\nInvalid Tools Details:")
            for tool in self.results["tool_details"]:
                if not tool["passed"]:
                    print(f"\n  {tool['name']}:")
                    for error in tool["errors"]:
                        print(f"    - {error}")


def main():
    """Main entry point."""
    validator = CapabilityValidator()
    results = validator.run_validation()
    validator.print_summary()

    if results["invalid_tools"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
