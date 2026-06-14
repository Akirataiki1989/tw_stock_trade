"""app/api/ai.py — AI 分析觸發與決策歷史查詢。"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.portfolio import AiDecision
from app.models.user import User
from app.schemas.ai import AiDecisionRead, AnalyzeRequest, AnalyzeResponse
from app.users import current_active_user

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze", response_model=list[AnalyzeResponse])
async def analyze(
    req: AnalyzeRequest,
    request: Request,
    user: User = Depends(current_active_user),
):
    """觸發指定標的的 AI 分析。每個標的獨立一個 session_id，非同步在 worker 執行。"""
    arq_pool = request.app.state.arq
    responses = []
    for symbol in req.symbols:
        session_id = uuid.uuid4()
        await arq_pool.enqueue_job(
            "task_run_ai_on_demand",
            str(user.id),
            symbol.upper(),
            str(session_id),
        )
        responses.append(AnalyzeResponse(session_id=session_id, status="running"))
    return responses


@router.get("/decisions", response_model=list[AiDecisionRead])
async def list_decisions(
    limit: int = Query(20, ge=1, le=100),
    symbol: Optional[str] = Query(None, description="篩選特定標的（decisions JSONB key）"),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查詢目前使用者的 AI 決策歷史，依時間倒序。"""
    stmt = (
        select(AiDecision)
        .where(AiDecision.user_id == user.id)
        .order_by(desc(AiDecision.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    decisions = result.scalars().all()

    if symbol:
        sym = symbol.upper()
        decisions = [d for d in decisions if d.decisions and sym in d.decisions]

    return decisions


@router.get("/decisions/{session_id}", response_model=AiDecisionRead)
async def get_decision(
    session_id: uuid.UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """查詢單筆 AI 決策（含完整 agent_reports）。"""
    stmt = select(AiDecision).where(
        AiDecision.session_id == session_id,
        AiDecision.user_id == user.id,
    )
    result = await db.execute(stmt)
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision
