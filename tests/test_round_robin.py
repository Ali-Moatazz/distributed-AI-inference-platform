from lb.load_balancer import LoadBalancer
from master.scheduler import MasterNode
from workers.mock_worker import MockWorker


class Request:
    def __init__(self, id):
        self.id = id


def test_rr():

    workers = {i: MockWorker(i) for i in range(3)}

    master = MasterNode(list(workers.keys()))
    lb = LoadBalancer(master, workers)

    master.set_load_balancer(lb)

    print("\n===== ROUND ROBIN TEST =====\n")

    for i in range(9):
        lb.dispatch(Request(i))

    print("\nWorker load distribution:")
    print(master.worker_load)


if __name__ == "__main__":
    test_rr()