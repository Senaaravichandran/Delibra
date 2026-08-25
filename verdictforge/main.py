"""FastAPI application factory and command-line entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from verdictforge.api import router
from verdictforge.arena import DebateEngine
from verdictforge.config import Settings, get_settings
from verdictforge.judging import BlindJudge
from verdictforge.middleware import ProductionMiddleware
from verdictforge.providers import ProviderRegistry
from verdictforge.repository import DebateRepository
from verdictforge.service import DebateService


@dataclass(slots=True)
class AppServices:
    settings: Settings
    providers: ProviderRegistry
    repository: DebateRepository
    debates: DebateService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    providers = ProviderRegistry(settings)
    repository = DebateRepository(settings.database_path)
    engine = DebateEngine(providers, settings)
    judge = BlindJudge(providers, settings)
    debates = DebateService(engine, judge, repository)
    services = AppServices(settings, providers, repository, debates)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        await repository.initialize()
        application.state.services = services
        yield
        await debates.shutdown()
        await providers.close()

    application = FastAPI(
        title="VerdictForge API",
        summary="Multi-model deliberation, blind judging, and persistent ratings.",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
    )
    application.add_middleware(ProductionMiddleware, settings=settings)
    application.include_router(router)
    web_directory = Path(__file__).parent / "web"
    application.mount("/", StaticFiles(directory=web_directory, html=True), name="web")
    return application


app = create_app()


def run() -> None:
    """Run the development server from the installed console command."""

    uvicorn.run("verdictforge.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
