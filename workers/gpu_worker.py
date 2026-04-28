import time
from llm.inference import run_llm
from rag.retriever import retrieve_context


class GPUWorker:
    def __init__(self, id):
        self.id = id

    def process(self, request):
        start = time.time()

        print(f"[Worker {self.id}] Processing request {request.id}")

        # Step 1: RAG retrieves context
        context = retrieve_context(request.query)

        # Step 2: LLM generates response using query + context
        result = run_llm(request.query, context)

        latency = time.time() - start

        return {
            "id": request.id,
            "worker_id": self.id,
            "query": request.query,
            "context": context,
            "result": result,
            "latency": latency
        }