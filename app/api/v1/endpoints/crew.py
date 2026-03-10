"""
CrewAI Agent Related API Endpoints
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio

from app.services.crew_service import CrewService

router = APIRouter()


class AgentRequest(BaseModel):
    """Agent execution request"""
    topic: str
    agents_config: Optional[List[Dict[str, Any]]] = None
    tasks_config: Optional[List[Dict[str, Any]]] = None


class AgentResponse(BaseModel):
    """Agent execution response"""
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


class CrewInfoResponse(BaseModel):
    """Crew info response"""
    name: str
    description: str
    agents: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]


@router.post("/execute", response_model=AgentResponse)
async def execute_crew(request: AgentRequest):
    """
    Execute CrewAI agent team task
    
    - **topic**: Task topic/objective
    - **agents_config**: Optional custom agent configuration
    - **tasks_config**: Optional custom task configuration
    """
    try:
        crew_service = CrewService()
        
        # Run crew
        result = await crew_service.run_crew(
            topic=request.topic,
            agents_config=request.agents_config,
            tasks_config=request.tasks_config,
        )
        
        return AgentResponse(
            success=True,
            result=result.get("output"),
            execution_time=result.get("execution_time"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/async")
async def execute_crew_async(
    request: AgentRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute CrewAI agent team task asynchronously
    
    Task will run in background, returns task ID immediately
    """
    # Task queue mechanism can be implemented here
    return {
        "task_id": "temp-task-id",
        "status": "queued",
        "message": "Task has been queued",
    }


@router.get("/info", response_model=CrewInfoResponse)
async def get_crew_info():
    """Get default Crew configuration information"""
    crew_service = CrewService()
    return crew_service.get_default_crew_info()


@router.get("/agents")
async def list_agents():
    """List available agent types"""
    return {
        "agents": [
            {
                "role": "Researcher",
                "goal": "Conduct in-depth research on specified topics",
                "backstory": "Experienced researcher skilled in information gathering and analysis",
            },
            {
                "role": "Writer",
                "goal": "Write high-quality content",
                "backstory": "Professional writer skilled at transforming complex information into accessible content",
            },
            {
                "role": "Editor",
                "goal": "Review and improve content quality",
                "backstory": "Senior editor ensuring content accuracy and readability",
            },
        ]
    }
