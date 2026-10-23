"""T.A.R.O. - User Profile loader.

MEMORY reference: section 4.
TASKS: TASK-060.

Reads data/profile.md. Recreates from template if missing.
Only non-empty fields filled in by the user are sent to the prompt.
"""

from __future__ import annotations

from pathlib import Path

from core.log.setup import get_logger

logger = get_logger(__name__)

PROFILE_TEMPLATE = """# Profile

- Name:
- Preferred name for T.A.R.O.:
- Machine: Ryzen 5 6600H, RTX 4050 6GB, 16 GB RAM
- Language(s): English
- Preferred reply length: short
- Voice: on
- Projects I am working on:
"""


class UserProfile:
    """Manages the user-editable profile markdown file."""

    def __init__(self, profile_path: Path | str = "data/profile.md") -> None:
        self.path = Path(profile_path)
        self.ensure_exists()

    def ensure_exists(self) -> None:
        """Create template profile.md if it does not exist."""
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(PROFILE_TEMPLATE, encoding="utf-8")
            logger.info("created_default_profile", path=str(self.path))

    def load_active_fields(self) -> dict[str, str]:
        """Read profile.md and return only non-empty fields."""
        if not self.path.exists():
            return {}

        fields: dict[str, str] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("-") and ":" in line:
                key, _, val = line[1:].partition(":")
                key = key.strip()
                val = val.strip()
                if val:
                    fields[key] = val
        return fields

    def format_for_prompt(self, max_tokens: int = 200) -> str:
        """Format active fields for injection into system prompt."""
        active = self.load_active_fields()
        if not active:
            return ""

        lines = [f"- {k}: {v}" for k, v in active.items()]
        text = "\n".join(lines)
        # Approximate 4 chars per token
        if len(text) > max_tokens * 4:
            text = text[: max_tokens * 4].rstrip() + "\n...[truncated]"
        return text


# Global singleton
_profile: UserProfile | None = None


def get_user_profile(path: Path | str | None = None) -> UserProfile:
    """Return singleton UserProfile."""
    global _profile
    if _profile is None or path is not None:
        _profile = UserProfile(path or "data/profile.md")
    return _profile
