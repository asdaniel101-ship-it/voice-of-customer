from contextlib import asynccontextmanager

from fastapi import FastAPI

from signalgraph.api.briefs import router as briefs_router
from signalgraph.api.companies import router as companies_router
from signalgraph.api.health import router as health_router
from signalgraph.api.mentions import router as mentions_router
from signalgraph.api.themes import router as themes_router
from signalgraph.scheduler import get_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = get_scheduler()
    try:
        scheduler.start()
    except Exception:
        pass
    yield
    try:
        scheduler.shutdown()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(title="SignalGraph", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(companies_router)
    app.include_router(mentions_router)
    app.include_router(briefs_router)
    app.include_router(themes_router)
    return app


app = create_app()
