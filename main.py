from workers.gpu_worker import GPUWorker
from master.scheduler import Scheduler
from lb.load_balancer import LoadBalancer
from client.load_generator import run_load_test


def main():
    # Create GPU workers
    workers = [GPUWorker(i) for i in range(4)]  # simulate 4 GPUs

    # Master Scheduler controls task execution
    scheduler = Scheduler(workers)

    # Load Balancer receives client requests first
    load_balancer = LoadBalancer(scheduler)

    # Run simulation
    run_load_test(load_balancer, num_users=1000)


if __name__ == "__main__":
    main()