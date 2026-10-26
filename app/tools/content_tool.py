import logging
from typing import Any, Dict
from app.tools.base import BaseTool
from app.models.schemas import TaskItem
from app.services.llm_service import llm_service

logger = logging.getLogger("tools.content")

class ContentGeneratorTool(BaseTool):
    """
    Tool specialized in synthesizing comprehensive, professional business narratives.
    Produces high-quality executive paragraphs, bulleted breakdowns, and strategic takeaways.
    """
    name = "content_generator"
    description = "Synthesizes in-depth strategic narratives, executive summaries, technical methodology, and governance policies."

    async def execute(self, task: TaskItem, context: Dict[str, Any]) -> str:
        """
        Executes content synthesis using the LLM.
        """
        doc_title = context.get("document_title", "Business Document")
        doc_type = context.get("document_type", "Report")
        assumptions = context.get("assumptions", [])
        assumptions_text = "\n".join(f"- {a}" for a in assumptions) if assumptions else "None specified."

        system_prompt = f"""You are an Executive Business & Technical Writer preparing a section for a formal {doc_type}: '{doc_title}'.
Produce thorough, authoritative, and actionable content.

GUIDELINES:
- Write in a polished, professional corporate tone.
- Do not output generic placeholder text (e.g. 'Lorem Ipsum' or 'TBD').
- Use clear paragraph structure and relevant bullet points.
- Align strictly with the document's assumptions:
{assumptions_text}
- Output ONLY the section content. Do NOT include section title prefixes like 'Section 1:' or markdown code fences.
"""
        user_prompt = f"""Task Objective: {task.title}
Detailed Instructions: {task.description}

Provide a concise, high-impact executive section (2 focused paragraphs plus 3 key bullet points, approximately 180 words):"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        logger.info(f"Executing content_generator for task: '{task.title}'")
        try:
            content = await llm_service.complete(messages=messages, max_tokens=400)
            return content.strip()
        except Exception as e:
            logger.error(f"content_generator failed for task '{task.title}': {e}")
            raise RuntimeError(f"Content generation failed: {e}")
