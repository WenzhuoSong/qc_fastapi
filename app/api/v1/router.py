"""
API V1 路由聚合
"""

from fastapi import APIRouter

from app.api.v1.endpoints import allocation, holdings, decisions, health, transmission

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(allocation.router, prefix="/allocation", tags=["allocation"])
api_router.include_router(holdings.router, prefix="/holdings", tags=["holdings"])
api_router.include_router(decisions.router, prefix="/decisions", tags=["decisions"])
api_router.include_router(transmission.router, prefix="/transmission", tags=["transmission"])
