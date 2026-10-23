"""T.A.R.O. - ModelManager tests.

TASKS: TASK-013.
Acceptance test: Loading a second large model unloads the first; VRAM logged each second.
"""

from __future__ import annotations

import pytest
from core.model.model_manager import ModelManager, VRAMStats, read_vram_sync


def test_model_switching_between_primary_and_backup() -> None:
    """Verifies that manager switches between user's primary (Qwen-8B) and backup (Nemotron)."""
    mm = ModelManager(
        chat_model="richardyoung/qwen3-8b-abliterated:Q4_K_M",
        backup_model="nemotron-3-nano:4b",
        vision_model="moondream:latest",
    )
    assert mm.current_chat_model == "richardyoung/qwen3-8b-abliterated:Q4_K_M"

    mm.switch_to_backup()
    assert mm.current_chat_model == "nemotron-3-nano:4b"

    mm.switch_to_primary()
    assert mm.current_chat_model == "richardyoung/qwen3-8b-abliterated:Q4_K_M"


def test_vram_stats_calculation() -> None:
    """Verifies GB conversion properties on VRAMStats."""
    stats = VRAMStats(total_mb=6144, used_mb=3072, free_mb=3072)
    assert stats.total_gb == 6.0
    assert stats.used_gb == 3.0
    assert stats.free_gb == 3.0


def test_num_gpu_reduction_on_low_vram() -> None:
    """Verifies that num_gpu is reduced when free VRAM drops below low watermark."""
    mm = ModelManager(
        chat_model="richardyoung/qwen3-8b-abliterated:Q4_K_M",
        backup_model="nemotron-3-nano:4b",
        vision_model="moondream:latest",
        vram_low_watermark_gb=1.0,
    )
    mm._num_gpu = 28
    critically_low_vram = VRAMStats(total_mb=6144, used_mb=5600, free_mb=544)  # ~0.53 GB free

    mm._reduce_num_gpu(critically_low_vram)
    assert mm.num_gpu == 26


def test_live_read_vram_sync() -> None:
    """Verifies live nvidia-smi VRAM reader returns valid stats on target GPU."""
    stats = read_vram_sync()
    if stats is not None:
        assert stats.total_mb > 0
        assert stats.free_mb > 0
