from fastapi import FastAPI

from signalgraph.api.companies import router as companies_router
from signalgraph.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="SignalGraph", version="0.1.0")
    app.include_router(health_router)
    app.include_router(companies_router)
    return app


app = create_app()
