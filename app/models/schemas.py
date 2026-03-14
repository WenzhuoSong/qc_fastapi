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
    defense_level: str = "full"
    risk_flags: Dict[str, List[str]] = {}
    regime: Optional[str] = None
    message: Optional[str] = None


# ── Decision Log (review + backfill) ─────────────────────────────────

class DecisionLogResponse(BaseModel):
    date: str
    qc_regime: Optional[str] = None
    ai_regime: Optional[str] = None
    regime_override: Optional[bool] = None
    confidence: Optional[int] = None
    defense_level: Optional[str] = None
    final_weights: Optional[Dict[str, float]] = None
    reasoning: Optional[str] = None
    market_outcome: Optional[str] = None
    decision_correct: Optional[bool] = None


class DecisionLogUpdate(BaseModel):
    """For backfilling post-hoc analysis fields."""
    market_outcome: Optional[str] = None
    decision_correct: Optional[bool] = None


# ── Holdings (QC 10:00 ET Snapshot) ──────────────────────────────────

class HoldingsRequest(BaseModel):
    """Payload from QuantConnect reporting current positions."""
    current_holdings: List[str]
    qc_regime: Optional[str] = None
    account_dd: Optional[float] = None


class HoldingsResponse(BaseModel):
    status: str
    message: str
