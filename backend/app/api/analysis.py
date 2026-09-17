from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.datasets import get_session, response
from app.datasets.models import Dataset
from app.llm.openai_provider import get_llm_provider
from app.llm.provider import LLMConfigurationError, LLMProvider, LLMProviderError
from app.llm.schemas import AnalysisRequest, AnalysisResponse

router = APIRouter(prefix="/datasets", tags=["analysis"])


@router.post("/{dataset_id}/analysis", response_model=AnalysisResponse)
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
        generated = await provider.analyze_dataset(response(dataset), request.question)
    except LLMConfigurationError:
        raise HTTPException(503, "AI-провайдер не настроен") from None
    except LLMProviderError:
        raise HTTPException(502, "AI-провайдер временно недоступен") from None
    return AnalysisResponse(
        content=generated.content,
        provider=provider.provider_name,
        model=generated.model,
        usage=generated.usage,
    )
