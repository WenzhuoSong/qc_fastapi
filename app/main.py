"""
Quant Agent Backend — FastAPI Delivery Gateway

This service is a lightweight read-only gateway. It queries PostgreSQL
for pre-computed allocation weights and returns them to QuantConnect.
All heavy LLM computation happens in the separate cron_pipeline.py.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.api.v1.router import api_router
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"API auth enabled: {bool(settings.API_TOKEN)}")
    print(f"Database configured: {bool(settings.DATABASE_URL)}")
    if settings.DATABASE_URL:
        try:
            init_db()
            print("Database tables initialized")
        except Exception as e:
            print(f"WARNING: Database init failed (app will still serve non-DB endpoints): {e}")
    yield
    print("Application shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Quant Agent API — lightweight delivery gateway for QuantConnect",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root path - Health check"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs_url": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
