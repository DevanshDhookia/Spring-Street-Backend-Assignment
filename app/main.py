from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.admin import holdings as admin_holdings
from app.api.admin import pipeline as admin_pipeline
from app.api.public import exposures, factsheet, growth, holdings, nav, performance, products
from app.config import settings
from app.pipeline.runner import run_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the daily pipeline scheduler on app startup; shut it down cleanly on exit
    scheduler = BackgroundScheduler(timezone=settings.pipeline_timezone)
    scheduler.add_job(
        run_pipeline,
        CronTrigger.from_crontab(settings.pipeline_cron),
        id="full_pipeline",
        kwargs={"triggered_by": "scheduler"},
        misfire_grace_time=3600,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Prisma Factsheet API",
    description="Daily-batch factsheet system for Spring Street Prisma products",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public endpoints
app.include_router(products.router)
app.include_router(factsheet.router)
app.include_router(nav.router)
app.include_router(holdings.router)
app.include_router(exposures.router)
app.include_router(performance.router)
app.include_router(growth.router)

# Admin endpoints (require X-Admin-Token header)
app.include_router(admin_holdings.router)
app.include_router(admin_pipeline.router)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(Path(__file__).parent.parent / "frontend" / "index.html")
