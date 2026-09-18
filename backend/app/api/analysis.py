import logging
from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent.tools import execute_dataset_tool
from app.api.datasets import get_session, response
from app.datasets.models import Dataset
from app.db.session import engine
from app.llm.models import AnalysisJob, AnalysisRecord
from app.llm.openai_provider import get_llm_provider
from app.llm.provider import LLMConfigurationError, LLMProvider, LLMProviderError
from app.llm.schemas import AnalysisJobResponse, AnalysisRequest, AnalysisResponse, SavedAnalysis

router = APIRouter(prefix="/datasets", tags=["analysis"])
logger = logging.getLogger(__name__)


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


def job_response(job: AnalysisJob) -> AnalysisJobResponse:
    return AnalysisJobResponse(
        id=job.id, dataset_id=job.dataset_id, question=job.question, status=job.status,
        analysis_id=job.analysis_id, error=job.error, created_at=job.created_at,
    )


async def run_job(job_id: UUID, provider: LLMProvider | None) -> None:
    with Session(engine) as session:
        job = session.get(AnalysisJob, job_id)
        if job is None or provider is None:
            return
        dataset = session.get(Dataset, job.dataset_id)
        if dataset is None:
            job.status, job.error = "failed", "Датасет не найден"
            session.commit()
            return
        job.status = "running"
        session.commit()
        try:
            generated = None
            for attempt in range(2):
                try:
                    generated = await provider.analyze_dataset(
                        response(dataset), job.question,
                        lambda name, arguments: execute_dataset_tool(dataset, name, arguments),
                    )
                    break
                except LLMProviderError:
                    if attempt == 1:
                        raise
                    logger.warning("Analysis job %s failed; retrying provider request", job.id)
            if generated is None:
                raise LLMProviderError("Provider produced no result")
            result = AnalysisResponse(
                content=generated.content, provider=provider.provider_name, model=generated.model,
                usage=generated.usage, analysis_trace=generated.analysis_trace,
            )
            record = AnalysisRecord(
                dataset_id=dataset.id,
                question=job.question,
                response=result.model_dump(mode="json"),
            )
            session.add(record)
            session.flush()
            job.status, job.analysis_id = "completed", record.id
        except (LLMConfigurationError, LLMProviderError):
            job.status, job.error = "failed", "AI-провайдер временно недоступен"
        except SQLAlchemyError:
            job.status, job.error = "failed", "Не удалось сохранить анализ"
        session.commit()


@router.post(
    "/{dataset_id}/analysis-jobs", response_model=AnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_analysis_job(
    dataset_id: UUID,
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    provider: LLMProvider | None = Depends(get_llm_provider),
):
    if session.get(Dataset, dataset_id) is None:
        raise HTTPException(404, "Датасет не найден")
    if provider is None:
        raise HTTPException(503, "AI-провайдер не настроен")
    job = AnalysisJob(dataset_id=dataset_id, question=request.question, status="queued")
    session.add(job)
    session.flush()
    payload = job_response(job)
    session.commit()
    background_tasks.add_task(run_job, job.id, provider)
    return payload


@router.get("/analysis-jobs/{job_id}", response_model=AnalysisJobResponse)
def get_analysis_job(job_id: UUID, session: Session = Depends(get_session)) -> AnalysisJobResponse:
    job = session.get(AnalysisJob, job_id)
    if job is None:
        raise HTTPException(404, "Задача анализа не найдена")
    return job_response(job)


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
