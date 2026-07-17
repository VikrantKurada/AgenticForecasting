from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db, make_engine, make_session_factory
from app.routers import chats, projects


def create_app(session_factory=None) -> FastAPI:
    if session_factory is None:
        engine = make_engine()
        init_db(engine)
        session_factory = make_session_factory(engine)

    app = FastAPI(title="Agentic Forecasting", version="0.1.0")
    app.state.session_factory = session_factory
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
    return app
