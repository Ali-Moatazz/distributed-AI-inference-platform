# main.py
# ---------------------------------------------------------------------------
# Entry point — wires all components together and runs the load test.
#
# Wiring order matters:
#   1. Create workers (no master yet — avoids circular dep)
#   2. Create Master (knows worker IDs, not LB yet)
#   3. Create LB (knows Master + worker objects)
#   4. Wire LB → Master (so Master can push failure notifications)
#   5. Wire Master → Workers (so workers can send heartbeats)
# ---------------------------------------------------------------------------

import sys
import time
import threading
import logging
from workers.gpu_worker import GPUWorker
from master.scheduler import MasterNode
from lb.load_balancer import LoadBalancer
from client.load_generator import run_load_test

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Main] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Main")


def main():
    NUM_WORKERS = 4
    NUM_USERS   = 100   # increase to 1000 for full load test

    # ── 1. Create workers (master not yet wired) ─────────────────────────
    worker_ids   = list(range(NUM_WORKERS))
    workers_dict = {wid: GPUWorker(worker_id=wid) for wid in worker_ids}

    # ── 2. Create Master ─────────────────────────────────────────────────
    master = MasterNode(worker_ids=worker_ids)

    # ── 3. Create LB ─────────────────────────────────────────────────────
    lb = LoadBalancer(master_node=master, workers=workers_dict)

    # ── 4. Wire LB into Master ────────────────────────────────────────────
    master.set_load_balancer(lb)

    # ── 5. Wire Master into Workers and (re)start heartbeat threads ───────
    for worker in workers_dict.values():
        worker.set_master(master)
        # Restart heartbeat now that master is wired
        worker._alive = True
        worker._start_heartbeat_thread()

    logger.info("=" * 60)
    logger.info(f"System ready. Workers: {worker_ids}")
    logger.info("=" * 60)

    # ── Optional: simulate Worker 1 failing 1 second into the test ───────
    def fail_worker(delay: float, wid: int):
        time.sleep(delay)
        logger.warning(f"[FaultSim] Shutting down Worker {wid}")
        workers_dict[wid].shutdown()

    threading.Thread(
        target=fail_worker, args=(1.0, 1), daemon=True
    ).start()

    # ── Run load test ─────────────────────────────────────────────────────
    # ── Run Demo & Load Test ──────────────────────────────────────────────
    start_time = time.time()
    
    # --- PART A: REAL AI DEMO (Testing Supabase + LLM) ---
    logger.info(">>> STARTING REAL AI DEMO QUESTIONS")
    from common.models import Request
    
    demo_questions = [
        "What is load balancing in this system?",
        "How do we handle fault tolerance?",
        "What is a distributed AI cluster?",
        "Tell me about RAG.",
        "Describe the Role of AI in our life"
    ]

    for i, q_text in enumerate(demo_questions):
        print(f"\n[USER {i}] Asking: {q_text}")
        req = Request(id=i, query=q_text)
        
        # This goes: LB -> Master -> Worker -> Supabase -> LLM
        response = lb.dispatch(req) 
        
        if response:
            print(f"--- ANSWER FROM WORKER {response.worker_id} ---")
            print(f"RESULT: {response.result}")
            print(f"LATENCY: {response.latency:.2f}s")
        else:
            print("!!! Request failed (No workers available)")

    # --- PART B: STRESS TEST (Optional) ---
    # After the demo, you can run the massive load test.
    # Note: If you use Real AI for 100 users, it will take ~5-10 minutes.
    logger.info(">>> STARTING CONCURRENT LOAD TEST")
    run_load_test(lb, num_users=20) # Start with 20 to be safe
    print("\n[Main] Load test finished. Cooling down for 2s...")
    time.sleep(2) 

    # ── Print final metrics ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("FINAL SYSTEM METRICS")
    print("=" * 60)
    
    metrics = master.get_metrics()
    print(f"  Total Requests:    {metrics['total_requests']}")
    print(f"  Failed Requests:   {metrics['failed_requests']}")
    print(f"  Avg Latency:       {metrics['average_latency_s']}s")
    
    print("\n  Worker Assignments:")
    for wid, count in metrics['worker_assignments'].items():
        status = metrics['worker_statuses'].get(wid, "UNKNOWN")
        print(f"    - Worker {wid}: {count} tasks (Status: {status})")
    
    print("=" * 60)

    total_time = time.time() - start_time
    print(f"Test Duration: {total_time:.2f} seconds")
    print(f"Throughput: {metrics['total_requests']/total_time:.2f} req/sec")
    print("=" * 60)

    sys.stdout.flush()

if __name__ == "__main__":
    main()