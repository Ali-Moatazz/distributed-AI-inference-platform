class Scheduler:
    def __init__(self, workers):
        self.workers = workers
        self.index = 0

    def get_next_worker(self):
        # Round Robin worker selection
        worker = self.workers[self.index]
        self.index = (self.index + 1) % len(self.workers)
        return worker

    def handle_request(self, request):
        print(f"[Scheduler] Scheduling request {request.id}")

        worker = self.get_next_worker()

        print(f"[Scheduler] Assigned request {request.id} to Worker {worker.id}")

        response = worker.process(request)
        return response