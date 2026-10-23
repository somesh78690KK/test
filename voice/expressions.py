"""T.A.R.O. - AI Voice Expressions & Emotional State Manager.

Integrates custom expressive voice files and maps conversational states to
visual and vocal expressions:
- Maps sentences and post-sentence vocal expressions (sighs, chuckles, thoughtful hums).
- Triggers dynamic emotional state broadcasts to the HUD.
- Serves and plays custom ElevenLabs voice recordings.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.log.setup import get_logger

logger = get_logger(__name__)

EXPRESSIONS_DIR = Path("voice/assets/expressions")


@dataclass
class VoiceExpression:
    id: str
    name: str
    category: str  # "greeting", "thoughtful", "pleased", "curious", "focused", "empathetic"
    audio_file: str
    description: str
    visual_theme: dict[str, str] = field(default_factory=dict)


DEFAULT_EXPRESSIONS: list[VoiceExpression] = [
    VoiceExpression(
        id="exp_ram_edtech_1",
        name="Ram - Slow Clear EdTech Expression 1",
        category="thoughtful",
        audio_file="expression_sample_1.mp3",
        description="Slow, clear, thoughtful vocal delivery with expressive post-sentence inflection.",
        visual_theme={"badge": "💡 Thoughtful", "color": "#7df9ff", "glow": "0 0 25px rgba(125, 249, 255, 0.6)"},
    ),
    VoiceExpression(
        id="exp_ram_edtech_2",
        name="Ram - Slow Clear EdTech Expression 2",
        category="empathetic",
        audio_file="expression_sample_2.mp3",
        description="Warm, patient, educational tone showing genuine understanding and engagement.",
        visual_theme={"badge": "✨ Empathetic", "color": "#b388ff", "glow": "0 0 25px rgba(179, 136, 255, 0.6)"},
    ),
]


class ExpressionManager:
    """Manages AI vocal and visual expressions."""

    def __init__(self, assets_dir: Path | None = None) -> None:
        self.assets_dir = assets_dir or EXPRESSIONS_DIR
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.expressions: dict[str, VoiceExpression] = {e.id: e for e in DEFAULT_EXPRESSIONS}
        self.current_expression: VoiceExpression = DEFAULT_EXPRESSIONS[0]
        self._import_from_downloads()

    def _import_from_downloads(self) -> None:
        """Automatically imports ElevenLabs audio files from user's Downloads directory if present."""
        downloads_dir = Path(os.path.expanduser(r"~\Downloads"))
        if not downloads_dir.exists():
            return

        candidates = list(downloads_dir.glob("ElevenLabs*Ram*.mp3"))
        for idx, src in enumerate(candidates, 1):
            dest_name = f"expression_sample_{idx}.mp3"
            dest_path = self.assets_dir / dest_name
            try:
                if not dest_path.exists() or dest_path.stat().st_size != src.stat().st_size:
                    shutil.copy2(src, dest_path)
                    logger.info("imported_user_voice_expression", src=src.name, dest=dest_name)
            except Exception as e:
                logger.debug("voice_import_notice", error=str(e))

    def get_expression(self, expression_id: str) -> VoiceExpression | None:
        return self.expressions.get(expression_id)

    def list_expressions(self) -> list[dict[str, Any]]:
        return [
            {
                "id": e.id,
                "name": e.name,
                "category": e.category,
                "audio_url": f"/voice/assets/expressions/{e.audio_file}",
                "description": e.description,
                "visual_theme": e.visual_theme,
            }
            for e in self.expressions.values()
        ]

    def set_active_expression(self, category_or_id: str) -> VoiceExpression:
        """Updates the current active expression."""
        for e in self.expressions.values():
            if e.id == category_or_id or e.category.lower() == category_or_id.lower():
                self.current_expression = e
                logger.info("active_expression_changed", expression=e.id, category=e.category)
                return e
        return self.current_expression


_GLOBAL_EXPRESSION_MANAGER: ExpressionManager | None = None


def get_expression_manager() -> ExpressionManager:
    global _GLOBAL_EXPRESSION_MANAGER
    if _GLOBAL_EXPRESSION_MANAGER is None:
        _GLOBAL_EXPRESSION_MANAGER = ExpressionManager()
    return _GLOBAL_EXPRESSION_MANAGER
