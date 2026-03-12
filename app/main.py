"""
CrewAI + FastAPI Main Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Execute on startup
    import os
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    raw_token = os.environ.get("API_TOKEN", "")
    print(f"API_TOKEN from os.environ: '{raw_token[:5]}...' (length={len(raw_token)})")
    print(f"API_TOKEN from settings:   (length={len(settings.API_TOKEN)})")
    print(f"All env keys with 'TOKEN': {[k for k in os.environ if 'TOKEN' in k.upper()]}")
    yield
    # Execute on shutdown
    print("Application shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Intelligent Agent API Service based on CrewAI and FastAPI",
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
