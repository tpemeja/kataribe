from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kataribe import __version__
from kataribe.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="kataribe", version=__version__)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
