from lb.load_balancer import LoadBalancer
from master.scheduler import MasterNode
from workers.gpu_worker import GPUWorker
from client.load_generator import run_load_test


def main():

    workers = {i: GPUWorker(i) for i in range(3)}

    master = MasterNode(list(workers.keys()))
    lb = LoadBalancer(master, workers)

    master.set_load_balancer(lb)

    run_load_test(lb, num_users=10)


if __name__ == "__main__":
    main()