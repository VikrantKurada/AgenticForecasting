from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.engine.events import RunEventBus
from app.connectors.registry import build_connectors
from app.db import init_db, make_engine, make_session_factory
from app.llm.builder import build_registry
from app.memory.integrations import build_memory_backend
from app.routers import (
    chat,
    chats,
    datasources,
    integrations,
    projects,
    providers,
    telemetry,
)


def create_app(
    session_factory=None, llm_registry=None, connectors=None, run_inline: bool = False
) -> FastAPI:
    if session_factory is None:
        engine = make_engine()
        init_db(engine)
        session_factory = make_session_factory(engine)

    app = FastAPI(title="Agentic Forecasting", version="0.1.0")
    app.state.session_factory = session_factory
    app.state.llm_registry = llm_registry or build_registry(session_factory)
    app.state.connectors = connectors or build_connectors(session_factory)
    app.state.memory_backend = build_memory_backend(session_factory)
    app.state.run_bus = RunEventBus()
    app.state.run_inline = run_inline
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(projects.router)
    app.include_router(chats.router)
    app.include_router(providers.router)
    app.include_router(datasources.router)
    app.include_router(integrations.router)
    app.include_router(chat.router)
    app.include_router(telemetry.router)
    return app
