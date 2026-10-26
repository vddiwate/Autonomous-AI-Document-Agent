from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict
from app.models.schemas import Plan, DocumentSection

class AgentState(TypedDict, total=False):
    """
    Central state tracked throughout the LangGraph workflow execution.
    """
    # Original user prompt
    request: str
    
    # Intent Classification ('conversation' or 'document_generation')
    intent: str
    conversational_reply: Optional[str]
    
    # Generated plan & tasks
    plan: Optional[Plan]
    
    # Executed document sections
    sections: List[DocumentSection]
    
    # Reflection & Critique state
    reflection_notes: Optional[str]
    critique_passed: bool
    quality_score: float
    
    # Final Output Document
    document_path: Optional[str]
    document_filename: Optional[str]
    
    # Execution logs & status
    logs: List[str]
    error: Optional[str]
