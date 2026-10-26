import os
import time
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.config import settings
from app.api.schemas import (
    AgentRequest,
    AgentResponse,
    DocumentMetadata,
    CriticReviewSummary,
    HealthResponse
)
from app.agent.workflow import agent_workflow

logger = logging.getLogger("api.routes")
router = APIRouter()

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Returns application health and configuration metadata."""
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        configured_model=settings.MODEL_NAME
    )

@router.post("/agent", response_model=AgentResponse, tags=["Autonomous Agent"])
async def run_agent(payload: AgentRequest, request: Request):
    """
    Main Autonomous Agent Endpoint with Smart Intent Routing.
    - If input is a greeting or general chat: Returns an instant conversational response.
    - If input is an informational or document request: Executes LangGraph (Plan -> Tools -> Critic -> Docx).
    """
    start_time = time.time()
    logger.info(f"Received request on /agent: '{payload.request[:80]}...'")

    try:
        # Invoke LangGraph StateGraph Workflow
        result_state = await agent_workflow.ainvoke({"request": payload.request})
        elapsed_time = round(time.time() - start_time, 2)
        intent = result_state.get("intent", "document_generation")

        # 1. Handle Conversational Greeting / Chat
        if intent == "conversation":
            return AgentResponse(
                status="success",
                intent="conversation",
                message=result_state.get("conversational_reply", "Hello! How can I assist you with your document today?"),
                execution_time_seconds=elapsed_time,
                plan=None,
                critic_review=None,
                document=None
            )

        # 2. Handle Document Generation
        doc_path = result_state.get("document_path")
        filename = result_state.get("document_filename")

        if not doc_path or not os.path.exists(doc_path):
            raise HTTPException(
                status_code=500,
                detail="Workflow finished but Word document could not be located on disk."
            )

        file_size = os.path.getsize(doc_path)
        base_url = str(request.base_url).rstrip("/")
        download_url = f"{base_url}/agent/documents/{filename}"

        plan = result_state["plan"]
        return AgentResponse(
            status="success",
            intent="document_generation",
            message=(
                f"Successfully planned and executed {len(plan.tasks)} tasks to produce "
                f"'{plan.document_title}' ({plan.document_type})."
            ),
            execution_time_seconds=elapsed_time,
            plan=plan,
            critic_review=CriticReviewSummary(
                passed=result_state.get("critique_passed", True),
                notes=result_state.get("reflection_notes", "Document passed QA checks.")
            ),
            document=DocumentMetadata(
                filename=filename,
                download_url=download_url,
                file_size_bytes=file_size
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during agent execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agent workflow execution failed: {str(e)}"
        )

@router.get("/agent/documents/{filename}", tags=["Documents"])
async def download_document(filename: str):
    """
    Directly downloads the generated Microsoft Word (.docx) document.
    """
    storage_dir = settings.absolute_storage_dir
    safe_filename = os.path.basename(filename)
    file_path = storage_dir / safe_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Requested document not found.")

    return FileResponse(
        path=str(file_path),
        filename=safe_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
