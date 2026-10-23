"""T.A.R.O. - System hardware stats and telemetry.

ARCHITECTURE reference: section 14.
RULES reference: section 3, 10.
TASKS: TASK-050.

Collects real-time hardware metrics for HUD telemetry (CPU, RAM, GPU,
VRAM, disk, network, temperature), reporting 'n/a' for unavailable sensors.
"""

from __future__ import annotations

import shutil
from typing import Any

from core.log.setup import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory, ToolResult

logger = get_logger(__name__)


def get_system_telemetry() -> dict[str, Any]:
    """Collects system stats dictionary. Missing sensors report 'n/a'."""
    import psutil

    # 1. CPU
    cpu_percent = psutil.cpu_percent(interval=None)

    # 2. RAM
    ram = psutil.virtual_memory()
    ram_total_gb = round(ram.total / (1024**3), 2)
    ram_used_gb = round(ram.used / (1024**3), 2)
    ram_percent = ram.percent

    # 3. Disk
    disk = psutil.disk_usage("/")
    disk_total_gb = round(disk.total / (1024**3), 1)
    disk_used_gb = round(disk.used / (1024**3), 1)
    disk_percent = disk.percent

    # 4. Network
    net = psutil.net_io_counters()
    net_sent_mb = round(net.bytes_sent / (1024**2), 1)
    net_recv_mb = round(net.bytes_recv / (1024**2), 1)

    # 5. Temperature
    temp_val: str | float = "n/a"
    try:
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                first_key = next(iter(temps))
                if temps[first_key]:
                    temp_val = round(temps[first_key][0].current, 1)
    except Exception:
        temp_val = "n/a"

    # 6. GPU & VRAM via nvidia-smi
    gpu_name: str = "n/a"
    vram_used_gb: str | float = "n/a"
    vram_total_gb: str | float = "n/a"

    try:
        import subprocess

        smi = shutil.which("nvidia-smi")
        if smi:
            res = subprocess.run(
                [
                    smi,
                    "--query-gpu=name,memory.total,memory.used",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 3:
                    gpu_name = parts[0]
                    vram_total_gb = round(float(parts[1]) / 1024, 2)
                    vram_used_gb = round(float(parts[2]) / 1024, 2)
    except Exception:
        pass

    return {
        "cpu_percent": cpu_percent,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "ram_percent": ram_percent,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "disk_percent": disk_percent,
        "net_sent_mb": net_sent_mb,
        "net_recv_mb": net_recv_mb,
        "temperature": temp_val,
        "gpu_name": gpu_name,
        "vram_used_gb": vram_used_gb,
        "vram_total_gb": vram_total_gb,
    }


class SystemStatsTool(BaseTool):
    """Retrieves current hardware statistics."""

    name = "system.stats"
    description = "Get real-time CPU, RAM, GPU, VRAM, disk, network, and temperature metrics."
    category = ToolCategory.HARDWARE
    risk = RiskLevel.SAFE
    timeout_s = 5
    parameters = {"type": "object", "properties": {}}

    async def run(self, args: dict) -> ToolResult:
        return await self.execute(**args)

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            stats = get_system_telemetry()
            lines = [
                f"CPU: {stats['cpu_percent']}%",
                f"RAM: {stats['ram_used_gb']} / {stats['ram_total_gb']} GB ({stats['ram_percent']}%)",
                f"Disk: {stats['disk_used_gb']} / {stats['disk_total_gb']} GB ({stats['disk_percent']}%)",
                f"GPU: {stats['gpu_name']}",
                f"VRAM: {stats['vram_used_gb']} / {stats['vram_total_gb']} GB",
                f"Network: {stats['net_sent_mb']} MB Sent, {stats['net_recv_mb']} MB Recv",
                f"Temperature: {stats['temperature']}",
            ]
            return ToolResult(status="ok", output="\n".join(lines))
        except Exception as e:
            logger.error("system_stats_failed", error=str(e))
            return ToolResult(status="error", output="", error=f"Failed to fetch system stats: {e}")


STATS_TOOLS: list[BaseTool] = [
    SystemStatsTool(),
]
