from llama_cpp import Llama
import os

# Find the model file in the main folder
current_dir = os.path.dirname(__file__)
model_path = os.path.abspath(os.path.join(current_dir, "..", "model.gguf"))

print(f"[LLM] Loading model from: {model_path}")

# Load the model (We do this globally so all workers share it to save RAM)
# n_ctx=512 is enough for short questions and keeps it fast
llm = Llama(model_path=model_path, n_ctx=512, verbose=False)

def run_llm(query, context):
    print(f"[LLM] Locally processing: {query[:30]}...")
    
    # Prompt format for Llama-3.2
    prompt = f"Context: {context}\nQuestion: {query}\nAnswer:"
    
    output = llm(
        prompt, 
        max_tokens=100, 
        stop=["Question:", "\n"], 
        echo=False
    )
    
    return output["choices"][0]["text"].strip()