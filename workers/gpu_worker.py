import time
import threading
import logging

from llm.inference import run_llm
from rag.retriever import retrieve_context

logger = logging.getLogger("WORKER")

# =========================================================
# HEARTBEAT CONFIG
# =========================================================

HEARTBEAT_INTERVAL = 1.5


class GPUWorker:
    def __init__(self, worker_id, master_node=None):
        """
        GPU Worker Node

        Responsibilities:
        - Execute RAG retrieval
        - Execute LLM inference
        - Send periodic heartbeats to Master
        - Simulate worker failure/recovery
        """

        self.id = worker_id

        # Reference to Master Node
        self.master = master_node

        # Worker state
        self.alive = True

        logger.info(f"[Worker {self.id}] started")

        # Start heartbeat thread ONLY if master exists
        if self.master is not None:
            self.start_heartbeats()

    # =========================================================
    # REQUEST PROCESSING
    # =========================================================
    def process(self, request):
        """
        Execute AI inference pipeline:
        RAG → LLM
        """

        start = time.time()

        logger.info(
            f"[Worker {self.id}] Processing request {request.id}"
        )

        # -------------------------------------------------
        # Step 1: Retrieve context (RAG)
        # -------------------------------------------------

        context = retrieve_context(request.query)

        # -------------------------------------------------
        # Step 2: Run LLM inference
        # -------------------------------------------------

        result = run_llm(request.query, context)

        # -------------------------------------------------
        # Step 3: Compute latency
        # -------------------------------------------------

        latency = time.time() - start

        logger.info(
            f"[Worker {self.id}] Completed request "
            f"{request.id} in {latency:.3f}s"
        )

        return {
            "id": request.id,
            "worker_id": self.id,
            "result": result,
            "latency": latency
        }

    # =========================================================
    # HEARTBEAT LOOP
    # =========================================================
    def _heartbeat_loop(self):
        """
        Periodically notify Master that this worker is alive.
        """

        while self.alive:

            if self.master is not None:
                self.master.record_heartbeat(self.id)

            time.sleep(HEARTBEAT_INTERVAL)

    # =========================================================
    # START HEARTBEATS
    # =========================================================
    def start_heartbeats(self):
        """
        Start background heartbeat thread.
        """

        threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        ).start()

        logger.info(
            f"[Worker {self.id}] Heartbeat thread started"
        )

    # =========================================================
    # FAILURE SIMULATION
    # =========================================================
    def shutdown(self):
        """
        Simulate worker/node failure
        by stopping heartbeat transmission.
        """

        self.alive = False

        logger.warning(
            f"[Worker {self.id}] STOPPED HEARTBEATS"
        )

    # =========================================================
    # RECOVERY SIMULATION (OPTIONAL)
    # =========================================================
    def recover(self):
        """
        Simulate worker recovery.
        """

        if not self.alive:

            self.alive = True

            logger.info(
                f"[Worker {self.id}] RECOVERED"
            )

            self.start_heartbeats()