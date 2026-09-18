from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agent.charts import ChartSpec
from app.agent.python_sandbox import PythonResult
from app.agent.statistics import StatisticsResult


class AnalysisContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1_000)
    key_findings: list[str] = Field(min_length=1, max_length=5)
    evidence: list["FindingEvidence"] = Field(default_factory=list, max_length=5)
    limitations: list[str] = Field(max_length=3)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=1_000)


class TokenUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class FindingEvidence(BaseModel):
    """A user-visible link between a conclusion and verified tool steps."""

    finding_index: int = Field(ge=0, le=4)
    trace_step_indexes: list[int] = Field(min_length=1, max_length=3)


class AnalysisTraceStep(BaseModel):
    turn: int = Field(default=1, ge=1, le=5)
    tool: str
    summary: str
    arguments: dict[str, object] = Field(default_factory=dict)
    duration_ms: int = Field(default=0, ge=0)
    result_preview: str | None = Field(default=None, max_length=4_000)
    sql_query: str | None = Field(default=None, max_length=8000)
    status: Literal["completed", "failed"] = "completed"
    statistics: StatisticsResult | None = None
    python_code: str | None = Field(default=None, max_length=6000)
    python_result: PythonResult | None = None
    chart: ChartSpec | None = None


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
