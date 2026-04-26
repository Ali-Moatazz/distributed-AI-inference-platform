import threading
from common.models import Request


def simulate_user(load_balancer, user_id):
    request = Request(id=user_id, query=f"Query {user_id}")

    # Client sends request to Load Balancer first
    response = load_balancer.handle_request(request)

    print(
        f"[Client] Response {response['id']} "
        f"| Worker: {response['worker_id']} "
        f"| Latency: {response['latency']:.3f}s"
    )


def run_load_test(load_balancer, num_users=1000):
    threads = []

    for i in range(num_users):
        t = threading.Thread(target=simulate_user, args=(load_balancer, i))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()