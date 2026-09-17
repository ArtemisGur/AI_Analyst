from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from app.agent.tools import ExecutedTool
from app.datasets.schemas import DatasetResponse
from app.llm.schemas import AnalysisContent, AnalysisTraceStep, TokenUsage


class LLMConfigurationError(Exception):
    """Raised when the selected provider is not configured."""


class LLMProviderError(Exception):
    """Raised when a provider cannot return a valid response."""


@dataclass(frozen=True)
class GeneratedAnalysis:
    content: AnalysisContent
    model: str
    usage: TokenUsage
    analysis_trace: list[AnalysisTraceStep] = field(default_factory=list)


class LLMProvider(Protocol):
    provider_name: str

    async def analyze_dataset(
        self,
        dataset: DatasetResponse,
        question: str,
        execute_tool: Callable[[str, str], ExecutedTool] | None = None,
    ) -> GeneratedAnalysis: ...
