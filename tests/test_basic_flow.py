# tests/test_basic_flow.py
# ---------------------------------------------------------------------------
# TEST: Basic end-to-end flow
#
# Validates:
#   1. A request travels: Client → LB → Master → Worker → back to Client
#   2. The response has correct fields (id, result, latency, worker_id)
#   3. Master metrics are updated after the request
#   4. Every response's worker_id is from the active pool
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
    """Spin up a clean system. Returns (lb, master, workers_dict)."""
    worker_ids   = list(range(num_workers))
    workers_dict = {wid: GPUWorker(worker_id=wid) for wid in worker_ids}
    master       = MasterNode(worker_ids=worker_ids)
    lb           = LoadBalancer(master_node=master, workers=workers_dict)
    master.set_load_balancer(lb)
    for w in workers_dict.values():
        w.set_master(master)
        w._alive = True
        w._start_heartbeat_thread()
    time.sleep(0.3)   # let heartbeats register before tests run
    return lb, master, workers_dict


# ── Test 1: single request returns valid Response ────────────────────────────

def test_single_request_returns_response():
    lb, master, _ = build_system()
    response = lb.dispatch(Request(id=1, query="What is AI?"))

    assert response is not None,                     "Response must not be None"
    assert response.id == 1,                         f"Wrong id: {response.id}"
    assert isinstance(response.result, str),         "Result must be a string"
    assert len(response.result) > 0,                 "Result must not be empty"
    assert response.latency > 0,                     "Latency must be > 0"
    assert response.worker_id in [0, 1, 2],          f"Bad worker_id: {response.worker_id}"

    print(f"  ✓ Worker {response.worker_id} responded in {response.latency:.3f}s")


# ── Test 2: multiple sequential requests all get responses ───────────────────

def test_multiple_requests_all_served():
    lb, _, _ = build_system()
    for i in range(9):
        resp = lb.dispatch(Request(id=i, query=f"Query {i}"))
        assert resp is not None, f"Request {i} got no response"

    print(f"  ✓ All 9 requests served without dropping any")


# ── Test 3: Master metrics are updated ───────────────────────────────────────

def test_master_metrics_updated():
    lb, master, _ = build_system()
    for i in range(5):
        lb.dispatch(Request(id=i, query=f"Query {i}"))

    m = master.get_metrics()
    assert m["total_requests"]  == 5, f"Expected 5, got {m['total_requests']}"
    assert m["failed_requests"] == 0, f"Expected 0, got {m['failed_requests']}"
    assert m["average_latency_s"] > 0, "Average latency must be > 0"

    print(f"  ✓ Metrics OK — total={m['total_requests']}, "
          f"avg_latency={m['average_latency_s']:.4f}s")


# ── Test 4: every response's worker_id is in the active pool ─────────────────

def test_response_worker_ids_are_active():
    lb, master, _ = build_system()
    active = set(master.get_active_worker_ids())

    for i in range(6):
        resp = lb.dispatch(Request(id=i, query=f"Q{i}"))
        assert resp.worker_id in active, (
            f"Request {i} went to inactive worker {resp.worker_id}"
        )

    print(f"  ✓ All workers used are in active pool: {active}")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_single_request_returns_response,
        test_multiple_requests_all_served,
        test_master_metrics_updated,
        test_response_worker_ids_are_active,
    ]
    print("\n" + "=" * 55)
    print("  TEST SUITE: Basic Flow")
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