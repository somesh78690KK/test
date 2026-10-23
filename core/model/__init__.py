"""T.A.R.O. model package."""

from core.model.model_manager import ModelManager, VRAMStats, read_vram_sync
from core.model.ollama_client import (
    ChatMessage,
    ChatResponse,
    ModelError,
    OllamaClient,
    ToolCall,
)

__all__ = [
    "ChatMessage",
    "ChatResponse",
    "ModelError",
    "OllamaClient",
    "ToolCall",
    "ModelManager",
    "VRAMStats",
    "read_vram_sync",
]
