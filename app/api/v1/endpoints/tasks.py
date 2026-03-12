"""
Task Management API Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime

from app.models.schemas import TaskCreateRequest, TaskResponse
from app.core.security import verify_token

router = APIRouter()

# In-memory task storage (use database in production)
tasks_db: dict = {}


@router.post("/", response_model=TaskResponse)
async def create_task(request: TaskCreateRequest, _token: str = Depends(verify_token)):
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
async def list_tasks(_token: str = Depends(verify_token)):
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
async def get_task(task_id: str, _token: str = Depends(verify_token)):
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
async def delete_task(task_id: str, _token: str = Depends(verify_token)):
    """Delete task"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")

    del tasks_db[task_id]
    return {"message": "Task deleted"}
