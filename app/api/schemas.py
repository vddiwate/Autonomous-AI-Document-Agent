from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from app.models.schemas import Plan

class AgentRequest(BaseModel):
    """
    Incoming user request schema.
    Fully dynamic: accepts any natural language input (greetings, questions, or document requests).
    """
    request: str = Field(..., description="Natural language input for the autonomous agent")

class DocumentMetadata(BaseModel):
    """Generated document details and download location."""
    filename: str
    download_url: str
    file_size_bytes: int

class CriticReviewSummary(BaseModel):
    """Quality and reflection review summary."""
    passed: bool
    notes: str

class AgentResponse(BaseModel):
    """
    Structured response returned by POST /agent.
    Dynamically handles both conversational messages and full document generation outputs.
    """
    status: str = Field(default="success")
    intent: str = Field(..., description="'conversation' for greetings/chat or 'document_generation' for document requests")
    message: str = Field(..., description="Conversational reply or executive document summary")
    execution_time_seconds: float
    plan: Optional[Plan] = None
    critic_review: Optional[CriticReviewSummary] = None
    document: Optional[DocumentMetadata] = None

class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    app_name: str
    version: str
    configured_model: str
