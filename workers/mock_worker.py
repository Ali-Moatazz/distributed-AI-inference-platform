####Test Filie ONLY####

class MockWorker:
    def __init__(self, id):
        self.id = id

    def process(self, request):
        print(f"[MOCK WORKER {self.id}] handled request {request.id}")
        return {
            "id": request.id,
            "worker": self.id
        }