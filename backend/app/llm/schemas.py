from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalysisContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1_000)
    key_findings: list[str] = Field(min_length=1, max_length=5)
    limitations: list[str] = Field(max_length=3)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=1_000)


class TokenUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class AnalysisTraceStep(BaseModel):
    tool: str
    summary: str


class AnalysisResponse(BaseModel):
    content: AnalysisContent
    provider: str
    model: str
    usage: TokenUsage
    analysis_trace: list[AnalysisTraceStep] = Field(default_factory=list, max_length=5)


class SavedAnalysis(AnalysisResponse):
    id: UUID
    dataset_id: UUID
    question: str
    created_at: datetime
