"""Versioned HTTP API for Delibra."""

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from verdictforge.arena import ArenaError
from verdictforge.schemas import (
    ArenaStats,
    DebateRecord,
    DebateRequest,
    HealthResponse,
    ModelSpec,
    PaginatedDebates,
)

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(request: Request) -> HealthResponse:
    services = request.app.state.services
    database_ok = await services.repository.is_healthy()
    available = len(services.providers.available_model_ids())
    return HealthResponse(
        status="ok" if database_ok and available >= 2 else "degraded",
        version=services.settings.app_version,
        environment=services.settings.environment,
        database="ok" if database_ok else "unavailable",
        available_models=available,
        api_key_required=bool(services.settings.api_key),
    )


@router.get("/models", response_model=list[ModelSpec], tags=["arena"])
async def models(request: Request) -> list[ModelSpec]:
    return list(request.app.state.services.providers.catalog.values())


@router.post(
    "/debates",
    response_model=DebateRecord,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["debates"],
)
async def create_debate(payload: DebateRequest, request: Request) -> DebateRecord:
    services = request.app.state.services
    if len(payload.question) > services.settings.max_question_length:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Question exceeds {services.settings.max_question_length} characters.",
        )
    try:
        return await services.debates.start(payload)
    except ArenaError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/debates", response_model=PaginatedDebates, tags=["debates"])
async def list_debates(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None, max_length=200),
) -> PaginatedDebates:
    return await request.app.state.services.repository.list_debates(
        limit=limit, offset=offset, query=query
    )


@router.get("/debates/{debate_id}", response_model=DebateRecord, tags=["debates"])
async def get_debate(debate_id: UUID, request: Request) -> DebateRecord:
    debate = await request.app.state.services.repository.get_debate(debate_id)
    if debate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debate not found.")
    return debate


@router.get("/debates/{debate_id}/export", tags=["debates"])
async def export_debate(
    debate_id: UUID,
    request: Request,
    format: str = Query(default="markdown", pattern="^(markdown|json)$"),
) -> Response:
    debate = await request.app.state.services.repository.get_debate(debate_id)
    if debate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debate not found.")
    filename = f"delibra-{debate_id}"
    if format == "json":
        content = json.dumps(debate.model_dump(mode="json"), indent=2)
        return Response(
            content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )
    content = _to_markdown(debate)
    return Response(
        content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
    )


@router.get("/stats", response_model=ArenaStats, tags=["arena"])
async def stats(request: Request) -> ArenaStats:
    services = request.app.state.services
    return await services.repository.get_stats(list(services.providers.catalog))


def _to_markdown(debate: DebateRecord) -> str:
    lines = [
        "# Delibra Debate",
        "",
        f"**Question:** {debate.question}",
        f"**Status:** {debate.status.value}",
        f"**Mode:** {debate.mode.value}",
        "",
    ]
    for answer in debate.answers:
        lines.extend([f"## {answer.model_id}", "", answer.content or f"_{answer.error}_", ""])
    if debate.judgment:
        lines.extend(["## Verdict", ""])
        for entry in debate.judgment.rankings:
            lines.append(
                f"{entry.rank}. **{entry.model_id}** — {entry.score:.1f}/100: {entry.verdict}"
            )
        lines.extend(["", debate.judgment.reasoning, ""])
    return "\n".join(lines)
