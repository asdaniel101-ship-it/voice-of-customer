import logging
from contextlib import asynccontextmanager
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("signalgraph").setLevel(logging.INFO)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from signalgraph.api.briefs import router as briefs_router
from signalgraph.api.companies import router as companies_router
from signalgraph.api.health import router as health_router
from signalgraph.api.mentions import router as mentions_router
from signalgraph.api.themes import router as themes_router
from signalgraph.scheduler import get_scheduler

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from signalgraph.database import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add website column to existing companies table if missing
        from sqlalchemy import inspect, text

        def _migrate(connection):
            inspector = inspect(connection)
            if "companies" in inspector.get_table_names():
                cols = [c["name"] for c in inspector.get_columns("companies")]
                if "website" not in cols:
                    connection.execute(text("ALTER TABLE companies ADD COLUMN website VARCHAR(512)"))

        await conn.run_sync(_migrate)

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

    @app.get("/")
    async def serve_dashboard():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
