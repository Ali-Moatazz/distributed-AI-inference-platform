# master/scheduler.py
import time
import threading
import logging
from common.models import WorkerInfo, WorkerStatus, Assignment, Request
import psutil

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
    def __init__(self, worker_ids: list):
        self._lock = threading.RLock()
        
        # Allows up to 20 concurrent tasks in the system pipeline
        self.execution_gate = threading.Semaphore(20) 

        self._workers = {wid: WorkerInfo(id=wid, last_heartbeat=time.time()) for wid in worker_ids}
        self._rr_index = 0
        self._lb = None
        self._metrics = {
            "total_unique_requests": 0,
            "total_assignments": 0, 
            "failed_requests": 0, 
            "total_latency": 0.0, 
            "worker_assignments": {wid: 0 for wid in worker_ids}
        }
        self.start_time = time.time()
        
        # Start background monitor threads
        threading.Thread(target=self._performance_monitor, daemon=True, name="PerfMonitor").start()
        threading.Thread(target=self._heartbeat_monitor, daemon=True, name="HeartbeatMonitor").start()

    def log_unique_request(self):
        """Called exactly once per client dispatch."""
        with self._lock:
            self._metrics["total_unique_requests"] += 1    

    def assign(self, request: Request):
        # 1. Wait for a spot in the 'Waiting Room' (The Semaphore)
        self.execution_gate.acquire() 

        with self._lock:
            active = [w for w in self._workers.values() if w.status == WorkerStatus.ACTIVE]
            
            if not active:
                self.execution_gate.release() # Release if we can't do the work
                return None

            active_sorted = sorted(active, key=lambda w: w.id)
            chosen = active_sorted[self._rr_index % len(active_sorted)]
            self._rr_index += 1
            chosen.active_connections += 1
            
            # Update Metrics
            self._metrics["total_assignments"] += 1 
            #self._metrics["worker_assignments"][chosen.id] += 1
            
            return Assignment(request=request, worker_id=chosen.id)

    def release(self, worker_id: int, latency: float = 0.0, failed: bool = False):
        """
        Called when a task finishes. 
        If failed=True, the worker is marked FAILED immediately.
        """
        with self._lock:
            if worker_id in self._workers:
                w = self._workers[worker_id]
                w.active_connections = max(0, w.active_connections - 1)
                
                if failed:
                    w.status = WorkerStatus.FAILED
                    self._metrics["failed_requests"] += 1
                    logger.warning(f"Worker {worker_id} marked FAILED. Task will be reassigned.")
                    self._notify_lb()
                else:
                    self._metrics["total_latency"] += latency
                    self._metrics["worker_assignments"][worker_id] += 1
        
        # 2. Release the gate so the NEXT user can enter the pipeline
        self.execution_gate.release()

    def get_active_worker_ids(self) -> list:
        """Return sorted list of currently ACTIVE worker IDs."""
        with self._lock:
            return sorted(
                wid for wid, w in self._workers.items()
                if w.status == WorkerStatus.ACTIVE
            )

    def get_metrics(self) -> dict:
        with self._lock:
            # Note: We use unique_requests for the denominator to get the 'User Average'
            total = self._metrics["total_unique_requests"]
            avg_latency = (self._metrics["total_latency"] / total if total > 0 else 0.0)
            
            return {
                "total_users_served": total,
                "total_tasks_run": self._metrics["total_assignments"],
                "failed_nodes_detected": self._metrics["failed_requests"],
                "average_user_latency_s": round(avg_latency, 4),
                "worker_assignments": dict(self._metrics["worker_assignments"]),
                "worker_statuses": {wid: w.status.value for wid, w in self._workers.items()},
            }

    def set_load_balancer(self, lb):
        self._lb = lb

    def record_heartbeat(self, worker_id: int):
        now = time.time()
        #recovered = False
        with self._lock:
            if worker_id not in self._workers:
                return
            w = self._workers[worker_id]
            w.last_heartbeat = now
            #if w.status == WorkerStatus.FAILED:
             #   w.status = WorkerStatus.ACTIVE
              #  w.active_connections = 0
               # recovered = True

        #if recovered:
         #   logger.info(f"Worker {worker_id} RECOVERED — back in active pool")
          #  self._notify_lb()

    def _heartbeat_monitor(self):
        while True:
            time.sleep(MONITOR_INTERVAL)
            now = time.time()
            newly_failed = []
            with self._lock:
                for wid, w in self._workers.items():
                    if w.status == WorkerStatus.FAILED:
                        continue
                    if now - w.last_heartbeat > HEARTBEAT_TIMEOUT:
                        w.status = WorkerStatus.FAILED
                        w.active_connections = 0
                        newly_failed.append(wid)
            if newly_failed:
                for wid in newly_failed:
                    logger.warning(f"Worker {wid} FAILED — missed heartbeat")
                self._notify_lb()

    def _notify_lb(self):
        if self._lb is not None:
            active = self.get_active_worker_ids()
            self._lb.update_active_workers(active)

    def _performance_monitor(self):
        """Background thread to log real-time cluster utilization."""
        while True:
            time.sleep(5)
            with self._lock:
                active_ids = self.get_active_worker_ids()
                total_reqs = self._metrics["total_unique_requests"]
                elapsed = time.time() - self.start_time
                throughput = total_reqs / elapsed if elapsed > 0 else 0
                
                # Hardware monitoring
                cpu_usage = psutil.cpu_percent()
                ram_usage = psutil.virtual_memory().percent

                print("\n" + "-"*45)
                print(f"[MONITOR] Uptime: {int(elapsed)}s | Active Nodes: {len(active_ids)}")
                print(f"[MONITOR] Throughput: {throughput:.2f} req/sec")
                print(f"[MONITOR] System Load: CPU: {cpu_usage}% | RAM: {ram_usage}%")
                print("-"*45 + "\n")