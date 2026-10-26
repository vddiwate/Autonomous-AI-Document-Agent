import logging
from typing import Dict, List, Optional
from app.tools.base import BaseTool

logger = logging.getLogger("tools.registry")

class ToolRegistry:
    """
    Central registry for dynamic tool discovery and execution.
    Allows zero-code modification when extending new tools.
    """
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Registers a new tool instance."""
        if not tool.name:
            raise ValueError("Tool name must not be empty.")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: '{tool.name}'")

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieves a registered tool by its name."""
        return self._tools.get(name)

    def get_metadata(self) -> List[Dict[str, str]]:
        """
        Returns dynamic metadata (names and descriptions) of all registered tools.
        Used to inject available tools dynamically into the Planner prompt.
        """
        return [
            {"name": tool.name, "description": tool.description}
            for tool in self._tools.values()
        ]

    def list_tools(self) -> List[str]:
        """Returns list of registered tool names."""
        return list(self._tools.keys())

tool_registry = ToolRegistry()
