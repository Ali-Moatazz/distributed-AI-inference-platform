from dataclasses import dataclass
from enum import Enum


# =========================
# WORKER STATUS
# =========================
class WorkerStatus(Enum):
    ACTIVE = "active"
    FAILED = "failed"


# =========================
# REQUEST / RESPONSE
# =========================
@dataclass
class Request:
    id: int
    query: str


@dataclass
class Response:
    id: int
    result: str
    latency: float
    worker_id: int


# =========================
# MASTER → LB COMMUNICATION
# =========================
@dataclass
class Assignment:
    request: Request
    worker_id: int


# =========================
# WORKER METADATA (IMPORTANT)
# =========================
@dataclass
class WorkerInfo:
    id: int
    status: WorkerStatus = WorkerStatus.ACTIVE
    active_connections: int = 0