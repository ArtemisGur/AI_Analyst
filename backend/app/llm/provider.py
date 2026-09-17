from dataclasses import dataclass
from typing import Protocol

from app.datasets.schemas import DatasetResponse
from app.llm.schemas import AnalysisContent, TokenUsage


class LLMConfigurationError(Exception):
    """Raised when the selected provider is not configured."""


class LLMProviderError(Exception):
    """Raised when a provider cannot return a valid response."""


@dataclass(frozen=True)
class GeneratedAnalysis:
    content: AnalysisContent
    model: str
    usage: TokenUsage


class LLMProvider(Protocol):
    provider_name: str

    async def analyze_dataset(
        self, dataset: DatasetResponse, question: str
    ) -> GeneratedAnalysis: ...
