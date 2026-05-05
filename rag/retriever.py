# rag/retriever.py
import os
from supabase import create_client, Client
import logging
import string
from dotenv import load_dotenv

current_dir = os.path.dirname(__file__)
env_path = os.path.join(current_dir, "..", ".env")
load_dotenv(env_path)
load_dotenv() 


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
logger = logging.getLogger("RAG")

supabase=None
if not SUPABASE_URL:
    logger.error("RAG Error: SUPABASE_URL is missing! Check your .env file.")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logger.error(f"Failed to connect to Supabase: {e}")


def retrieve_context(query: str) -> str:
    """
    Searches Supabase knowledge_base table using a single OR query
    instead of multiple HTTP requests.
    """

    if supabase is None:
        return "General technical context for distributed AI systems."
    
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