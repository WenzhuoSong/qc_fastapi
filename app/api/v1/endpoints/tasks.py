"""
Task Management API Endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

router = APIRouter()

# In-memory task storage (use database in production)
tasks_db = {}


class TaskCreateRequest(BaseModel):
    """Create task request"""
    name: str
    description: str
    agent_role: str
    expected_output: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    """Task response"""
    id: str
    name: str
    description: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[str] = None


@router.post("/", response_model=TaskResponse)
async def create_task(request: TaskCreateRequest):
    """Create new task"""
    task_id = f"task_{len(tasks_db) + 1}"
    
    task = {
        "id": task_id,
        "name": request.name,
        "description": request.description,
        "agent_role": request.agent_role,
        "expected_output": request.expected_output,
        "context": request.context,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "result": None,
    }
    
    tasks_db[task_id] = task
    
    return TaskResponse(
        id=task_id,
        name=task["name"],
        description=task["description"],
        status=task["status"],
        created_at=task["created_at"],
    )


@router.get("/", response_model=List[TaskResponse])
async def list_tasks():
    """List all tasks"""
    return [
        TaskResponse(
            id=task["id"],
            name=task["name"],
            description=task["description"],
            status=task["status"],
            created_at=task["created_at"],
            completed_at=task.get("completed_at"),
            result=task.get("result"),
        )
        for task in tasks_db.values()
    ]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get task details"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks_db[task_id]
    return TaskResponse(
        id=task["id"],
        name=task["name"],
        description=task["description"],
        status=task["status"],
        created_at=task["created_at"],
        completed_at=task.get("completed_at"),
        result=task.get("result"),
    )


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete task"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del tasks_db[task_id]
    return {"message": "Task deleted"}
