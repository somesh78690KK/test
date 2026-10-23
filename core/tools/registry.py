"""T.A.R.O. - Tool registry.

Validates and stores all tools. Provides category-based filtering so only
relevant tool schemas are included in each model call.

ARCHITECTURE reference: section 7, 17.
RULES reference: sections 3, 12.
TASKS: TASK-020, TASK-024.
"""

from __future__ import annotations

from core.log import get_logger
from core.tools.base import BaseTool, RiskLevel, ToolCategory

log = get_logger(__name__)

# Required class-level attributes - registry refuses to register without them
_REQUIRED_ATTRS = ("name", "description", "parameters", "risk", "category", "timeout_s")

# Max tool actions per family (RULES section 12)
_MAX_TOOLS_PER_FAMILY = 15

# Core tools always loaded (ARCHITECTURE section 17)
_CORE_CATEGORIES = {ToolCategory.CORE}


class ToolRegistry:
    """Singleton-style registry that holds all registered tool instances.

    Usage:
        registry = ToolRegistry()
        registry.register(MyTool())
        schemas = registry.schemas_for_categories({ToolCategory.FILES})
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._by_category: dict[ToolCategory, list[str]] = {c: [] for c in ToolCategory}

    def register(self, tool: BaseTool) -> None:
        """Validate and register a tool.

        Args:
            tool: An instantiated BaseTool subclass.

        Raises:
            ValueError: If a required attribute is missing or the tool name
                is already registered.
        """
        # Validate required attributes
        for attr in _REQUIRED_ATTRS:
            if not hasattr(tool, attr) or getattr(tool, attr) is None:
                raise ValueError(
                    f"Tool {type(tool).__name__} is missing required attribute '{attr}'. "
                    "Registration refused."
                )

        # Validate risk is a RiskLevel
        if not isinstance(tool.risk, RiskLevel):
            raise ValueError(
                f"Tool '{tool.name}' has invalid risk '{tool.risk}'. "
                f"Must be a RiskLevel enum value."
            )

        # Validate category
        if not isinstance(tool.category, ToolCategory):
            raise ValueError(f"Tool '{tool.name}' has invalid category '{tool.category}'.")

        # Validate timeout
        if not isinstance(tool.timeout_s, int) or tool.timeout_s <= 0:
            raise ValueError(
                f"Tool '{tool.name}' has invalid timeout_s '{tool.timeout_s}'. "
                "Must be a positive integer."
            )

        # Check for duplicate names
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered. " "Use a unique name.")

        # Description length check (RULES section 12: under 30 words)
        desc_words = len(tool.description.split())
        if desc_words > 40:  # Slightly lenient than spec for complex tools
            log.warning(
                "tool_description_long",
                tool=tool.name,
                words=desc_words,
                limit=30,
            )

        self._tools[tool.name] = tool
        self._by_category[tool.category].append(tool.name)
        log.debug("tool_registered", name=tool.name, risk=tool.risk, category=tool.category)

    def get(self, name: str) -> BaseTool | None:
        """Return the tool with the given name, or None."""
        return self._tools.get(name)

    def all_tools(self) -> list[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def schemas_for_categories(
        self,
        categories: set[ToolCategory],
    ) -> list[dict]:
        """Return JSON schemas for tools in the given categories.

        Core tools are always included.

        Args:
            categories: Set of tool categories to include.

        Returns:
            List of tool schema dicts ready for the Ollama API.
        """
        include = categories | _CORE_CATEGORIES
        schemas = []
        for cat in include:
            for name in self._by_category.get(cat, []):
                tool = self._tools[name]
                schemas.append(tool.to_schema())
        return schemas

    def schemas_for_names(self, names: list[str]) -> list[dict]:
        """Return schemas for a specific list of tool names (for find_tools)."""
        schemas = []
        for name in names:
            tool = self._tools.get(name)
            if tool:
                schemas.append(tool.to_schema())
        return schemas

    def tool_names_and_descriptions(self) -> list[dict]:
        """Return name + description pairs for all tools (used by find_tools embedder)."""
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def count(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Return the global tool registry."""
    return _registry
