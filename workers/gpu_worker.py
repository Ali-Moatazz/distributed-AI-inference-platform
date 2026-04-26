import time


class GPUWorker:
    def __init__(self, id):
        self.id = id

    def process(self, request):
        print(f"[Worker {self.id}] Processing request {request.id}")

        # Simulate processing (LLM + RAG)
        time.sleep(0.2)

        return {
            "id": request.id,
            "worker_id": self.id,
            "result": f"Processed request {request.id}",
        }