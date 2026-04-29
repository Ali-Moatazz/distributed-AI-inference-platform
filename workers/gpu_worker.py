# workers/gpu_worker.py
# ---------------------------------------------------------------------------
# GPU WORKER NODE — dumb execution layer.
#
# Responsibilities:
#   1. Process a request: run RAG retrieval + LLM inference, return Response
#   2. Send heartbeats to Master at a fixed interval to prove it is alive
#   3. Support shutdown() to simulate a node failure (stops heartbeats)
#
# RULES (from spec):
#   - Workers do NOT know about other workers
#   - Workers do NOT make routing decisions
#   - Workers do NOT talk to the LB directly
#   - Workers do NOT manage system state
# ---------------------------------------------------------------------------

import time
import threading
import logging
from common.models import Request, Response
from llm.inference import run_llm
from rag.retriever import retrieve_context

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)

# Workers send a heartbeat every HEARTBEAT_INTERVAL seconds.
# Must be shorter than Master's HEARTBEAT_TIMEOUT (6s) so workers
# are never falsely marked failed under normal operation.
HEARTBEAT_INTERVAL = 1.5


class GPUWorker:
    """
    Stateless executor.
    Knows only: how to process a request and how to prove it is alive.
    """

    def __init__(self, worker_id: int, master_node=None):
        """
        Parameters
        ----------
        worker_id   : unique integer identifier
        master_node : MasterNode — used only for sending heartbeats.
                      Can be set later via set_master().
        """
        self.id       = worker_id
        self._master  = master_node
        self._alive   = True
        self._logger  = logging.getLogger(f"Worker-{worker_id}")

        self._start_heartbeat_thread()
        self._logger.info(f"Worker {self.id} online")

    # ====================================================================
    # CORE EXECUTION
    # ====================================================================

    def process(self, request: Request) -> Response:
        """
        Execute the full pipeline for a single request:
          1. RAG: retrieve relevant context from knowledge base
          2. LLM: run inference with context
          3. Return a Response with timing info
        """

        if not self._alive:
            self._logger.error(f"Worker {self.id} received request while DOWN!")
            raise RuntimeError("Node is unreachable") 
        
        start = time.time()
        self._logger.info(f"Processing request {request.id}")

        # RAG step
        self._logger.info(f"Step 1: Starting RAG (Supabase) for Request {request.id}")
        context = retrieve_context(request.query)
        self._logger.info(f"Step 1: RAG Complete for Request {request.id}")


        # LLM inference step
        self._logger.info(f"Step 2: Queuing for LLM Brain - Request {request.id}") 
        result = run_llm(request.query, context)

        latency = time.time() - start
        self._logger.info(
            f"Finished request {request.id} in {latency:.3f}s"
        )

        return Response(
            id=request.id,
            result=result,
            latency=latency,
            worker_id=self.id,
        )

    # ====================================================================
    # HEARTBEAT
    # ====================================================================

    def set_master(self, master_node):
        """Wire in the Master after construction (breaks circular dep)."""
        self._master = master_node

    def shutdown(self):
        """
        Stop sending heartbeats — simulates a crashed/unreachable node.
        Master will detect the timeout and mark this worker FAILED.
        """
        self._alive = False
        self._logger.warning(f"Worker {self.id} shutting down (heartbeats stopped)")

    def _send_heartbeats(self):
        """
        Background loop: tell Master this worker is alive.
        Stops when _alive is False (i.e., shutdown() was called).
        """
        while self._alive:
            if self._master is not None:
                self._master.record_heartbeat(self.id)
            time.sleep(HEARTBEAT_INTERVAL)

    def _start_heartbeat_thread(self):
        t = threading.Thread(
            target=self._send_heartbeats,
            daemon=True,
            name=f"Heartbeat-{self.id}",
        )
        t.start()
