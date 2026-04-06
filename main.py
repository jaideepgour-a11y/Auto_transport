"""
Shivani Carriers - WhatsApp Driver Tracking
Main FastAPI application entry point
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import webhook_router
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initialising database...")
    await init_db()
    logger.info("Starting 6-hour follow-up scheduler...")
    scheduler_task = asyncio.create_task(start_scheduler())
    yield
    # Shutdown
    await stop_scheduler()
    scheduler_task.cancel()
    logger.info("Scheduler stopped.")


app = FastAPI(
    title="Shivani Carriers - Driver Tracking",
    description="WhatsApp-based driver tracking flow via Meta Cloud API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router, prefix="/webhook", tags=["WhatsApp Webhook"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "shivani-driver-tracking"}
