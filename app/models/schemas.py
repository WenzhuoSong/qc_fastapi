"""
Centralized Pydantic Schemas

All request / response models in one place so they are easy to find,
reuse, and keep consistent across endpoints.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


# ── Crew ─────────────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    topic: str
    agents_config: Optional[List[Dict[str, Any]]] = None
    tasks_config: Optional[List[Dict[str, Any]]] = None


class AgentResponse(BaseModel):
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


class CrewInfoResponse(BaseModel):
    name: str
    description: str
    agents: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]


# ── Task Management ──────────────────────────────────────────────────

class TaskCreateRequest(BaseModel):
    name: str
    description: str
    agent_role: str
    expected_output: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[str] = None


# ── Allocation (V3.1 Chronos) ───────────────────────────────────────

class AllocationResponse(BaseModel):
    """Response returned to QuantConnect for portfolio rebalancing."""
    date: str
    status: str
    is_stale: bool
    weights: Dict[str, float]
    message: Optional[str] = None


# ── Holdings (QC 10:00 ET Snapshot) ──────────────────────────────────

class HoldingsRequest(BaseModel):
    """Payload from QuantConnect reporting current positions."""
    current_holdings: List[str]
    qc_regime: Optional[str] = None
    account_dd: Optional[float] = None


class HoldingsResponse(BaseModel):
    status: str
    message: str
