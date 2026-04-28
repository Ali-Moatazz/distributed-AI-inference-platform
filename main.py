import threading
import time
from lb.load_balancer import LoadBalancer
from master.scheduler import Scheduler
from workers.gpu_worker import GPUWorker
from common.models import Request

def simulate_user(lb, user_id):
    req = Request(id=user_id, query=f"Stress Test Query {user_id}")
    lb.receive_request(req)

def main():
    # 1. Setup workers in SIMULATION MODE for the 1000 requests test
    workers = [GPUWorker(i, simulation_mode=True) for i in range(4)]
    master = Scheduler(workers)
    lb = LoadBalancer(master)

    print("--- STARTING 1000 CONCURRENT REQUESTS TEST ---")
    start_time = time.time()
    
    threads = []
    for i in range(1000):
        t = threading.Thread(target=simulate_user, args=(lb, i))
        threads.append(t)
        t.start()
        
    # Wait for all 1000 to finish
    for t in threads:
        t.join()

    total_time = time.time() - start_time
    print(f"\n--- TEST COMPLETE ---")
    print(f"Total time for 1000 requests: {total_time:.2f} seconds")
    print(f"Throughput: {1000/total_time:.2f} requests per second")

if __name__ == "__main__":
    main()