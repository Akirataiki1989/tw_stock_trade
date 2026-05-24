import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AnalyzeRequest(BaseModel):
    symbols: list[str]
    mode: str = "full"


class AnalyzeResponse(BaseModel):
    session_id: uuid.UUID
    status: str  # "running" | "completed" | "failed"


class AiDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: uuid.UUID
    analysis: Optional[str] = None
    decisions: Optional[Any] = None
    market_summary: Optional[str] = None
    model_used: Optional[str] = None
    tokens_used: int
    execution_ms: int
    agent_reports: Optional[Any] = None
    created_at: datetime
