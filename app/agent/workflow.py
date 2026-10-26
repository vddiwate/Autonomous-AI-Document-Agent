import os
import logging
from typing import Any, Dict
from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState
from app.agent.planner import planner
from app.agent.executor import step_executor
from app.agent.critic import critic
from app.services.llm_service import llm_service
from app.services.document_service import document_service
from app.prompts.router_prompt import get_router_system_prompt

logger = logging.getLogger("agent.workflow")

# --- 1. LANGGRAPH NODES ---

async def intent_router_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 0: Autonomous Intent Classifier.
    Uses LLM reasoning with ZERO hardcoded word lists to dynamically understand user intent
    and generate purely autonomous conversational replies.
    """
    logger.info("--- [LANGGRAPH NODE: INTENT ROUTER] ---")
    user_request = state["request"].strip()

    messages = [
        {"role": "system", "content": get_router_system_prompt()},
        {"role": "user", "content": f"User Input:\n{user_request}"}
    ]

    try:
        # LLM analyzes input, categorizes intent, and dynamically generates the conversational response
        classification = await llm_service.complete_json(messages=messages, max_tokens=250)
        intent = classification.get("intent", "document_generation")
        reply = classification.get("reply")
        reasoning = classification.get("reasoning", "")

        logger.info(f"Intent classified dynamically as '{intent}' by LLM. Reasoning: {reasoning}")

        if intent == "conversation":
            return {
                "intent": "conversation",
                "conversational_reply": reply,
                "logs": state.get("logs", []) + [f"Intent: conversation ({reasoning})"]
            }

        return {
            "intent": "document_generation",
            "logs": state.get("logs", []) + [f"Intent: document_generation ({reasoning})"]
        }

    except Exception as e:
        logger.warning(f"Intent classification error: {e}. Defaulting to document_generation.")
        return {
            "intent": "document_generation",
            "logs": state.get("logs", []) + [f"Intent router fallback to document_generation: {e}"]
        }

async def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: Analyzes request, formulates assumptions, and creates the dynamic plan.
    """
    logger.info("--- [LANGGRAPH NODE: PLANNER] ---")
    request = state["request"]
    plan = await planner.create_plan(request)
    return {
        "plan": plan,
        "logs": state.get("logs", []) + [f"Planned {len(plan.tasks)} tasks. (Ambiguous={plan.is_ambiguous})"]
    }

async def executor_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 2: Executes planned tasks using registered tools from ToolRegistry.
    """
    logger.info("--- [LANGGRAPH NODE: EXECUTOR] ---")
    plan = state["plan"]
    sections = await step_executor.execute_plan(plan)
    return {
        "sections": sections,
        "logs": state.get("logs", []) + [f"Synthesized {len(sections)} sections via ToolRegistry."]
    }

async def critic_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 3: Reflects and validates document quality against initial user intent.
    """
    logger.info("--- [LANGGRAPH NODE: CRITIC / REFLECTION] ---")
    request = state["request"]
    plan = state["plan"]
    sections = state["sections"]

    report = await critic.evaluate_document(
        user_request=request,
        plan=plan,
        sections=sections
    )
    return {
        "critique_passed": report.passed,
        "quality_score": report.quality_score,
        "reflection_notes": report.critique_notes,
        "logs": state.get("logs", []) + [f"Critic QA Passed={report.passed} (Score={report.quality_score}/10)"]
    }

async def document_builder_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 4: Compiles all synthesized sections into a polished .docx Word document.
    """
    logger.info("--- [LANGGRAPH NODE: DOCUMENT BUILDER] ---")
    plan = state["plan"]
    sections = state["sections"]

    doc_path = document_service.generate_docx(plan, sections)
    filename = os.path.basename(doc_path)

    return {
        "document_path": doc_path,
        "document_filename": filename,
        "logs": state.get("logs", []) + [f"Generated Word document: {filename}"]
    }

# --- 2. ROUTING LOGIC ---

def route_by_intent(state: AgentState) -> str:
    """Conditional edge decision: End early on conversation, or proceed to planning."""
    if state.get("intent") == "conversation":
        return "end_conversation"
    return "proceed_to_planner"

# --- 3. ASSEMBLE STATEGRAPH WORKFLOW ---

def create_agent_workflow():
    """
    Builds and compiles the production LangGraph state machine with conditional routing.
    """
    workflow = StateGraph(AgentState)

    # Register Nodes
    workflow.add_node("router", intent_router_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("document_builder", document_builder_node)

    # Establish Conditional Edge from Router
    workflow.add_edge(START, "router")
    workflow.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "end_conversation": END,
            "proceed_to_planner": "planner"
        }
    )

    # Linear execution pipeline for document generation
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "critic")
    workflow.add_edge("critic", "document_builder")
    workflow.add_edge("document_builder", END)

    # Compile the runnable graph
    compiled_graph = workflow.compile()
    logger.info("LangGraph Agent Workflow successfully compiled with autonomous LLM intent router.")
    return compiled_graph

agent_workflow = create_agent_workflow()
