from lb.load_balancer import LoadBalancer
from master.scheduler import Scheduler
from workers.mock_worker import MockWorker

class Request:
    def __init__(self, id):
        self.id = id


def test_system():

    # 1. Create mock workers
    workers = [MockWorker(i) for i in range(3)]

    # 2. Create master
    master = Scheduler(workers)

    # 3. Create LB
    lb = LoadBalancer(master)

    # 4. Send multiple requests
    for i in range(10):
        req = Request(i)

        print("\n====================")
        response = lb.receive_request(req)

        print(f"[TEST] Response: {response}")


if __name__ == "__main__":
    test_system()