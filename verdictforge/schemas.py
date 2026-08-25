"""Validated domain contracts shared by the API, services, and persistence layer."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

TrimmedText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    """Base model that rejects accidental or misspelled input fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProviderName(StrEnum):
    GROQ = "groq"
    NVIDIA = "nvidia"


class DebateMode(StrEnum):
    DIRECT = "direct"
    DELIBERATE = "deliberate"


class DebateStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class AnswerStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class ModelSpec(StrictModel):
    id: str
    display_name: str
    provider: ProviderName
    model: str
    description: str
    accent: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    available: bool = False


class DebateRequest(StrictModel):
    question: TrimmedText = Field(max_length=12_000)
    model_ids: list[str] | None = None
    mode: DebateMode = DebateMode.DELIBERATE
    system_prompt: str | None = Field(default=None, max_length=4_000)

    @field_validator("model_ids")
    @classmethod
    def unique_model_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        unique = list(dict.fromkeys(value))
        if not 2 <= len(unique) <= 4:
            raise ValueError("select between 2 and 4 unique models")
        return unique


class Usage(StrictModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class AnswerResult(StrictModel):
    model_id: str
    content: str = ""
    status: AnswerStatus
    latency_ms: int = Field(ge=0)
    usage: Usage = Field(default_factory=Usage)
    error: str | None = None


class RankingEntry(StrictModel):
    model_id: str
    rank: int = Field(ge=1, le=4)
    score: float = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list, max_length=4)
    weaknesses: list[str] = Field(default_factory=list, max_length=4)
    verdict: str = ""


class Judgment(StrictModel):
    rankings: list[RankingEntry]
    reasoning: str
    judge_model: str

    @field_validator("rankings")
    @classmethod
    def ranks_are_unique(cls, value: list[RankingEntry]) -> list[RankingEntry]:
        ranks = [entry.rank for entry in value]
        model_ids = [entry.model_id for entry in value]
        if len(ranks) != len(set(ranks)) or len(model_ids) != len(set(model_ids)):
            raise ValueError("ranking entries must have unique ranks and models")
        return sorted(value, key=lambda entry: entry.rank)


class RatingSnapshot(StrictModel):
    model_id: str
    rating: float
    debates: int = Field(default=0, ge=0)
    wins: int = Field(default=0, ge=0)


class DebateRecord(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    question: str
    mode: DebateMode
    status: DebateStatus = DebateStatus.QUEUED
    answers: list[AnswerResult] = Field(default_factory=list)
    judgment: Judgment | None = None
    ratings: list[RatingSnapshot] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    error: str | None = None


class DebateSummary(StrictModel):
    id: UUID
    question: str
    mode: DebateMode
    status: DebateStatus
    winner_model_id: str | None = None
    created_at: datetime
    duration_ms: int | None = None


class PaginatedDebates(StrictModel):
    items: list[DebateSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class ArenaStats(StrictModel):
    total_debates: int = Field(ge=0)
    completed_debates: int = Field(ge=0)
    average_duration_ms: int = Field(ge=0)
    ratings: list[RatingSnapshot]


class HealthResponse(StrictModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: Literal["ok", "unavailable", "not_initialized"]
    available_models: int = Field(ge=0)

