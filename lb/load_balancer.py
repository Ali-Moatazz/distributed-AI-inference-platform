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

from copy import copy
import logging
import string
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
        master_node : MasterNode instance
        workers     : dict { worker_id -> GPUWorker instance }
        """
        self._master  = master_node
        self._workers = workers

        # Passive awareness of cluster state
        self._lock = threading.Lock()
        self._active_ids: set = set(workers.keys())

        # Thread-safe Cache
        self._cache = {} 
        self._cache_lock = threading.Lock()
        
        # Words to strip to find the "Meaning" of the question
        self._stop_words = {
            'what', 'is', 'how', 'the', 'tell', 'me', 'about', 'explain', 
            'describe', 'please', 'a', 'an', 'are', 'do', 'we', 'in', 'this'
        }

        logger.info(f"Ready. Worker pool: {sorted(workers.keys())}")

    def _generate_cache_key(self, query: str) -> str:
        """
        Normalizes query: 'What is load balancing?' -> 'balancing,load'
        Ensures same meaning results in same cache key.
        """
        # 1. Lowercase and remove punctuation
        clean = query.lower().translate(str.maketrans('', '', string.punctuation))
        
        # 2. Filter out noise words, keep only significant keywords
        words = [w for w in clean.split() if w not in self._stop_words and len(w) > 2]
        
        # 3. Sort alphabetically so word order doesn't matter
        words.sort()
        
        # 4. Join as key
        return ",".join(words)

    def dispatch(self, request):
        # ──  Count the unique user intent  ──
        self._master.log_unique_request()

        # 1. Semantic Cache Lookup
        cache_key = self._generate_cache_key(request.query)
        with self._cache_lock:
            if cache_key in self._cache:
                self._master.log_cache_hit()
                logger.info(f"[CACHE] Hit for query: {request.query}")
                cached_resp = copy(self._cache[cache_key])
                cached_resp.worker_id = "CACHE" 
                cached_resp.id = request.id
                # Note: No master.release() needed because it never called assign()
                return cached_resp

        # 2. Request Distribution with Retry Logic
        max_retries = 3
        for attempt in range(max_retries):
            assignment = self._master.assign(request)
            if assignment is None: return None

            worker_id = assignment.worker_id
            worker = self._workers.get(worker_id)

            try:
                response = worker.process(request)
                with self._cache_lock:
                    self._cache[cache_key] = response
                
                # Success: Release the worker and record latency
                self._master.release(worker_id, latency=response.latency)
                return response

            except Exception as e:
                logger.warning(f"Reassigning Request {request.id}...")
                # Notify Master of failure
                self._master.release(worker_id, failed=True) 
            
                continue
        return None 

    # ====================================================================
    # MASTER NOTIFICATION — passive awareness update
    # ====================================================================

    def update_active_workers(self, active_ids: list):
        """Called by Master to update LB's passive awareness."""
        with self._lock:
            old = self._active_ids.copy()
            self._active_ids = set(active_ids)
            removed = old - self._active_ids
            added   = self._active_ids - old

        if removed:
            logger.warning(f"Master Alert: Workers disconnected -> {removed}")
        if added:
            logger.info(f"Master Alert: Workers recovered -> {added}")