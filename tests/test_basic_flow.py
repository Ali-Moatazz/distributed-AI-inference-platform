from lb.load_balancer import LoadBalancer
from master.scheduler import MasterNode
from workers.mock_worker import MockWorker


class Request:
    def __init__(self, id):
        self.id = id


def test_basic_flow():

    workers = {i: MockWorker(i) for i in range(3)}

    master = MasterNode(list(workers.keys()))
    lb = LoadBalancer(master, workers)

    master.set_load_balancer(lb)

    print("\n===== BASIC FLOW TEST =====\n")

    for i in range(5):
        req = Request(i)
        response = lb.dispatch(req)
        print(f"Response: {response}")


if __name__ == "__main__":
    test_basic_flow()