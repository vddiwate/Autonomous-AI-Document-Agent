import os
import time
import json
import asyncio
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.config import settings
from app.api.schemas import (
    AgentRequest,
    AgentResponse,
    DocumentMetadata,
    CriticReviewSummary,
    HealthResponse
)
from app.agent.workflow import agent_workflow
from app.agent.planner import planner
from app.agent.executor import step_executor
from app.agent.critic import critic
from app.services.llm_service import llm_service
from app.services.document_service import document_service
from app.prompts.router_prompt import get_router_system_prompt
from app.models.schemas import DocumentSection

logger = logging.getLogger("api.routes")
router = APIRouter()

def is_obviously_document_request(text: str) -> bool:
    """Fast-path heuristic to bypass router LLM overhead for clear document/knowledge requests."""
    t = text.lower().strip()
    greetings = {"hi", "hello", "hey", "hola", "how are you", "who are you", "help", "yo"}
    if t in greetings:
        return False
    doc_keywords = ["what", "how", "why", "difference", "explain", "create", "plan", "architecture", "design", "sop", "proposal", "roadmap", "strategy", "compare", "build"]
    return len(t.split()) > 3 or any(k in t for k in doc_keywords)

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
    user_request = payload.request.strip()

    # Contextual resolution for affirmative follow-ups (e.g. "yes do", "proceed", "create it")
    if payload.history and len(user_request.split()) <= 4 and any(w in user_request.lower() for w in ["yes", "do", "proceed", "make", "create", "generate", "sure", "ok", "okay"]):
        last_topics = [h.get("content", "") for h in payload.history if h.get("role") == "user"]
        if last_topics:
            user_request = f"Generate the comprehensive executive document for: {last_topics[-1]}"
            logger.info(f"Resolved follow-up context to: '{user_request}'")

    logger.info(f"Received request on /agent: '{user_request[:80]}...'")

    try:
        # Invoke LangGraph StateGraph Workflow
        result_state = await agent_workflow.ainvoke({"request": user_request})
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

        # Formulate informative conversational message answering the prompt first
        chat_summary = getattr(plan, "chat_summary", None)
        if not chat_summary:
            sections = result_state.get("sections", [])
            if sections and sections[0].content:
                chat_summary = sections[0].content

        if chat_summary and chat_summary.strip():
            final_message = (
                f"{chat_summary.strip()}\n\n"
                f"---\n"
                f"I have also synthesized an in-depth, executive-grade document **'{plan.document_title}'** ({plan.document_type}) "
                f"covering all architectural components, data tables, and implementation steps. You can download the Microsoft Word (.docx) file below."
            )
        else:
            final_message = (
                f"Successfully planned and executed {len(plan.tasks)} tasks to produce "
                f"'{plan.document_title}' ({plan.document_type})."
            )

        return AgentResponse(
            status="success",
            intent="document_generation",
            message=final_message,
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

@router.post("/agent/stream", tags=["Autonomous Agent"])
async def run_agent_stream(payload: AgentRequest, request: Request):
    """
    Streams step-by-step progress events (Plan created, tasks running/completed, critic review, document compilation)
    followed by the final AgentResponse.
    """
    async def event_generator():
        start_time = time.time()
        try:
            user_request = payload.request.strip()

            # Contextual resolution for affirmative follow-ups (e.g. "yes do", "proceed", "create it")
            if payload.history and len(user_request.split()) <= 4 and any(w in user_request.lower() for w in ["yes", "do", "proceed", "make", "create", "generate", "sure", "ok", "okay"]):
                last_topics = [h.get("content", "") for h in payload.history if h.get("role") == "user"]
                if last_topics:
                    user_request = f"Generate the comprehensive executive document for: {last_topics[-1]}"
                    logger.info(f"Resolved follow-up context to: '{user_request}'")

            # Stage 1: Router (with 0s fast-path bypass)
            is_fast_doc = is_obviously_document_request(user_request)
            if is_fast_doc:
                intent = "document_generation"
                yield json.dumps({
                    "type": "stage",
                    "stage": "router",
                    "status": "completed",
                    "message": "Intent verified: Document & Strategic Plan generation (Fast-path)"
                }) + "\n"
            else:
                yield json.dumps({
                    "type": "stage",
                    "stage": "router",
                    "status": "running",
                    "message": "Analyzing request intent..."
                }) + "\n"

                messages = [
                    {"role": "system", "content": get_router_system_prompt()},
                    {"role": "user", "content": f"User Input:\n{user_request}"}
                ]
                classification = await llm_service.complete_json(messages=messages, max_tokens=250)
                intent = classification.get("intent", "document_generation")
                reply = classification.get("reply")

                if intent == "conversation":
                    chat_messages = [
                        {"role": "system", "content": "You are PlanToDoc AI, an autonomous business and strategy document agent. Be concise, direct, helpful, and professional."},
                        {"role": "user", "content": user_request}
                    ]
                    full_reply = ""
                    try:
                        async for token in llm_service.stream_complete(messages=chat_messages, max_tokens=300):
                            full_reply += token
                            yield json.dumps({"type": "text_delta", "delta": token}) + "\n"
                            await asyncio.sleep(0.01)
                    except Exception:
                        full_reply = reply or "Hello! How can I assist you with your document today?"
                        yield json.dumps({"type": "text_delta", "delta": full_reply}) + "\n"

                    elapsed_time = round(time.time() - start_time, 2)
                    resp = AgentResponse(
                        status="success",
                        intent="conversation",
                        message=full_reply,
                        execution_time_seconds=elapsed_time
                    )
                    yield json.dumps({"type": "complete", "response": resp.model_dump()}) + "\n"
                    return

                yield json.dumps({
                    "type": "stage",
                    "stage": "router",
                    "status": "completed",
                    "message": "Intent verified: Document & Strategic Plan generation"
                }) + "\n"

            # Stage 2: Planner
            yield json.dumps({
                "type": "stage",
                "stage": "planner",
                "status": "running",
                "message": "Formulating execution plan, assumptions, and task decomposition..."
            }) + "\n"

            plan = await planner.create_plan(user_request)
            yield json.dumps({
                "type": "stage",
                "stage": "planner",
                "status": "completed",
                "message": f"Plan created: '{plan.document_title}' ({plan.document_type}) with {len(plan.tasks)} tasks",
                "plan": plan.model_dump()
            }) + "\n"

            # Stream direct answer/explanation tokens immediately to the UI
            chat_summary = getattr(plan, "chat_summary", None)
            if chat_summary and chat_summary.strip():
                words = chat_summary.strip().split(" ")
                for idx, word in enumerate(words):
                    yield json.dumps({"type": "text_delta", "delta": word + " "}) + "\n"
                    if idx % 4 == 0:
                        await asyncio.sleep(0.02)

            # Stage 3: Concurrent Tool Execution (Run all tasks in parallel)
            total_tasks = len(plan.tasks)
            context = {
                "document_title": plan.document_title,
                "document_type": plan.document_type,
                "assumptions": plan.assumptions
            }

            for task in plan.tasks:
                yield json.dumps({
                    "type": "task",
                    "task_id": task.id,
                    "total_tasks": total_tasks,
                    "title": task.title,
                    "tool": task.tool,
                    "status": "running",
                    "message": f"Task {task.id}/{total_tasks} is running: '{task.title}' ({task.tool})..."
                }) + "\n"

            event_queue = asyncio.Queue()

            async def run_single_task(task_item):
                sec = await step_executor.execute_single_task(task_item, context, total_tasks)
                await event_queue.put((task_item, sec))
                return sec

            task_runners = [
                asyncio.create_task(run_single_task(t))
                for t in plan.tasks
            ]

            # Stream completion events dynamically as each concurrent task finishes
            for _ in range(total_tasks):
                finished_task, _ = await event_queue.get()
                yield json.dumps({
                    "type": "task",
                    "task_id": finished_task.id,
                    "total_tasks": total_tasks,
                    "title": finished_task.title,
                    "tool": finished_task.tool,
                    "status": "completed",
                    "message": f"Task {finished_task.id}/{total_tasks} completed: '{finished_task.title}'"
                }) + "\n"

            sections = await asyncio.gather(*task_runners)

            # If chat_summary was empty, stream first section content
            if not chat_summary and sections and sections[0].content:
                chat_summary = sections[0].content
                words = chat_summary.strip().split(" ")
                for idx, word in enumerate(words):
                    yield json.dumps({"type": "text_delta", "delta": word + " "}) + "\n"
                    if idx % 4 == 0:
                        await asyncio.sleep(0.03)

            # Stage 4: Critic QA
            yield json.dumps({
                "type": "stage",
                "stage": "critic",
                "status": "running",
                "message": "Autonomous QA Critic evaluating document quality and completeness..."
            }) + "\n"

            report = await critic.evaluate_document(
                user_request=user_request,
                plan=plan,
                sections=sections
            )

            yield json.dumps({
                "type": "stage",
                "stage": "critic",
                "status": "completed",
                "passed": report.passed,
                "quality_score": report.quality_score,
                "message": f"Critic review completed (Score: {report.quality_score}/10, Passed: {report.passed})"
            }) + "\n"

            # Stage 5: Document Builder
            yield json.dumps({
                "type": "stage",
                "stage": "document_builder",
                "status": "running",
                "message": "Compiling styled Microsoft Word (.docx) document..."
            }) + "\n"

            doc_path = document_service.generate_docx(plan, sections)
            filename = os.path.basename(doc_path)
            file_size = os.path.getsize(doc_path)
            base_url = str(request.base_url).rstrip("/")
            download_url = f"{base_url}/agent/documents/{filename}"

            elapsed_time = round(time.time() - start_time, 2)

            # Formulate informative summary
            chat_summary = getattr(plan, "chat_summary", None)
            if not chat_summary and sections:
                chat_summary = sections[0].content

            if chat_summary and chat_summary.strip():
                final_message = (
                    f"{chat_summary.strip()}\n\n"
                    f"---\n"
                    f"I have also synthesized an in-depth, executive-grade document **'{plan.document_title}'** ({plan.document_type}) "
                    f"covering all architectural components, data tables, and implementation steps. You can download the Microsoft Word (.docx) file below."
                )
            else:
                final_message = (
                    f"Successfully planned and executed {len(plan.tasks)} tasks to produce "
                    f"'{plan.document_title}' ({plan.document_type})."
                )

            final_resp = AgentResponse(
                status="success",
                intent="document_generation",
                message=final_message,
                execution_time_seconds=elapsed_time,
                plan=plan,
                critic_review=CriticReviewSummary(
                    passed=report.passed,
                    notes=report.critique_notes
                ),
                document=DocumentMetadata(
                    filename=filename,
                    download_url=download_url,
                    file_size_bytes=file_size
                )
            )

            yield json.dumps({
                "type": "stage",
                "stage": "document_builder",
                "status": "completed",
                "message": f"Document compiled: {filename}"
            }) + "\n"

            yield json.dumps({
                "type": "complete",
                "response": final_resp.model_dump()
            }) + "\n"

        except Exception as e:
            logger.error(f"Error in stream: {e}", exc_info=True)
            yield json.dumps({
                "type": "error",
                "message": f"Execution error: {str(e)}"
            }) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

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
