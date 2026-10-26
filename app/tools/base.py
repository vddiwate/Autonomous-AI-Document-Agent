from abc import ABC, abstractmethod
from typing import Any, Dict
from app.models.schemas import TaskItem

class BaseTool(ABC):
    """
    Abstract Base Class for all autonomous agent tools.
    Adheres to the Open/Closed Principle (SOLID).
    """
    name: str
    description: str

    @abstractmethod
    async def execute(self, task: TaskItem, context: Dict[str, Any]) -> Any:
        """
        Executes the specific capability of this tool.
        """
        pass
