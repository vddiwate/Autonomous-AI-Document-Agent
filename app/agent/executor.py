import asyncio
import logging
from typing import Any, Dict, List
from app.models.schemas import Plan, TaskItem, DocumentSection, TableData
from app.tools import tool_registry

logger = logging.getLogger("agent.executor")

class StepExecutor:
    """
    Autonomous Execution Engine that processes the Planner's TODO list.
    Orchestrates specialized tools dynamically from the ToolRegistry with concurrent execution
    and enterprise structured logging.
    """
    def __init__(self):
        self.registry = tool_registry

    async def execute_single_task(self, task: TaskItem, context: Dict[str, Any], total_tasks: int) -> DocumentSection:
        """
        Executes an individual task using its designated registered tool.
        """
        task.status = "in_progress"
        logger.info(f"[TASK_RUNNING] [{task.id}/{total_tasks}]: '{task.title}' | Tool: '{task.tool}'")

        tool = self.registry.get(task.tool)
        if not tool:
            logger.warning(f"[TOOL_FALLBACK] Tool '{task.tool}' not found in registry. Defaulting to 'content_generator'")
            tool = self.registry.get("content_generator")

        if not tool:
            raise RuntimeError(f"No execution tool available for task {task.id}")

        try:
            tool_output = await tool.execute(task, context)

            # Construct clean DocumentSection based on tool output type
            if isinstance(tool_output, dict) and "table" in tool_output:
                section = DocumentSection(
                    section_id=task.id,
                    title=task.title,
                    content=tool_output.get("intro_text", ""),
                    table=tool_output.get("table"),
                    callout=tool_output.get("callout_note")
                )
                output_meta = f"Table ({len(section.table.rows)} rows)"
            else:
                section = DocumentSection(
                    section_id=task.id,
                    title=task.title,
                    content=str(tool_output),
                    table=None,
                    callout=None
                )
                output_meta = f"Narrative text ({len(section.content)} chars)"

            task.status = "completed"
            task.result = f"Successfully synthesized section '{task.title}'"
            logger.info(f"[TASK_SUCCESS] [{task.id}/{total_tasks}]: '{task.title}' | Payload: {output_meta}")
            return section

        except Exception as e:
            task.status = "failed"
            task.result = str(e)
            logger.error(f"[TASK_FAILED] [{task.id}/{total_tasks}]: '{task.title}' - Error: {e}", exc_info=True)
            raise RuntimeError(f"Step execution failure on task {task.id} ('{task.title}'): {e}")

    async def execute_plan(self, plan: Plan) -> List[DocumentSection]:
        """
        Executes plan tasks concurrently with asyncio.gather to achieve ultra-low latency.
        Preserves strict document section order by task ID.
        """
        total_tasks = len(plan.tasks)
        logger.info("----------------------------------------------------------------------")
        logger.info(f"[EXECUTOR_START] Processing {total_tasks} tasks concurrently for: '{plan.document_title}'")
        logger.info("----------------------------------------------------------------------")
        
        context: Dict[str, Any] = {
            "document_title": plan.document_title,
            "document_type": plan.document_type,
            "assumptions": plan.assumptions
        }

        # Concurrently execute all tasks in parallel
        task_coroutines = [
            self.execute_single_task(task, context, total_tasks)
            for task in plan.tasks
        ]
        sections = await asyncio.gather(*task_coroutines)

        logger.info("----------------------------------------------------------------------")
        logger.info(f"[EXECUTOR_COMPLETE] All {total_tasks} tasks executed concurrently.")
        logger.info("----------------------------------------------------------------------")
        return list(sections)

step_executor = StepExecutor()
