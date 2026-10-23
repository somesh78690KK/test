"""T.A.R.O. - Model Manager.

Ensures only one large model is in VRAM at a time. Monitors VRAM via
nvidia-smi every second. Adjusts num_gpu when free VRAM falls below
the low watermark.

ARCHITECTURE reference: section 6.3.
TASKS: TASK-013.

Key rules:
- Before loading a large model, check that the previous one will unload.
- Vision model is unloaded after ``vision_unload_after_s`` seconds of
  disuse (default 30 s).
- OLLAMA_MAX_LOADED_MODELS=1 must be set in the environment (checked by
  taro.doctor, enforced by Ollama itself).
- Model switching triggered by the user asking "use the backup model"
  switches to nemotron-3-nano:4b.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from dataclasses import dataclass

from core.log import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# VRAM data
# ---------------------------------------------------------------------------


@dataclass
class VRAMStats:
    """GPU VRAM statistics from nvidia-smi."""

    total_mb: int
    used_mb: int
    free_mb: int

    @property
    def total_gb(self) -> float:
        return self.total_mb / 1024.0

    @property
    def free_gb(self) -> float:
        return self.free_mb / 1024.0

    @property
    def used_gb(self) -> float:
        return self.used_mb / 1024.0


# ---------------------------------------------------------------------------
# Model manager
# ---------------------------------------------------------------------------


class ModelManager:
    """Manages which large model is loaded in VRAM.

    Args:
        chat_model: Primary chat model tag.
        backup_model: Backup chat model tag (e.g. nemotron-3-nano:4b).
        vision_model: Vision model tag (loaded on demand).
        vram_low_watermark_gb: Reduce num_gpu when free VRAM drops below this.
        vram_ceiling_gb: Alert threshold.
        vision_unload_after_s: Seconds after last vision use before unloading.
    """

    def __init__(
        self,
        chat_model: str = "",
        backup_model: str = "",
        vision_model: str = "",
        vram_low_watermark_gb: float = 1.0,
        vram_ceiling_gb: float = 5.5,
        vision_unload_after_s: int = 30,
    ) -> None:
        from core.config import cfg

        self.chat_model = chat_model or cfg.model.chat_model
        self.backup_model = backup_model or cfg.model.backup_model
        self.vision_model = vision_model or cfg.model.vision_model
        self.vram_low_watermark_gb = vram_low_watermark_gb
        self.vram_ceiling_gb = vram_ceiling_gb
        self.vision_unload_after_s = vision_unload_after_s

        # State
        self._active_model: str | None = None
        self._use_backup: bool = False
        self._vision_last_used: float = 0.0
        self._num_gpu: int | str = "auto"
        self._lock = asyncio.Lock()
        self._vram_poll_task: asyncio.Task[None] | None = None
        self._last_vram: VRAMStats | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_chat_model(self) -> str:
        """The model tag that should be used for the next chat request."""
        return self.backup_model if self._use_backup else self.chat_model

    @property
    def num_gpu(self) -> int | str:
        """Current num_gpu setting (may be reduced by VRAM monitor)."""
        return self._num_gpu

    def switch_to_backup(self) -> None:
        """Switch to the backup model for subsequent requests."""
        log.info("model_switch", from_model=self.current_chat_model, to_model=self.backup_model)
        self._use_backup = True

    def switch_to_primary(self) -> None:
        """Switch back to the primary chat model."""
        log.info("model_switch", from_model=self.current_chat_model, to_model=self.chat_model)
        self._use_backup = False

    def record_vision_use(self) -> None:
        """Mark the vision model as just used (resets unload timer)."""
        self._vision_last_used = time.monotonic()

    def vision_should_unload(self) -> bool:
        """Return True if the vision model should be unloaded."""
        if self._vision_last_used == 0.0:
            return False
        return time.monotonic() - self._vision_last_used > self.vision_unload_after_s

    async def unload_all(self) -> None:
        """Unload all models from VRAM immediately."""
        import httpx

        from core.config import cfg

        try:
            async with httpx.AsyncClient(base_url=cfg.model.ollama_host, timeout=3.0) as client:
                for model_tag in (self.chat_model, self.backup_model, self.vision_model):
                    await client.post("/api/generate", json={"model": model_tag, "keep_alive": 0})
            self._active_model = None
            log.info("all_models_unloaded")
        except Exception as e:
            log.warning("unload_all_error", error=str(e))

    def get_vram_stats(self) -> VRAMStats | None:
        """Return the most recent VRAM stats, or None if unavailable."""
        return self._last_vram

    async def start_monitoring(self) -> None:
        """Start the background VRAM polling task."""
        if self._vram_poll_task is None or self._vram_poll_task.done():
            self._vram_poll_task = asyncio.create_task(self._vram_poll_loop())
            log.info("vram_monitor_started")

    async def stop_monitoring(self) -> None:
        """Stop the VRAM polling task."""
        if self._vram_poll_task and not self._vram_poll_task.done():
            self._vram_poll_task.cancel()
            try:
                await self._vram_poll_task
            except asyncio.CancelledError:
                pass
        log.info("vram_monitor_stopped")

    # ------------------------------------------------------------------
    # VRAM monitoring
    # ------------------------------------------------------------------

    async def _vram_poll_loop(self) -> None:
        """Poll nvidia-smi every second; adjust num_gpu on low VRAM."""
        while True:
            try:
                stats = await asyncio.to_thread(self._read_vram)
                async with self._lock:
                    self._last_vram = stats
                    if stats and stats.free_gb < self.vram_low_watermark_gb:
                        self._reduce_num_gpu(stats)
                    if stats and stats.used_gb > self.vram_ceiling_gb:
                        log.warning(
                            "vram_ceiling_exceeded",
                            used_gb=round(stats.used_gb, 2),
                            ceiling_gb=self.vram_ceiling_gb,
                        )
            except Exception as exc:  # noqa: BLE001 - monitor must not crash
                log.warning("vram_poll_error", error=str(exc))

            await asyncio.sleep(1.0)

    def _read_vram(self) -> VRAMStats | None:
        """Read VRAM stats from nvidia-smi.

        Returns:
            VRAMStats or None if nvidia-smi is unavailable.
        """
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode != 0:
                return None
            line = result.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                return None
            return VRAMStats(
                total_mb=int(parts[0]),
                used_mb=int(parts[1]),
                free_mb=int(parts[2]),
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            return None

    def _reduce_num_gpu(self, stats: VRAMStats) -> None:
        """Lower num_gpu by 2 layers when free VRAM is critically low."""
        if self._num_gpu == "auto":
            # Read current from nvidia-smi; estimate a starting point
            self._num_gpu = 28
        elif isinstance(self._num_gpu, int) and self._num_gpu > 8:
            self._num_gpu = self._num_gpu - 2
            log.warning(
                "num_gpu_reduced",
                new_num_gpu=self._num_gpu,
                free_vram_gb=round(stats.free_gb, 2),
            )


def read_vram_sync() -> VRAMStats | None:
    """Synchronous VRAM read for use in the doctor check and tests."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode != 0:
            return None
        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            return None
        return VRAMStats(
            total_mb=int(parts[0]),
            used_mb=int(parts[1]),
            free_mb=int(parts[2]),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


_model_manager: ModelManager | None = None


def get_model_manager() -> ModelManager:
    """Return the singleton ModelManager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
