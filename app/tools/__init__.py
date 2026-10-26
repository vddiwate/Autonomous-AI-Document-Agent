from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry, tool_registry
from app.tools.content_tool import ContentGeneratorTool
from app.tools.table_tool import TableGeneratorTool

# Register default core tools
tool_registry.register(ContentGeneratorTool())
tool_registry.register(TableGeneratorTool())

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "tool_registry",
    "ContentGeneratorTool",
    "TableGeneratorTool"
]
