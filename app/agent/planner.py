import logging
from typing import Any, Dict, List, Optional
from app.models.schemas import Plan, TaskItem
from app.services.llm_service import llm_service
from app.tools import tool_registry
from app.prompts.planner_prompt import get_planner_system_prompt

logger = logging.getLogger("agent.planner")

class Planner:
    """
    Autonomous Planner component that analyzes user requests and creates dynamic execution plans.
    Retrieves available tools dynamically from the central ToolRegistry.
    Uses clean enterprise logging with zero emojis.
    """
    def __init__(self):
        self.llm = llm_service

    async def create_plan(self, request: str) -> Plan:
        """
        Generates an autonomous plan from the user's prompt dynamically.
        """
        logger.info(f"Analyzing request and formulating execution plan for: '{request[:80]}...'")
        
        # Dynamically inject registered tools metadata into prompt
        tools_metadata = tool_registry.get_metadata()
        system_prompt = get_planner_system_prompt(tools_metadata)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Request:\n{request}"}
        ]

        try:
            plan_json = await self.llm.complete_json(messages=messages, max_tokens=850)
            
            # Dynamically convert parsed tasks into validated TaskItem models
            tasks = [
                TaskItem(
                    id=t.get("id", idx + 1),
                    title=t.get("title", f"Task {idx + 1}"),
                    description=t.get("description", ""),
                    tool=t.get("tool", "content_generator"),
                    status="pending"
                )
                for idx, t in enumerate(plan_json.get("tasks", []))
            ]

            plan = Plan(
                document_title=plan_json.get("document_title", "Business Document"),
                document_type=plan_json.get("document_type", "Standard Report"),
                is_ambiguous=bool(plan_json.get("is_ambiguous", False)),
                assumptions=plan_json.get("assumptions", []),
                tasks=tasks
            )

            # Enterprise structured logging
            logger.info("----------------------------------------------------------------------")
            logger.info(f"[PLAN_CREATED] Title: '{plan.document_title}' | Type: '{plan.document_type}' | Ambiguous: {plan.is_ambiguous}")
            if plan.assumptions:
                logger.info(f"[PLAN_ASSUMPTIONS] {len(plan.assumptions)} assumptions formulated:")
                for idx, a in enumerate(plan.assumptions, 1):
                    logger.info(f"  Assump #{idx}: {a}")

            logger.info(f"[PLAN_TODO_TASKS] Total: {len(plan.tasks)} tasks scheduled:")
            for t in plan.tasks:
                logger.info(f"  Task #{t.id} [PENDING]: '{t.title}' | Tool: '{t.tool}'")
            logger.info("----------------------------------------------------------------------")

            return plan

        except Exception as e:
            logger.error(f"[PLAN_FAILED] Error generating plan: {e}", exc_info=True)
            raise RuntimeError(f"Failed to generate autonomous plan: {e}")

planner = Planner()
