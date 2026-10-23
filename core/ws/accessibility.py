"""T.A.R.O. - Keyboard shortcuts and accessibility manager (TASK-086).

ARCHITECTURE reference: section 24 (HUD).
TASKS: TASK-086.

Manages keyboard shortcuts for the HUD and ensures WCAG AA compliance:
  - Keyboard navigation (Tab, Escape, Enter, Arrow keys).
  - ARIA live region notifications for state changes.
  - Focus management for modals and confirmation dialogs.
  - High contrast mode support.

Acceptance (TASK-086): axe check passes with no critical issues.
"""

from __future__ import annotations

from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)


# Default keyboard shortcuts
DEFAULT_SHORTCUTS: list[dict[str, str]] = [
    {"key": "Ctrl+/", "action": "toggle_focus_chat", "description": "Focus chat input"},
    {"key": "Ctrl+K", "action": "command_palette", "description": "Open command palette"},
    {"key": "Ctrl+,", "action": "open_settings", "description": "Open settings"},
    {"key": "Ctrl+Shift+M", "action": "toggle_mute", "description": "Toggle microphone mute"},
    {"key": "Ctrl+Space", "action": "push_to_talk", "description": "Push-to-talk"},
    {"key": "Escape", "action": "close_modal", "description": "Close modal / cancel action"},
    {"key": "Ctrl+Alt+F12", "action": "kill_switch", "description": "Emergency kill switch"},
    {"key": "Ctrl+Shift+T", "action": "toggle_tools", "description": "Toggle tool activity panel"},
    {"key": "Ctrl+Shift+H", "action": "toggle_history", "description": "Toggle history view"},
    {"key": "Ctrl+Shift+V", "action": "toggle_memory", "description": "Toggle memory viewer"},
    {"key": "Tab", "action": "focus_next", "description": "Focus next interactive element"},
    {"key": "Shift+Tab", "action": "focus_prev", "description": "Focus previous element"},
    {"key": "Enter", "action": "activate", "description": "Activate focused element"},
]


class AccessibilityManager:
    """Manages keyboard shortcuts and WCAG AA accessibility features."""

    def __init__(self) -> None:
        self._shortcuts: list[dict[str, str]] = list(DEFAULT_SHORTCUTS)
        self._custom_shortcuts: dict[str, dict[str, str]] = {}
        self._high_contrast = False
        self._reduced_motion = False
        self._focus_visible = True

    @property
    def high_contrast(self) -> bool:
        return self._high_contrast

    @high_contrast.setter
    def high_contrast(self, value: bool) -> None:
        self._high_contrast = bool(value)

    def set_high_contrast(self, enabled: bool) -> None:
        self._high_contrast = bool(enabled)

    @property
    def reduced_motion(self) -> bool:
        return self._reduced_motion

    @reduced_motion.setter
    def reduced_motion(self, value: bool) -> None:
        self._reduced_motion = bool(value)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = bool(enabled)

    def get_shortcuts(self) -> list[dict[str, str]]:
        """Return all registered keyboard shortcuts."""
        all_shortcuts = list(self._shortcuts)
        for action, custom in self._custom_shortcuts.items():
            all_shortcuts.append(custom)
        return all_shortcuts

    def register_shortcut(self, key: str, action: str, description: str) -> None:
        """Register a custom keyboard shortcut."""
        self._custom_shortcuts[action] = {
            "key": key,
            "action": action,
            "description": description,
        }
        logger.info("shortcut_registered", key=key, action=action)

    def unregister_shortcut(self, action: str) -> bool:
        """Remove a custom shortcut."""
        if action in self._custom_shortcuts:
            del self._custom_shortcuts[action]
            return True
        return False

    def get_aria_attributes(self) -> dict[str, Any]:
        """Return ARIA attributes for the HUD layout."""
        return {
            "main_region": {
                "role": "main",
                "aria-label": "T.A.R.O. Assistant Chat",
            },
            "sidebar": {
                "role": "complementary",
                "aria-label": "System Telemetry and Status",
            },
            "tool_panel": {
                "role": "log",
                "aria-label": "Tool Activity Log",
                "aria-live": "polite",
            },
            "chat_input": {
                "role": "textbox",
                "aria-label": "Send a message to T.A.R.O.",
                "aria-multiline": "false",
            },
            "status_orb": {
                "role": "status",
                "aria-label": "System Status",
                "aria-live": "assertive",
            },
            "confirmation_dialog": {
                "role": "alertdialog",
                "aria-modal": "true",
                "aria-label": "Action Confirmation Required",
            },
            "settings_modal": {
                "role": "dialog",
                "aria-modal": "true",
                "aria-label": "Settings",
            },
        }

    def generate_accessibility_css(self) -> str:
        """Generate CSS for WCAG AA compliance features."""
        css_parts = [
            # Focus visible indicators (WCAG 2.4.7)
            """
/* Focus indicators - WCAG AA 2.4.7 */
:focus-visible {
    outline: 3px solid #4fc3f7;
    outline-offset: 2px;
    border-radius: 4px;
}
""",
            # Skip to main content link
            """
/* Skip link for keyboard nav */
.skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    padding: 8px 16px;
    background: #1a1a2e;
    color: #e0e0e0;
    z-index: 10000;
    transition: top 0.2s;
}
.skip-link:focus {
    top: 0;
}
""",
            # Minimum contrast ratio (4.5:1 for normal text)
            """
/* High contrast mode */
.high-contrast {
    --text-primary: #ffffff;
    --text-secondary: #e0e0e0;
    --bg-primary: #000000;
    --bg-secondary: #1a1a1a;
    --accent: #ffff00;
}
""",
            # Reduced motion preference
            """
/* Reduced motion - WCAG 2.3.3 */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
    .orb-ring { animation: none !important; }
}
""",
            # Minimum touch/click target size (44x44px per WCAG 2.5.5)
            """
/* Touch targets - WCAG 2.5.5 */
button, [role="button"], .clickable {
    min-height: 44px;
    min-width: 44px;
}
""",
        ]

        return "\n".join(css_parts)

    def get_state_announcements(self) -> dict[str, str]:
        """ARIA live region announcements for state transitions."""
        return {
            "idle": "T.A.R.O. is idle and ready.",
            "listening": "T.A.R.O. is listening for your voice input.",
            "thinking": "T.A.R.O. is processing your request.",
            "speaking": "T.A.R.O. is responding.",
            "error": "An error occurred. Check the status panel.",
            "tool_started": "Tool execution started.",
            "tool_completed": "Tool execution completed successfully.",
            "tool_failed": "Tool execution failed. See details in the activity panel.",
            "confirmation_needed": "Action requires your confirmation. Please review.",
        }
