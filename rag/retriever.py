# rag/retriever.py
from supabase import create_client, Client
import logging
import string

SUPABASE_URL = "https://hiizomzqwczdnfgqgxsh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpaXpvbXpxd2N6ZG5mZ3FneHNoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc0MDk5MTAsImV4cCI6MjA5Mjk4NTkxMH0.fLs1nUEsp86pOHUJ6WJ6cvrbpBDPg_kimm5er8S3plM"

logger = logging.getLogger("RAG")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logger.error(f"Failed to connect to Supabase: {e}")


def retrieve_context(query: str) -> str:
    """
    Searches Supabase knowledge_base table using a single OR query
    instead of multiple HTTP requests.
    """
    logger.info(f"Querying database for: {query}")

    # Extract clean words
    words = [
        w.strip(string.punctuation).lower()
        for w in query.split()
    ]

    # Filter noise words
    keywords = [w for w in words if len(w) >= 4]

    if not keywords:
        return "General technical context for distributed AI systems."

    try:
        # Build OR filter string:
        # keyword.ilike.word1,keyword.ilike.word2,...
        or_filter = ",".join([f"keyword.ilike.*{w}*" for w in keywords])

        response = (
            supabase.table("knowledge_base")
            .select("content")
            .or_(or_filter)
            .limit(1)
            .execute()
        )

        if response.data:
            context = response.data[0]["content"]
            logger.info(f"Found context in Supabase: {context[:60]}...")
            return context

    except Exception as e:
        logger.error(f"Database lookup failed: {e}")

    return "General technical context for distributed AI systems."