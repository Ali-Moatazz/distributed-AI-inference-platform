def retrieve_context(query):
    print(f"[RAG] Retrieving context for request query: {query}")

    knowledge_base = {
        "load balancing": "Load balancing distributes incoming requests across multiple workers to avoid overloading one node.",
        "gpu": "GPU worker nodes execute AI inference tasks in parallel to improve throughput.",
        "llm": "A Large Language Model generates text responses based on the input query and context.",
        "rag": "Retrieval-Augmented Generation retrieves relevant context before generating an answer.",
        "distributed": "Distributed systems divide work across multiple nodes to improve scalability and reliability.",
    }

    query_lower = query.lower()

    for keyword, context in knowledge_base.items():
        if keyword in query_lower:
            return context

    return "General context about distributed AI inference systems."