from fastapi import FastAPI

from pipepulse import __version__
from pipepulse.routes import health


def create_app() -> FastAPI:
    app = FastAPI(title="pipepulse", version=__version__, docs_url="/api/docs")
    app.include_router(health.router)
    return app


app = create_app()
