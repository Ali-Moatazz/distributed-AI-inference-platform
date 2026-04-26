class LoadBalancer:
    def __init__(self, scheduler):
        self.scheduler = scheduler

    def handle_request(self, request):
        print(f"[Load Balancer] Received request {request.id}")

        # Forward request to Master Scheduler
        return self.scheduler.handle_request(request)