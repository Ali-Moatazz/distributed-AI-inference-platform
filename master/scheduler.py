import threading

class Scheduler:
    def __init__(self, workers):
        self.workers = workers
        self.index = 0
        # Only allow 4 "active" tasks at once to protect your CPU/RAM
        self.execution_limit = threading.Semaphore(4) 
        self.completed_count = 0

    def get_next_worker(self):
        worker = self.workers[self.index]
        self.index = (self.index + 1) % len(self.workers)
        return worker

    def handle_request(self, request):
        # All 1000 requests hit this line, but only 4 pass through at a time
        with self.execution_limit:
            worker = self.get_next_worker()
            response = worker.process(request)
            
            self.completed_count += 1
            if self.completed_count % 10 == 0:
                print(f"[MASTER] Progress: {self.completed_count}/1000 requests completed...")
                
            return response