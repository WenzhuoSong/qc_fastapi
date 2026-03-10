"""
Health Check Endpoints
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "crewai-fastapi",
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check"""
    return {
        "ready": True,
        "checks": {
            "api": "ok",
        },
    }
