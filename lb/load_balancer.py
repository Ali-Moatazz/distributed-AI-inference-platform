import logging

logger = logging.getLogger("LB")


class LoadBalancer:
    def __init__(self, master_node, workers: dict):
        """
        Load Balancer (DATA PLANE ONLY)

        Responsibilities:
        - Receive requests from clients
        - Ask Master for worker assignment
        - Dispatch request to assigned worker
        - Return responses back to clients
        - Receive worker-pool updates from Master

        IMPORTANT:
        - LB contains NO scheduling logic
        - LB contains NO failure detection logic
        - LB does NOT decide worker health
        """

        self.master = master_node
        self.workers = workers

        # Pure synchronization copy from Master
        self.active_workers = set(workers.keys())

        logger.info(f"[LB] Initialized with workers: {list(workers.keys())}")

    # =========================================================
    # CLIENT ENTRY POINT
    # =========================================================
    def dispatch(self, request):
        """
        Request Flow:
        Client → LB → Master → Worker → LB → Client
        """

        logger.info(f"[LB] Received request {request.id}")

        # -------------------------------------------------
        # Step 1: Ask Master for assignment
        # -------------------------------------------------
        assignment = self.master.assign(request)

        if assignment is None:
            logger.error(f"[LB] No worker available for request {request.id}")
            return None

        worker_id = assignment.worker_id

        # -------------------------------------------------
        # Step 2: Get worker instance
        # -------------------------------------------------
        worker = self.workers.get(worker_id)

        if worker is None:
            logger.error(f"[LB] Worker {worker_id} not found")
            return None

        logger.info(f"[LB] Dispatching request {request.id} → Worker {worker_id}")

        # -------------------------------------------------
        # Step 3: Execute request
        # -------------------------------------------------
        try:
            response = worker.process(request)

        except Exception as e:
            # IMPORTANT:
            # LB does NOT decide failure state.
            # Master detects failure independently using heartbeat monitoring.
            logger.error(
                f"[LB] Execution error on Worker {worker_id}: {e}"
            )
            return None

        # -------------------------------------------------
        # Step 4: Notify Master request completed
        # -------------------------------------------------
        self.master.release(worker_id, request.id)

        return response

    # =========================================================
    # CONTROL PLANE UPDATE (MASTER → LB)
    # =========================================================
    def update_active_workers(self, active_ids):
        """
        Master synchronizes active worker pool with LB.

        LB does NOT decide worker health.
        It only mirrors Master's view.
        """

        old_workers = self.active_workers.copy()

        self.active_workers = set(active_ids)

        removed = old_workers - self.active_workers
        added = self.active_workers - old_workers

        if removed:
            logger.warning(f"[LB] Removed failed workers: {removed}")

        if added:
            logger.info(f"[LB] Added recovered workers: {added}")

        logger.info(
            f"[LB] Active worker pool updated: "
            f"{self.active_workers}"
        )