# utils/pinecone_schema_query.py
import os
import pinecone
from typing import List, Tuple
from utils.question_embedding import embed_question
# -----------------------------------------------------------------
# 1️⃣  Get (or create) the Pinecone index that stores the *schema* embeddings.
# -----------------------------------------------------------------
from pinecone import Pinecone, ServerlessSpec
# -----------------------------------------------------------------
# 1️⃣  Get (or create) the Pinecone index that stores the *schema* embeddings.
# -----------------------------------------------------------------
def _get_schema_index() -> Pinecone.Index:
    return _get_schema_index_for_key(os.getenv("PINECONE_API_KEY"))


def _get_schema_index_for_key(pc_api_key: str | None) -> Pinecone.Index:
    schema_index_name = os.getenv("PINECONE_INDEX_NAME", "schema-embeddings")
    
    if not pc_api_key:
        raise RuntimeError("PINECONE_API_KEY not found in .env")

    pc = Pinecone(api_key=pc_api_key)

    existing_indexes = [idx.name for idx in pc.list_indexes()]
    if schema_index_name not in existing_indexes:
        pc.create_index(
            name=schema_index_name,
            dimension=768,               # Gemini‑001 embedding dimension
            metric="cosine",            # <-- cosine similarity
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
    return pc.Index(schema_index_name)


# -----------------------------------------------------------------
# 2️⃣  Retrieve the top‑k most‑similar schema entries for a question.
# -----------------------------------------------------------------
def retrieve_top_schema(
    question: str,
    top_k: int = 5,
    namespace: str = "",
    gemini_api_key: str | None = None,
    pinecone_api_key: str | None = None,
) -> List[Tuple[str, float, dict]]:

    q_emb = embed_question(question, api_key=gemini_api_key)

    index = _get_schema_index_for_key(pinecone_api_key or os.getenv("PINECONE_API_KEY"))
    results = index.query(
        namespace=namespace,
        vector=q_emb,
        top_k=top_k,
        include_metadata=True,
        include_values=False,   # we only need the metadata, not the stored vectors
    )
    # Convert Pinecone Match objects to a simple list of tuples
    return [(m.id, m.score, m.metadata) for m in results.matches]


# -----------------------------------------------------------------
# Optional helper: compute cosine similarity manually (useful for debugging).
# -----------------------------------------------------------------
def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:

    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must be of the same length")
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
