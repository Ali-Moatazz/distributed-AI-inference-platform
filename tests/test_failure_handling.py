# tests/test_failure_handling.py

from lb.load_balancer import LoadBalancer
from master.scheduler import MasterNode
from workers.gpu_worker import GPUWorker

from common.models import Request

import threading
import time
import logging


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s"
)

logger = logging.getLogger("TEST")


# =========================================================
# FAILURE HANDLING TEST
# =========================================================

def test_failure_handling():

    print("\n===== FAILURE HANDLING TEST =====\n")

    # -------------------------------------------------
    # STEP 1: CREATE WORKERS
    # -------------------------------------------------

    workers = {
        i: GPUWorker(worker_id=i)
        for i in range(3)
    }

    # -------------------------------------------------
    # STEP 2: CREATE MASTER
    # -------------------------------------------------

    master = MasterNode(
        worker_ids=list(workers.keys())
    )

    # -------------------------------------------------
    # STEP 3: CREATE LOAD BALANCER
    # -------------------------------------------------

    lb = LoadBalancer(
        master_node=master,
        workers=workers
    )

    # -------------------------------------------------
    # STEP 4: CONNECT MASTER ↔ LB
    # -------------------------------------------------

    master.set_load_balancer(lb)

    # -------------------------------------------------
    # STEP 5: CONNECT WORKERS → MASTER
    # -------------------------------------------------

    for worker in workers.values():

        worker._master = master

        # restart heartbeat thread
        worker.start_heartbeats()

    # -------------------------------------------------
    # STEP 6: SIMULATE FAILURE
    # -------------------------------------------------

    def fail_worker():

        # let worker run initially
        time.sleep(3)

        print("\n🔥 Worker 1 STOPPED HEARTBEATS\n")

        # stops heartbeat thread
        workers[1].shutdown()

    threading.Thread(
        target=fail_worker,
        daemon=True
    ).start()

    # -------------------------------------------------
    # STEP 7: SEND REQUESTS
    # -------------------------------------------------

    for i in range(15):

        request = Request(
            id=i,
            query=f"Distributed systems query {i}"
        )

        response = lb.dispatch(request)

        if response:
            print(
                f"[CLIENT] Request {i} handled by "
                f"Worker {response['worker_id']}"
            )

        else:
            print(
                f"[CLIENT] Request {i} failed"
            )

        time.sleep(0.5)

    # -------------------------------------------------
    # STEP 8: FINAL STATUS
    # -------------------------------------------------

    print("\n===== FINAL STATUS =====")

    print(
        f"Active Workers: "
        f"{master.get_active_workers()}"
    )

    print("\n===== METRICS =====")

    metrics = master.get_metrics()

    for key, value in metrics.items():
        print(f"{key}: {value}")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    test_failure_handling()