from lb.load_balancer import LoadBalancer
from master.scheduler import Scheduler
from workers.gpu_worker import GPUWorker

class Request:
    def __init__(self, id, query):
        self.id = id
        self.query = query


def main():

    # 1. Create workers (GPU cluster)
    workers = [GPUWorker(i) for i in range(4)]

    # 2. Create master scheduler
    master = Scheduler(workers)

    # 3. Connect LB → Master (IMPORTANT: your LB already expects this)
    lb = LoadBalancer(master)

    # 4. Simulate requests
    for i in range(10):
        req = Request(i, f"Query {i}")

        print("\n==============================")
        response = lb.receive_request(req)

        print(f"[CLIENT] Response: {response}")


if __name__ == "__main__":
    main()