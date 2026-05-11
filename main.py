# main.py
import os
from dotenv import load_dotenv
load_dotenv() # Load .env before anything else

import time
import threading
import logging
import sys
from workers.gpu_worker import GPUWorker
from master.scheduler import MasterNode
from lb.load_balancer import LoadBalancer
from client.load_generator import run_load_test
from common.models import Request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Main")

def main():
    NUM_WORKERS = 4
    TOTAL_TARGET_USERS = 1000
    DEMO_COUNT = 100

    # ── 1. Initialization ────────────────────────────────────────────────
    worker_ids = list(range(NUM_WORKERS))
    workers_dict = {wid: GPUWorker(worker_id=wid) for wid in worker_ids}
    master = MasterNode(worker_ids=worker_ids)
    lb = LoadBalancer(master_node=master, workers=workers_dict)
    master.set_load_balancer(lb)

    for worker in workers_dict.values():
        worker.set_master(master)
        worker._alive = True
        worker._start_heartbeat_thread()

    logger.info("=" * 60)
    logger.info("SYSTEM ONLINE: PREPARING 1000 REQUEST VALIDATION")
    logger.info("=" * 60)

    start_time = time.time()

    # ── 2. Phase 1: 100 Demo Questions (Including Cache Hits) ────────────
    # We use a mix of unique and repeat questions to test Cache and RAG
    base_queries = [
        "What is load balancing?",
        "Explain fault tolerance.",
        "Tell me about RAG.",
        "What is a distributed system?",
        "How do heartbeats work?"
    ]

    print(f"\n>>> STARTING PHASE 1: {DEMO_COUNT} DEMO REQUESTS")
    for i in range(DEMO_COUNT):
        # Every 2nd and 3rd request is a repeat to trigger CACHE
        query_text = base_queries[i % len(base_queries)]
        
        # Note: Worker 1 is programmed to fail mid-task during its 2nd job
        # Since we use 4 workers, Worker 1 will get Request 1 and Request 5.
        # Request 5 should trigger the 'Auto-Reassignment' logic.
        
        resp = lb.dispatch(Request(id=i, query=query_text))
        
        if i < 10: # Only print the first few to keep terminal clean
            if resp:
                print(f"[User {i}] DONE | Worker: {resp.worker_id} | Latency: {resp.latency:.2f}s")
        elif i == 10:
            print("... (Demo continuing silently) ...")

    # ── 3. Phase 2: 900 Concurrent Users (Load Test) ─────────────────────
    REMAINING = TOTAL_TARGET_USERS - DEMO_COUNT
    print(f"\n>>> STARTING PHASE 2: {REMAINING} CONCURRENT USERS")
    run_load_test(lb, num_users=REMAINING)

    # ── 4. Final Cleanup & Metrics ───────────────────────────────────────
    print("\n[Main] Finalizing metrics... Cooling down 2s.")
    time.sleep(2)
    sys.stdout.flush()

    metrics = master.get_metrics()
    
    print("\n" + "█" * 60)
    print("             FINAL SYSTEM METRICS (1000 USERS)           ")
    print("█" * 60)
    print(f"  Total Unique Users Served:   {metrics['total_users_served']}")
    print(f"  Total Worker Tasks Run:      {metrics['total_tasks_run']}")
    print(f"  Failed Nodes Detected:       {metrics['failed_nodes_detected']}")
    print(f"  Average System Latency:      {metrics['average_user_latency_s']}s")
    
    print("\n  Node Distribution Stats:")
    for wid, count in metrics['worker_assignments'].items():
        status = metrics['worker_statuses'].get(wid, "UNKNOWN")
        print(f"    - Worker {wid}: {count} tasks successfully handled (Status: {status})")
    
    total_time = time.time() - start_time
    print("-" * 60)
    print(f"  Total Wall-Clock Time:   {total_time:.2f} seconds")
    print(f"  System Throughput:       {metrics['total_users_served']/total_time:.2f} users/sec")
    print("█" * 60)

if __name__ == "__main__":
    main()