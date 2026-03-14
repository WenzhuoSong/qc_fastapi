"""
API V1 路由聚合
"""

from fastapi import APIRouter

from app.api.v1.endpoints import allocation, crew, health, tasks

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(allocation.router, prefix="/allocation", tags=["allocation"])
api_router.include_router(crew.router, prefix="/crew", tags=["crew"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
