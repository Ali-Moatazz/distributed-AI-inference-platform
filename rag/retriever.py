# rag/retriever.py
from supabase import create_client, Client
import logging
import string

# Paste your real keys here!
SUPABASE_URL = "https://hiizomzqwczdnfgqgxsh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpaXpvbXpxd2N6ZG5mZ3FneHNoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc0MDk5MTAsImV4cCI6MjA5Mjk4NTkxMH0.fLs1nUEsp86pOHUJ6WJ6cvrbpBDPg_kimm5er8S3plM"

logger = logging.getLogger("RAG")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logger.error(f"Failed to connect to Supabase: {e}")

def retrieve_context(query: str) -> str:
    """
    Searches Supabase knowledge_base table for keywords in the user query.
    """
    logger.info(f"Querying database for: {query}")
    
    # Simple keyword extraction (splitting query into words)
    words = [w.strip(string.punctuation).lower() for w in query.split()]
    
    for word in words:
        if len(word) < 4: continue # Skip short words like 'the', 'is', 'how'
        
        try:
            # Search database: 'keyword' column contains the word
            response = supabase.table("knowledge_base") \
                .select("content") \
                .ilike("keyword", f"{word}") \
                .execute()

            if response.data:
                context = response.data[0]['content']
                logger.info(f"Found context in Supabase: {context[:50]}...")
                return context
        except Exception as e:
            logger.error(f"Database lookup failed: {e}")

    return "General technical context for distributed AI systems."