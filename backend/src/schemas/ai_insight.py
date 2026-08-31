"""Exact reporting facts are serialized as decimal strings, never binary floats."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AnomalySignal(StrictModel):
    code: str
    severity: Literal['INFO', 'WARNING', 'CRITICAL']
    description: str
    metric_reference: str


class ProviderMetadata(StrictModel):
    provider: str
    cached: bool = False
    latency_ms: int = 0
    tokens_used: int = 0
    fallback_reason: str | None = None


class NarrativeOutput(StrictModel):
    headline: str = Field(max_length=300)
    factual_metrics: dict[str, Decimal | None]
    analytical_narrative: str = Field(max_length=5000)
    actionable_recommendations: list[str]


class AIInsightResponse(NarrativeOutput):
    organization_id: UUID
    period_label: str
    as_of_date: date
    data_as_of: date
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence_score: Literal['HIGH', 'MEDIUM', 'LOW']
    confidence_category: Literal['HIGH', 'MEDIUM', 'LOW']
    source_references: list[str]
    metric_sources: dict[str, str]
    unavailable_metrics: list[str]
    anomalies_detected: list[AnomalySignal] = Field(default_factory=list)
    provider_metadata: ProviderMetadata


class FinancialQAQueryRequest(StrictModel):
    query_text: str = Field(min_length=1, max_length=1000)
    session_id: UUID | None = None
    project_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None


class FinancialQAQueryResponse(StrictModel):
    session_id: UUID
    answer_text: str
    classified_intent: str
    source_references: list[str]
    confidence_score: Literal['HIGH', 'MEDIUM', 'LOW']
    insight: AIInsightResponse | None = None
