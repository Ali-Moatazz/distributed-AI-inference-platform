# distributed-AI-inference-platform
🚀 Distributed AI Inference Platform

A scalable distributed system designed to handle 1000+ concurrent AI inference requests using load balancing, GPU task distribution, and fault-tolerant microservice architecture.

The system simulates a real-world LLM inference infrastructure, where incoming requests are dynamically distributed across multiple compute nodes to ensure low latency, high throughput, and optimal GPU utilization.

🧠 System Overview

This project implements a full distributed computing pipeline consisting of:

Client request simulation (1000+ concurrent users)
Intelligent load balancer
Master scheduler node
GPU worker nodes
RAG (Retrieval-Augmented Generation) module
Fault-tolerant execution layer
🏗️ Architecture
Client Layer
Simulates high-concurrency AI requests
Generates load for performance testing
Load Balancer
Distributes incoming requests using:
Round Robin
Least Connections
Load-aware routing
Master Node
Schedules tasks
Monitors system health
Handles coordination between workers
GPU Worker Nodes
Execute LLM inference tasks
Process requests in parallel
Return computed responses
RAG Module
Retrieves contextual knowledge from vector store
Enhances LLM outputs with external data
⚙️ Key Features
🚀 High Concurrency Handling
Supports 1000+ simultaneous requests
Optimized request scheduling for minimal latency
⚖️ Load Balancing Strategies
Round Robin
Least Connections
Dynamic load-aware routing
🧠 Distributed Task Execution
GPU-based parallel processing
Efficient task distribution across nodes
🔁 Fault Tolerance
Automatic detection of node failures
Task reassignment to active nodes
Ensures no request loss
📊 Performance Monitoring
Latency tracking
Throughput analysis
GPU utilization monitoring
🧪 Testing & Evaluation

The system is evaluated under:

Load simulation (100 → 1000 users)
Node failure scenarios
Performance benchmarking:
Response time
Throughput
Resource utilization
🛠️ Tech Stack
Python
Distributed Systems Architecture
Socket Programming
Load Balancing Algorithms
CUDA / GPU Computing (conceptual or optional implementation)
Vector Databases (RAG module)
Docker (optional deployment layer)
📌 Key Learning Outcomes
Distributed system design
Load balancing strategies
Fault-tolerant system architecture
High-concurrency request handling
GPU task scheduling principles
Real-world AI infrastructure simulation
🎯 Why this project matters

This project simulates real-world infrastructure used in:

AI model serving systems
Cloud inference platforms
Large-scale backend systems
Distributed computing clusters
📈 Potential Improvements
Kubernetes-based orchestration
Real GPU cluster deployment
Kafka-based message queue
Prometheus + Grafana monitoring
Auto-scaling workers


Steps for AI Llama:
 1. install from https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf?download=true
 2. put the file downloaded in the folder containing the main.py
 3. rename it to Model.gguf
 4. run pip install llama-cpp-python
 5. (if failure of 3): run pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu 
 
