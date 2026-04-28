# tests/test_round_robin.py
# ---------------------------------------------------------------------------
# TEST: Round Robin assignment distribution
#
# Validates:
#   1. With N workers and N requests, each worker gets exactly 1 request
#   2. With 2N requests, each worker gets exactly 2 requests
#   3. Assignment order follows the Round Robin cycle (0→1→2→0→1→2→...)
#   4. Master's worker_assignments metric reflects the fair distribution
# ---------------------------------------------------------------------------

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
from workers.gpu_worker import GPUWorker
from master.scheduler import MasterNode
from lb.load_balancer import LoadBalancer
from common.models import Request


def build_system(num_workers: int = 3):
    worker_ids   = list(range(num_workers))
    workers_dict = {wid: GPUWorker(worker_id=wid) for wid in worker_ids}
    master       = MasterNode(worker_ids=worker_ids)
    lb           = LoadBalancer(master_node=master, workers=workers_dict)
    master.set_load_balancer(lb)
    for w in workers_dict.values():
        w.set_master(master)
        w._alive = True
        w._start_heartbeat_thread()
    time.sleep(0.3)
    return lb, master, workers_dict


# ── Test 1: One full cycle — each worker gets exactly 1 request ──────────────

def test_one_cycle_each_worker_gets_one_request():
    lb, master, _ = build_system(num_workers=3)
    worker_hits = {0: 0, 1: 0, 2: 0}

    for i in range(3):
        resp = lb.dispatch(Request(id=i, query=f"Q{i}"))
        worker_hits[resp.worker_id] += 1

    for wid, count in worker_hits.items():
        assert count == 1, f"Worker {wid} expected 1 hit, got {count}"

    print(f"  ✓ Distribution after 3 requests: {worker_hits}")


# ── Test 2: Two full cycles — each worker gets exactly 2 requests ─────────────

def test_two_cycles_each_worker_gets_two_requests():
    lb, master, _ = build_system(num_workers=3)
    worker_hits = {0: 0, 1: 0, 2: 0}

    for i in range(6):
        resp = lb.dispatch(Request(id=i, query=f"Q{i}"))
        worker_hits[resp.worker_id] += 1

    for wid, count in worker_hits.items():
        assert count == 2, f"Worker {wid} expected 2 hits, got {count}"

    print(f"  ✓ Distribution after 6 requests: {worker_hits}")


# ── Test 3: Explicit Round Robin order ───────────────────────────────────────
#
# With 3 workers [0, 1, 2] the assignment sequence must be:
#   request 0 → worker 0
#   request 1 → worker 1
#   request 2 → worker 2
#   request 3 → worker 0  (wraps)
#   request 4 → worker 1
#   request 5 → worker 2

def test_round_robin_order():
    _, master, _ = build_system(num_workers=3)

    assigned_workers = []
    for i in range(6):
        assignment = master.assign(Request(id=i, query=f"Q{i}"))
        assert assignment is not None
        assigned_workers.append(assignment.worker_id)
        # Immediately release so connections don't accumulate
        master.release(assignment.worker_id)

    expected = [0, 1, 2, 0, 1, 2]
    assert assigned_workers == expected, (
        f"Expected RR order {expected}, got {assigned_workers}"
    )
    print(f"  ✓ Round Robin order correct: {assigned_workers}")


# ── Test 4: Master metrics reflect fair distribution ─────────────────────────

def test_metrics_reflect_fair_distribution():
    lb, master, _ = build_system(num_workers=4)

    for i in range(8):
        lb.dispatch(Request(id=i, query=f"Q{i}"))

    metrics = master.get_metrics()
    assignments = metrics["worker_assignments"]

    for wid in range(4):
        assert assignments[wid] == 2, (
            f"Worker {wid} expected 2 assignments, got {assignments[wid]}"
        )

    print(f"  ✓ Metrics distribution: {assignments}")


# ── Test 5: RR skips a worker with 0 active workers in pool ─────────────────
#  (edge case: if only 1 worker is active, all requests go to it)

def test_all_requests_go_to_only_active_worker():
    _, master, workers_dict = build_system(num_workers=3)

    # Manually shut down workers 1 and 2
    workers_dict[1].shutdown()
    workers_dict[2].shutdown()
    # Wait for Master to detect failures (HEARTBEAT_TIMEOUT = 6s)
    # Instead of waiting, use Master's record to simulate:
    from common.models import WorkerStatus
    with master._lock:
        master._workers[1].status = WorkerStatus.FAILED
        master._workers[2].status = WorkerStatus.FAILED

    for i in range(4):
        assignment = master.assign(Request(id=i, query=f"Q{i}"))
        assert assignment is not None
        assert assignment.worker_id == 0, (
            f"Expected only Worker 0, got Worker {assignment.worker_id}"
        )
        master.release(0)

    print(f"  ✓ All requests correctly routed to the single active worker (0)")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_one_cycle_each_worker_gets_one_request,
        test_two_cycles_each_worker_gets_two_requests,
        test_round_robin_order,
        test_metrics_reflect_fair_distribution,
        test_all_requests_go_to_only_active_worker,
    ]
    print("\n" + "=" * 55)
    print("  TEST SUITE: Round Robin Assignment")
    print("=" * 55)
    passed = failed = 0
    for test in tests:
        try:
            print(f"\n▶ {test.__name__}")
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ ERROR: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'=' * 55}")
    print(f"  Result: {passed} passed, {failed} failed")
    print("=" * 55)