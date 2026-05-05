# lb/load_balancer.py
# ---------------------------------------------------------------------------
# LOAD BALANCER — a dumb data-plane router. Zero intelligence.
#
# Responsibilities:
#   1. Receive a request from the client
#   2. Ask Master for an Assignment — LB never picks a worker itself
#   3. Forward the request to the assigned worker
#   4. Return the response to the client
#   5. Notify Master that the request is done (so Master can update load)
#   6. Accept worker-status updates FROM Master (passive awareness only)
#
# RULES (from spec):
#   - LB does NOT detect failures
#   - LB does NOT track heartbeats
#   - LB does NOT have scheduling logic
#   - LB does NOT do retries
#   - LB does NOT remove workers from the pool — that is Master's job
#   - LB updates its internal list ONLY when Master tells it to
# ---------------------------------------------------------------------------

import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LB] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("LoadBalancer")


class LoadBalancer:
    """
    Dumb pass-through router.
    All decisions come from Master. LB just moves data.
    """

    def __init__(self, master_node, workers: dict):
        """
        Parameters
        ----------
        master_node : MasterNode  — the ONLY decision-maker
        workers     : dict { worker_id (int) -> GPUWorker instance }
        """
        self._master  = master_node
        self._workers = workers

        # Passive awareness — updated ONLY by Master notifications
        self._lock = threading.Lock()
        self._active_ids: set = set(workers.keys())

        self._cache = {} 
        self._cache_lock = threading.Lock()

        logger.info(f"Ready. Worker pool: {sorted(workers.keys())}")

    # ====================================================================
    # MAIN DISPATCH — called by clients
    # ====================================================================

    def dispatch(self, request):
        """
        Full pipeline:
          1. Ask Master for assignment (Master picks the worker)
          2. Get the worker instance
          3. Send the request to the worker
          4. Tell Master the task is done
          5. Return response to client

        Returns a Response dict, or None if no workers are available.
        """

       # ── Step 1: check cache first ───────────────────────────────────────────
        with self._cache_lock:
            if request.query in self._cache:
                logger.info(f"[CACHE] Hit for query: '{request.query[:20]}...'")
                cached_response = self._cache[request.query]
                # Update the ID so it matches the current request
                cached_response.id = request.id 
                return cached_response
        # ── Step 2: Ask Master ───────────────────────────────────────────
        max_retries = 3
        for attempt in range(max_retries): 
            assignment = self._master.assign(request)
            if assignment is None:
                logger.error(
                    f"Request {request.id} dropped — Master returned no assignment"
                )
                return None

            worker_id = assignment.worker_id

            # ── Step 3: Get worker ───────────────────────────────────────────
            worker = self._workers.get(worker_id)
            if worker is None:
                logger.error(
                    f"Request {request.id} — worker {worker_id} not in registry"
                )
                self._master.release(worker_id)
                return None

        # ── Step 4: Forward to worker ────────────────────────────────────
            try:

                logger.info(f"Forwarding request {request.id} → Worker {worker_id}")
                response = worker.process(request)
                with self._cache_lock:
                    self._cache[request.query] = response

                # ── Step 4: Notify Master task is complete ───────────────────────
                self._master.release(worker_id, latency=response.latency)

                # ── Step 5: Return to client ─────────────────────────────────────
                return response
            except Exception as e:
                # 4. FAILURE: The worker crashed during the task!
                logger.warning(f"Worker {worker_id} FAILED during Request {request.id}. Reassigning...")
                
                # Notify master of the failure (so it can mark worker FAILED)
                # We release the semaphore slot but pass 0 latency
                self._master.release(worker_id, failed=True) 
                
                # The loop continues to 'attempt + 1' and gets a NEW worker from Master
                continue
        logger.error(f"Request {request.id} failed after {max_retries} attempts.")
        return None    

    # ====================================================================
    # MASTER NOTIFICATION — passive awareness update
    # ====================================================================

    def update_active_workers(self, active_ids: list):
        """
        Called by Master when a worker fails or recovers.
        LB updates its awareness list — it does NOT act on this itself.
        Master already stopped assigning the failed worker; LB just logs.
        """
        with self._lock:
            old = self._active_ids.copy()
            self._active_ids = set(active_ids)
            removed = old - self._active_ids
            added   = self._active_ids - old

        if removed:
            logger.warning(
                f"Notified by Master: workers removed from pool → {removed}"
            )
        if added:
            logger.info(
                f"Notified by Master: workers recovered into pool → {added}"
            )