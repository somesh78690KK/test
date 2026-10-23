"""Execution logic for system_info skill."""

import platform
import shutil
from typing import Any


def run(args: dict[str, Any]) -> dict[str, Any]:
    detailed = args.get("detailed", False)

    sys_platform = platform.platform()
    cpu_info = platform.processor() or "x86_64"

    # Disk usage
    total, used, free = shutil.disk_usage("/")
    total_gb = round(total / (1024**3), 1)
    used_gb = round(used / (1024**3), 1)
    free_gb = round(free / (1024**3), 1)

    output = (
        f"OS: {sys_platform}\n"
        f"Processor: {cpu_info}\n"
        f"Primary Storage: {used_gb} GB used of {total_gb} GB ({free_gb} GB free)"
    )

    return {
        "status": "ok",
        "output": output,
        "platform": sys_platform,
        "disk_free_gb": free_gb,
    }
