from fastapi import FastAPI

from pipepulse import __version__
from pipepulse.routes import health, meta, metrics, pipelines, projects


def create_app() -> FastAPI:
    app = FastAPI(
        title="pipepulse",
        version=__version__,
        # Everything under /api, so a single ingress rule routes it.
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(pipelines.router)
    app.include_router(meta.router)
    app.include_router(metrics.router)
    return app


app = create_app()
