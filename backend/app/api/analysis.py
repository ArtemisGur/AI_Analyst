from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent.tools import execute_dataset_tool
from app.api.datasets import get_session, response
from app.datasets.models import Dataset
from app.llm.models import AnalysisRecord
from app.llm.openai_provider import get_llm_provider
from app.llm.provider import LLMConfigurationError, LLMProvider, LLMProviderError
from app.llm.schemas import AnalysisRequest, AnalysisResponse, SavedAnalysis

router = APIRouter(prefix="/datasets", tags=["analysis"])


def saved_response(record: AnalysisRecord) -> SavedAnalysis:
    return SavedAnalysis(
        **record.response,
        id=record.id,
        dataset_id=record.dataset_id,
        question=record.question,
        created_at=record.created_at.replace(tzinfo=UTC)
        if record.created_at.tzinfo is None
        else record.created_at,
    )


@router.get("/{dataset_id}/analyses", response_model=list[SavedAnalysis])
def list_analyses(
    dataset_id: UUID,
    response: Response,
    session: Session = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    if session.get(Dataset, dataset_id) is None:
        raise HTTPException(404, "Датасет не найден")
    total = session.scalar(
        select(func.count())
        .select_from(AnalysisRecord)
        .where(AnalysisRecord.dataset_id == dataset_id)
    )
    response.headers["X-Total-Count"] = str(total or 0)
    query = (
        select(AnalysisRecord)
        .where(AnalysisRecord.dataset_id == dataset_id)
        .order_by(AnalysisRecord.created_at.desc(), AnalysisRecord.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [saved_response(record) for record in session.scalars(query)]


@router.post("/{dataset_id}/analysis", response_model=SavedAnalysis)
async def analyze_dataset(
    dataset_id: UUID,
    request: AnalysisRequest,
    session: Session = Depends(get_session),
    provider: LLMProvider | None = Depends(get_llm_provider),
) -> AnalysisResponse:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "Датасет не найден")
    if provider is None:
        raise HTTPException(503, "AI-провайдер не настроен")
    try:
        generated = await provider.analyze_dataset(
            response(dataset),
            request.question,
            lambda name, arguments: execute_dataset_tool(dataset, name, arguments),
        )
    except LLMConfigurationError:
        raise HTTPException(503, "AI-провайдер не настроен") from None
    except LLMProviderError:
        raise HTTPException(502, "AI-провайдер временно недоступен") from None
    result = AnalysisResponse(
        content=generated.content,
        provider=provider.provider_name,
        model=generated.model,
        usage=generated.usage,
        analysis_trace=generated.analysis_trace,
    )
    record = AnalysisRecord(
        dataset_id=dataset_id, question=request.question, response=result.model_dump(mode="json")
    )
    try:
        session.add(record)
        session.flush()
        saved = saved_response(record)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(503, "Не удалось сохранить анализ. Повторите попытку.") from None
    return saved
