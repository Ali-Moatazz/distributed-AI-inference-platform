# common/models.py
# ---------------------------------------------------------------------------
# Shared data layer — every component imports from here.
# This ensures all parts of the system "speak the same language".
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# WorkerStatus — the two states a worker can be in
# ---------------------------------------------------------------------------

class WorkerStatus(Enum):
    ACTIVE = "active"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# WorkerInfo — Master's internal record for each worker node
# ---------------------------------------------------------------------------

@dataclass
class WorkerInfo:
    id: int
    status: WorkerStatus = WorkerStatus.ACTIVE
    active_connections: int = 0        # tasks currently in progress
    last_heartbeat: float = 0.0        # Unix timestamp of last heartbeat


# ---------------------------------------------------------------------------
# Request — a client's incoming query
# ---------------------------------------------------------------------------

@dataclass
class Request:
    id: int
    query: str
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Response — what the system returns to the client
# ---------------------------------------------------------------------------

@dataclass
class Response:
    id: int
    result: str
    latency: float
    worker_id: int


# ---------------------------------------------------------------------------
# Assignment — Master's decision: which worker handles this request.
# The LB uses ONLY this — it never decides by itself.
# ---------------------------------------------------------------------------

@dataclass
class Assignment:
    request: Request
    worker_id: int