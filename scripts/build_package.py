"""T.A.R.O. - Packaging & Build Automation Script (TASK-093).

Usage:
    python scripts/build_package.py [--dry-run]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build T.A.R.O. executable with PyInstaller.")
    parser.add_argument("--dry-run", action="store_true", help="Validate spec file without compiling.")
    args = parser.parse_args()

    spec_file = Path("taro.spec")
    if not spec_file.exists():
        print("Error: taro.spec not found in current directory.")
        return 1

    print("=== T.A.R.O. Executable Packaging ===")
    if args.dry_run:
        print("Dry run: Validating spec file syntax...")
        with open(spec_file, "r", encoding="utf-8") as f:
            compile(f.read(), "taro.spec", "exec")
        print("Validation successful: taro.spec is syntactically correct and ready for build.")
        return 0

    print("Running PyInstaller...")
    res = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "taro.spec"])
    if res.returncode == 0:
        print("Build completed: dist/taro/taro.exe")
    return res.returncode


if __name__ == "__main__":
    raise SystemExit(main())
