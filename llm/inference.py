import time


def run_llm(query, context):
    print(f"[LLM] Generating response for query: {query}")

    # Simulate LLM/GPU inference delay
    time.sleep(0.2)

    return (
        f"LLM Response: For the query '{query}', "
        f"the system used this retrieved context: '{context}'."
    )