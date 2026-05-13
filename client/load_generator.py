# client/load_generator.py
# ---------------------------------------------------------------------------
# CLIENT LOAD GENERATOR — simulates concurrent users.
#
# Clients know ONLY about the Load Balancer.
# They have zero knowledge of Master, workers, or assignments.
# ---------------------------------------------------------------------------

import threading
import logging
from common.models import Request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Client] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Client")


def simulate_user(load_balancer, user_id: int):
    """A single user sends one request and logs the response."""
    request = Request(id=user_id, query=f"Query TASKID{user_id}")
    response = load_balancer.dispatch(request)

    if response:
        logger.info(
            f"[User {user_id}] ✓ Worker {response.worker_id} | "
            f"Latency: {response.latency:.3f}s | Result: {response.result[:40]}..."
        )
    else:
        logger.warning(f"[User {user_id}] ✗ No response (all workers down?)")


def run_load_test(load_balancer, num_users: int = 1000):
    """Spawn num_users threads, each simulating one concurrent user."""
    threads = []
    for i in range(num_users):
        t = threading.Thread(
            target=simulate_user,
            args=(load_balancer, i),
            daemon=True,
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    logger.info(f"Load test complete — {num_users} users processed.")