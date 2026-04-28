# master/scheduler.py
# ---------------------------------------------------------------------------
# MASTER NODE — the ONLY intelligent component in the system.
#
# Responsibilities:
#   1. Track every worker: status, load, last heartbeat timestamp
#   2. Run a background monitor thread that checks heartbeat timeouts
#      → marks workers FAILED when they miss too many beats
#      → marks workers ACTIVE again if they recover
#      → notifies the LB whenever the active pool changes
#   3. Assign requests ONLY to ACTIVE workers (Round Robin or Least-Conn)
#   4. Release a worker's load counter when a request finishes
#   5. Collect system metrics (total requests, failures, latency)
#
# RULES (from spec):
#   - Master is the SINGLE SOURCE OF TRUTH for worker health
#   - Master NEVER assigns a FAILED worker
#   - LB never detects failures — Master notifies LB
# ---------------------------------------------------------------------------

import time
import threading
import logging
from common.models import WorkerInfo, WorkerStatus, Assignment, Request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Master] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Master")

# Heartbeat config
HEARTBEAT_TIMEOUT  = 3.0   # seconds without heartbeat → FAILED
MONITOR_INTERVAL   = 1.0   # how often the monitor thread checks


class MasterNode:
    """
    Control-plane brain of the system.
    All scheduling decisions, health tracking, and metrics live here.
    """

    def __init__(self, worker_ids: list):
        self._lock = threading.Lock()

        # ── Worker registry ──────────────────────────────────────────────
        now = time.time()
        self._workers: dict = {
            wid: WorkerInfo(id=wid, last_heartbeat=now)
            for wid in worker_ids
        }

        # Round-robin cursor (index into sorted active worker list)
        self._rr_index: int = 0

        # ── LB reference (set later to break circular dependency) ────────
        self._lb = None

        # ── Metrics ──────────────────────────────────────────────────────
        self._metrics = {
            "total_requests":    0,
            "failed_requests":   0,
            "total_latency":     0.0,
            "worker_assignments": {wid: 0 for wid in worker_ids},
        }

        # ── Background health monitor ────────────────────────────────────
        self._monitor_thread = threading.Thread(
            target=self._heartbeat_monitor, daemon=True, name="MasterMonitor"
        )
        self._monitor_thread.start()

        logger.info(f"Started with workers: {worker_ids}")

    # ====================================================================
    # PUBLIC API — used by LB
    # ====================================================================

    def assign(self, request: Request):
        """
        Choose an ACTIVE worker for this request using Round Robin.
        Returns an Assignment, or None if no workers are available.

        This is the ONLY place where worker selection happens.
        """
        with self._lock:
            active = [
                w for w in self._workers.values()
                if w.status == WorkerStatus.ACTIVE
            ]

        if not active:
            logger.warning(
                f"Request {request.id} — no active workers available"
            )
            with self._lock:
                self._metrics["failed_requests"] += 1
            return None

        # Round Robin over the sorted active list (stable ordering)
        active_sorted = sorted(active, key=lambda w: w.id)
        with self._lock:
            chosen = active_sorted[self._rr_index % len(active_sorted)]
            self._rr_index += 1
            chosen.active_connections += 1
            self._metrics["total_requests"] += 1
            self._metrics["worker_assignments"][chosen.id] = (
                self._metrics["worker_assignments"].get(chosen.id, 0) + 1
            )

        logger.info(
            f"Assigned request {request.id} → Worker {chosen.id} "
            f"(active_conn={chosen.active_connections})"
        )
        return Assignment(request=request, worker_id=chosen.id)

    def release(self, worker_id: int, latency: float = 0.0):
        """
        Called by LB after a worker finishes a request.
        Decrements the worker's load counter and records latency.
        """
        with self._lock:
            if worker_id in self._workers:
                w = self._workers[worker_id]
                w.active_connections = max(0, w.active_connections - 1)
            self._metrics["total_latency"] += latency

    def get_active_worker_ids(self) -> list:
        """Return sorted list of currently ACTIVE worker IDs."""
        with self._lock:
            return sorted(
                wid for wid, w in self._workers.items()
                if w.status == WorkerStatus.ACTIVE
            )

    def get_metrics(self) -> dict:
        """Return a snapshot of current system metrics."""
        with self._lock:
            total = self._metrics["total_requests"]
            avg_latency = (
                self._metrics["total_latency"] / total if total > 0 else 0.0
            )
            return {
                "total_requests":     total,
                "failed_requests":    self._metrics["failed_requests"],
                "average_latency_s":  round(avg_latency, 4),
                "worker_assignments": dict(self._metrics["worker_assignments"]),
                "worker_statuses":    {
                    wid: w.status.value
                    for wid, w in self._workers.items()
                },
            }

    def set_load_balancer(self, lb):
        """Wire the LB in after construction (avoids circular imports)."""
        self._lb = lb

    # ====================================================================
    # HEARTBEAT API — called by Workers
    # ====================================================================

    def record_heartbeat(self, worker_id: int):
        """
        Worker calls this periodically to prove it is alive.
        Master updates the last_heartbeat timestamp.
        If the worker was previously FAILED, it is recovered here.
        """
        now = time.time()
        recovered = False

        with self._lock:
            if worker_id not in self._workers:
                return
            w = self._workers[worker_id]
            w.last_heartbeat = now

            if w.status == WorkerStatus.FAILED:
                w.status = WorkerStatus.ACTIVE
                w.active_connections = 0
                recovered = True

        if recovered:
            logger.info(f"Worker {worker_id} RECOVERED — back in active pool")
            self._notify_lb()

    # ====================================================================
    # BACKGROUND MONITOR — heartbeat timeout detection
    # ====================================================================

    def _heartbeat_monitor(self):
        """
        Runs forever in a daemon thread.
        Every MONITOR_INTERVAL seconds it checks every ACTIVE worker:
          - if now - last_heartbeat > HEARTBEAT_TIMEOUT → mark FAILED
          - notify LB of the updated active pool
        This is the ONLY failure detection mechanism (per spec).
        """
        while True:
            time.sleep(MONITOR_INTERVAL)
            now = time.time()
            newly_failed = []

            with self._lock:
                for wid, w in self._workers.items():
                    if w.status == WorkerStatus.FAILED:
                        continue   # already known bad
                    if now - w.last_heartbeat > HEARTBEAT_TIMEOUT:
                        w.status = WorkerStatus.FAILED
                        w.active_connections = 0
                        newly_failed.append(wid)

            for wid in newly_failed:
                logger.warning(
                    f"Worker {wid} FAILED — missed heartbeat for "
                    f">{HEARTBEAT_TIMEOUT}s"
                )

            if newly_failed:
                self._notify_lb()

    def _notify_lb(self):
        """Push updated active-worker list to LB whenever health changes."""
        if self._lb is not None:
            active = self.get_active_worker_ids()
            logger.info(f"Notifying LB — active workers now: {active}")
            self._lb.update_active_workers(active)