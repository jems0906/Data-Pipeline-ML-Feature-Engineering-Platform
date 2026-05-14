from pathlib import Path
from typing import Iterable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from app.api.routes.features import router as feature_router
from app.api.routes.health import router as health_router
from app.api.routes.pipelines import router as pipeline_router
from app.core.config import settings
from app.db.session import Base, engine


def _iter_sql_statements(script: str) -> Iterable[str]:
    for chunk in script.split(";"):
        statement = chunk.strip()
        if statement:
            yield statement


def _apply_sql_bootstrap() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    init_sql = root_dir / "infra" / "sql" / "init.sql"
    if not init_sql.exists():
        return

    sql_script = init_sql.read_text(encoding="utf-8")
    with engine.begin() as conn:
        for statement in _iter_sql_statements(sql_script):
            conn.exec_driver_sql(statement)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    standalone_ui = Path(__file__).resolve().parents[2] / "frontend" / "standalone" / "index.html"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(pipeline_router, prefix=settings.api_prefix)
    app.include_router(feature_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui")

    @app.get("/ui", include_in_schema=False)
    def standalone_ui_page() -> FileResponse:
        return FileResponse(standalone_ui)

    @app.on_event("startup")
    def startup() -> None:
        Base.metadata.create_all(bind=engine)
        _apply_sql_bootstrap()
        for path in [settings.raw_dir, settings.processed_dir, settings.exports_dir, settings.metadata_dir]:
            Path(path).mkdir(parents=True, exist_ok=True)

    return app


app = create_app()
