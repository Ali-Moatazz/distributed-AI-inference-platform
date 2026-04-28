# tests/test_failure_handling.py
# ---------------------------------------------------------------------------
# TEST: Fault tolerance — the MOST IMPORTANT test suite
#
# Validates the full failure detection pipeline:
#   1. Before failure  → requests reach all workers normally
#   2. Worker stops heartbeats → Master detects timeout → marks FAILED
#   3. After failure   → Master NEVER assigns the failed worker
#   4. LB is notified  → its awareness list is updated
#   5. Recovery        → if worker resumes heartbeats, Master marks it ACTIVE
#   6. No request is dropped if at least one worker is alive
# ---------------------------------------------------------------------------

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import threading
from workers.gpu_worker import GPUWorker
from master.scheduler import MasterNode, HEARTBEAT_TIMEOUT, MONITOR_INTERVAL
from lb.load_balancer import LoadBalancer
from common.models import Request, WorkerStatus


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


def wait_for_failure_detection():
    """Wait long enough for Master's monitor to detect a missed heartbeat."""
    wait_time = HEARTBEAT_TIMEOUT + MONITOR_INTERVAL + 0.5
    print(f"    (waiting {wait_time:.1f}s for failure detection...)")
    time.sleep(wait_time)


# ── Test 1: System works normally before any failure ─────────────────────────

def test_normal_operation_before_failure():
    lb, master, _ = build_system(num_workers=3)

    active_before = master.get_active_worker_ids()
    assert len(active_before) == 3, f"Expected 3 active, got {active_before}"

    for i in range(6):
        resp = lb.dispatch(Request(id=i, query=f"Q{i}"))
        assert resp is not None, f"Request {i} got no response"

    print(f"  ✓ Normal operation: all 3 workers active, 6 requests served")


# ── Test 2: Master detects heartbeat timeout and marks worker FAILED ──────────

def test_master_detects_failure_via_heartbeat():
    _, master, workers_dict = build_system(num_workers=3)

    # Worker 1 stops sending heartbeats
    workers_dict[1].shutdown()

    # Before timeout — worker 1 should still be ACTIVE
    active_before = master.get_active_worker_ids()
    assert 1 in active_before, "Worker 1 should be ACTIVE before timeout"
    print(f"    Active before timeout: {active_before}")

    wait_for_failure_detection()

    # After timeout — worker 1 should be FAILED
    with master._lock:
        status = master._workers[1].status
    assert status == WorkerStatus.FAILED, (
        f"Worker 1 should be FAILED, got {status}"
    )
    active_after = master.get_active_worker_ids()
    assert 1 not in active_after, f"Worker 1 should not be in active pool: {active_after}"

    print(f"  ✓ Master correctly marked Worker 1 as FAILED")
    print(f"    Active after failure: {active_after}")


# ── Test 3: Master NEVER assigns a failed worker ─────────────────────────────

def test_master_never_assigns_failed_worker():
    lb, master, workers_dict = build_system(num_workers=3)

    # Shut down worker 1 and wait for detection
    workers_dict[1].shutdown()
    wait_for_failure_detection()

    active = set(master.get_active_worker_ids())
    assert 1 not in active, "Worker 1 should be FAILED"

    # Send many requests — none should go to worker 1
    for i in range(10):
        resp = lb.dispatch(Request(id=i, query=f"Q{i}"))
        assert resp is not None, f"Request {i} dropped unexpectedly"
        assert resp.worker_id != 1, (
            f"Request {i} was assigned to FAILED Worker 1!"
        )

    print(f"  ✓ Zero requests sent to failed Worker 1 across 10 dispatches")


# ── Test 4: LB is notified when a worker fails ───────────────────────────────

def test_lb_notified_of_failure():
    lb, master, workers_dict = build_system(num_workers=3)

    assert 1 in lb._active_ids, "Worker 1 should be in LB awareness list"

    workers_dict[1].shutdown()
    wait_for_failure_detection()

    assert 1 not in lb._active_ids, (
        f"LB was not notified of Worker 1's failure. "
        f"LB active_ids: {lb._active_ids}"
    )
    print(f"  ✓ LB correctly notified: active_ids = {lb._active_ids}")


# ── Test 5: System continues serving requests after a failure ─────────────────

def test_system_continues_after_failure():
    lb, master, workers_dict = build_system(num_workers=3)

    workers_dict[2].shutdown()
    wait_for_failure_detection()

    active = master.get_active_worker_ids()
    assert len(active) == 2, f"Expected 2 active workers, got {active}"

    served = 0
    for i in range(6):
        resp = lb.dispatch(Request(id=i, query=f"Q{i}"))
        if resp is not None:
            served += 1

    assert served == 6, f"Expected 6 served, got {served}"
    print(f"  ✓ All 6 requests served with only 2 workers remaining: {active}")


# ── Test 6: Recovery — worker resumes heartbeats → Master marks ACTIVE ────────

def test_master_detects_worker_recovery():
    lb, master, workers_dict = build_system(num_workers=3)

    # Step 1: shut down worker 0
    workers_dict[0].shutdown()
    wait_for_failure_detection()

    with master._lock:
        assert master._workers[0].status == WorkerStatus.FAILED, \
            "Worker 0 should be FAILED after shutdown"
    print(f"    Worker 0 confirmed FAILED")

    # Step 2: revive worker 0 (restart heartbeats)
    workers_dict[0]._alive = True
    workers_dict[0]._start_heartbeat_thread()

    # Give Master time to receive a heartbeat and recover it
    recovery_wait = 3.0
    print(f"    (waiting {recovery_wait}s for recovery detection...)")
    time.sleep(recovery_wait)

    with master._lock:
        status = master._workers[0].status
    assert status == WorkerStatus.ACTIVE, (
        f"Worker 0 should be ACTIVE after recovery, got {status}"
    )

    active = master.get_active_worker_ids()
    assert 0 in active, f"Worker 0 not in active pool after recovery: {active}"

    print(f"  ✓ Worker 0 correctly recovered to ACTIVE")
    print(f"    Active pool after recovery: {active}")


# ── Test 7: All workers fail → requests return None gracefully ────────────────

def test_all_workers_fail_returns_none():
    lb, master, workers_dict = build_system(num_workers=2)

    for w in workers_dict.values():
        w.shutdown()
    wait_for_failure_detection()

    active = master.get_active_worker_ids()
    assert len(active) == 0, f"Expected no active workers, got {active}"

    resp = lb.dispatch(Request(id=99, query="Emergency query"))
    assert resp is None, f"Expected None when all workers are down, got {resp}"

    metrics = master.get_metrics()
    assert metrics["failed_requests"] >= 1

    print(f"  ✓ System gracefully returns None when all workers are down")
    print(f"    failed_requests in metrics: {metrics['failed_requests']}")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_normal_operation_before_failure,
        test_master_detects_failure_via_heartbeat,
        test_master_never_assigns_failed_worker,
        test_lb_notified_of_failure,
        test_system_continues_after_failure,
        test_master_detects_worker_recovery,
        test_all_workers_fail_returns_none,
    ]
    print("\n" + "=" * 55)
    print("  TEST SUITE: Failure Handling (Most Important)")
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