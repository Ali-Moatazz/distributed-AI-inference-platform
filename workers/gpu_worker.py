import time
from llm.inference import run_llm
from rag.retriever import retrieve_context

class GPUWorker:
    def __init__(self, id, simulation_mode=False):
        self.id = id
        self.simulation_mode = simulation_mode

    def process(self, request):
        start = time.time()
        
        if self.simulation_mode:
            # For 1000 requests test: Simulate the AI delay
            time.sleep(0.1) 
            result = "Simulated AI Response"
            context = "Simulated Context"
        else:
            # For real demonstration: Use the real Llama model
            context = retrieve_context(request.query)
            result = run_llm(request.query, context)

        latency = time.time() - start
        return {
            "id": request.id,
            "worker_id": self.id,
            "result": result,
            "latency": latency
        }