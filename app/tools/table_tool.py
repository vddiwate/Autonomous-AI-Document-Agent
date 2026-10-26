import logging
from typing import Any, Dict
from app.tools.base import BaseTool
from app.models.schemas import TaskItem, TableData
from app.services.llm_service import llm_service

logger = logging.getLogger("tools.table")

class TableGeneratorTool(BaseTool):
    """
    Tool specialized in synthesizing structured numerical and tabular data.
    Outputs strict headers and rows for native Microsoft Word (.docx) table formatting.
    """
    name = "table_generator"
    description = "Produces structured numerical matrices, project timelines, budget breakdowns, or risk evaluation tables with headers and rows."

    async def execute(self, task: TaskItem, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesizes introductory narrative and a structured table.
        """
        doc_title = context.get("document_title", "Business Document")
        doc_type = context.get("document_type", "Report")
        assumptions = context.get("assumptions", [])
        assumptions_text = "\n".join(f"- {a}" for a in assumptions) if assumptions else "None."

        system_prompt = f"""You are a Quantitative Analyst and Technical Architect preparing a structured data section for '{doc_title}'.
Your task is to synthesize:
1. A brief explanatory narrative (1-2 paragraphs).
2. A comprehensive, realistic tabular matrix with professional column headers and detailed rows.
3. A key strategic takeaway / executive note.

Align strictly with documented project assumptions:
{assumptions_text}

OUTPUT FORMAT:
Respond STRICTLY with a valid JSON object matching this schema:
{{
  "intro_text": "string (1-2 introductory paragraphs establishing context)",
  "table": {{
    "headers": ["Column 1", "Column 2", "Column 3", "..."],
    "rows": [
      ["Row 1 Col 1", "Row 1 Col 2", "Row 1 Col 3", "..."],
      ["Row 2 Col 1", "Row 2 Col 2", "Row 2 Col 3", "..."]
    ]
  }},
  "callout_note": "string (A strategic risk note, budget disclaimer, or governance guideline)"
}}
"""
        user_prompt = f"""Task Objective: {task.title}
Detailed Instructions: {task.description}

Generate the structured JSON response (concise 1-paragraph intro, 3-4 structured table rows, and 1 crisp strategic callout note):"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        logger.info(f"Executing table_generator for task: '{task.title}'")
        try:
            result_json = await llm_service.complete_json(messages=messages, max_tokens=550)
            raw_table = result_json.get("table", {})
            table_data = TableData(
                headers=raw_table.get("headers", []),
                rows=raw_table.get("rows", [])
            )
            return {
                "intro_text": result_json.get("intro_text", ""),
                "table": table_data,
                "callout_note": result_json.get("callout_note", "")
            }
        except Exception as e:
            logger.error(f"table_generator failed for task '{task.title}': {e}")
            raise RuntimeError(f"Table generation failed: {e}")
