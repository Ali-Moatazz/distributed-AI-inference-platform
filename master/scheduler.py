import threading
import logging
import time

from common.models import WorkerInfo, WorkerStatus, Assignment

logger = logging.getLogger("MASTER")

# ==========================================
# HEARTBEAT CONFIG
# ==========================================

MONITOR_INTERVAL = 1
HEARTBEAT_TIMEOUT = 5  # seconds


class MasterNode:
    def __init__(self, worker_ids: list[int]):

        self.lock = threading.Lock()

        # ==========================================
        # WORKER STATE
        # ==========================================

        self.workers = {
            wid: WorkerInfo(id=wid)
            for wid in worker_ids
        }

        self.worker_index = 0

        # LAST HEARTBEAT TIME (IMPORTANT FIX)
        self.last_heartbeat = {
            wid: time.time() for wid in worker_ids
        }

        # worker load tracking
        self.worker_load = {
            wid: 0 for wid in worker_ids
        }

        # ==========================================
        # METRICS
        # ==========================================

        self.completed_requests = 0
        self.failed_requests = 0

        self.latencies = []

        self.start_time = time.time()

        self.request_start_time = {}

        # ==========================================
        # LB REFERENCE
        # ==========================================

        self.lb = None

        # ==========================================
        # START MONITOR THREAD
        # ==========================================

        threading.Thread(
            target=self._monitor,
            daemon=True
        ).start()

        logger.info(f"[MASTER] Started with workers: {worker_ids}")

    # =========================================================
    # ASSIGNMENT (ROUND ROBIN ONLY ACTIVE)
    # =========================================================
    def assign(self, request):

        with self.lock:

            active_workers = [
                w for w in self.workers.values()
                if w.status == WorkerStatus.ACTIVE
            ]

            if not active_workers:
                self.failed_requests += 1
                logger.error(f"[MASTER] No active workers for request {request.id}")
                return None

            chosen = active_workers[
                self.worker_index % len(active_workers)
            ]

            self.worker_index += 1

            self.worker_load[chosen.id] += 1
            self.request_start_time[request.id] = time.time()

        logger.info(f"[MASTER] Assigned request {request.id} → Worker {chosen.id}")

        return Assignment(request=request, worker_id=chosen.id)

    # =========================================================
    # COMPLETION TRACKING
    # =========================================================
    def release(self, worker_id, request_id=None):

        with self.lock:
            self.completed_requests += 1

            if worker_id in self.worker_load:
                self.worker_load[worker_id] = max(
                    0, self.worker_load[worker_id] - 1
                )

            if request_id in self.request_start_time:
                latency = time.time() - self.request_start_time[request_id]
                self.latencies.append(latency)
                del self.request_start_time[request_id]

        logger.info(f"[MASTER] Released Worker {worker_id}")

    # =========================================================
    # HEARTBEAT RECEIVER
    # =========================================================
    def record_heartbeat(self, worker_id):

        with self.lock:
            self.last_heartbeat[worker_id] = time.time()

            if self.workers[worker_id].status == WorkerStatus.FAILED:
                self.workers[worker_id].status = WorkerStatus.ACTIVE
                logger.info(f"[MASTER] Worker {worker_id} recovered")

                if self.lb:
                    self.lb.update_active_workers(self.get_active_workers())

    # =========================================================
    # FAILURE DETECTION (TIME-BASED FIXED)
    # =========================================================
    def _monitor(self):

        while True:
            time.sleep(MONITOR_INTERVAL)

            current_time = time.time()
            failed_workers = []

            with self.lock:

                for wid, worker in self.workers.items():

                    if worker.status == WorkerStatus.FAILED:
                        continue

                    last = self.last_heartbeat.get(wid, 0)

                    if current_time - last > HEARTBEAT_TIMEOUT:
                        worker.status = WorkerStatus.FAILED
                        failed_workers.append(wid)

            if failed_workers:
                logger.warning(f"[MASTER] Failed workers detected: {failed_workers}")

                if self.lb:
                    self.lb.update_active_workers(self.get_active_workers())

    # =========================================================
    # ACTIVE WORKERS
    # =========================================================
    def get_active_workers(self):

        with self.lock:
            return [
                wid for wid, w in self.workers.items()
                if w.status == WorkerStatus.ACTIVE
            ]

    # =========================================================
    # LINK LB
    # =========================================================
    def set_load_balancer(self, lb):
        self.lb = lb

    # =========================================================
    # METRICS
    # =========================================================
    def get_metrics(self):

        runtime = time.time() - self.start_time

        throughput = (
            self.completed_requests / runtime
            if runtime > 0 else 0
        )

        avg_latency = (
            sum(self.latencies) / len(self.latencies)
            if self.latencies else 0
        )

        with self.lock:
            active_workers = len(self.get_active_workers())

        return {
            "completed_requests": self.completed_requests,
            "failed_requests": self.failed_requests,
            "throughput_req_per_sec": throughput,
            "avg_latency_sec": avg_latency,
            "active_workers": active_workers,
            "worker_load": dict(self.worker_load)
        }