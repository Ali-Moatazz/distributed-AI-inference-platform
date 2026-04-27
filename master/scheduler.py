class Scheduler:
    def __init__(self, workers):
        self.workers = workers
        self.index = 0

    def get_next_worker(self):
        worker = self.workers[self.index]
        self.index = (self.index + 1) % len(self.workers)
        return worker

    def handle_request(self, request):
        print(f"[MASTER] Received request {request.id}")

        # 1. Select worker (Round Robin)
        worker = self.get_next_worker()

        print(f"[MASTER] Assigning request {request.id} → Worker {worker.id}")

        # 2. Send to worker
        response = worker.process(request)

        print(f"[MASTER] Completed request {request.id}")

        return response