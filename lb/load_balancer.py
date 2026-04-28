class LoadBalancer:
    def __init__(self, master_scheduler):
        self.master = master_scheduler

    def handle_request(self, request):
        return self.receive_request(request)

    def receive_request(self, request):
        # 1. Log incoming request
        print(f"[LB] Received request {request.id} from client")

        # 2. Forward to master scheduler
        response = self.forward_to_master(request)

        return response

    def forward_to_master(self, request):
        # 3. Separation layer (no scheduling logic here)
        print(f"[LB] Forwarding request {request.id} to Master Scheduler")

        return self.master.handle_request(request)