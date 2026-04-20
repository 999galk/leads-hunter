"""
RAG store for successful outreach templates.

ChromaDB is used to find past high-performing messages that match
the current lead's profile. The Copywriter uses these as few-shot
examples before writing new messages.

Self-improvement loop:
  1. Copywriter calls get_successful_templates — retrieves top examples.
  2. Messages are written and evaluated by the pipeline.
  3. ingest_feedback.py reads message_feedback rows and calls
     add_message() here to grow the store over time.

On first run the collection is empty — init_rag() seeds it automatically
from data/seed_templates.json so the Copywriter has something to work with.
"""

import json
import os

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

_ROOT           = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CHROMA_PATH    = os.path.join(_ROOT, "data", "chroma_db")
_SEED_PATH      = os.path.join(_ROOT, "data", "seed_templates.json")
_COLLECTION     = "successful_messages"

# Response types treated as "high-performing" for retrieval
_POSITIVE_RESPONSES = {"replied", "accepted"}

_initialized = False  # print only on first init call per process


def _get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=_CHROMA_PATH)
    return client.get_or_create_collection(
        name=_COLLECTION,
        embedding_function=DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def init_rag() -> None:
    """
    Initialise ChromaDB. Seeds the collection from seed_templates.json
    if it is empty. Safe to call on every startup — prints only once per process.
    """
    global _initialized
    collection = _get_collection()
    if collection.count() == 0:
        _seed(collection)
        print(f"[rag] Seeded {collection.count()} templates into ChromaDB.")
        _initialized = True
    elif not _initialized:
        print(f"[rag] ChromaDB ready — {collection.count()} historical successful message templates loaded.")
        _initialized = True


def _seed(collection: chromadb.Collection) -> None:
    with open(_SEED_PATH, encoding="utf-8") as f:
        templates = json.load(f)

    ids, docs, metas = [], [], []
    for t in templates:
        ids.append(t["id"])
        docs.append(t["content"])
        metas.append({
            "message_type":  t["message_type"],
            "approach":      t["approach"],
            "industry":      t["industry"],
            "seniority":     t["seniority"],
            "response_type": t["response_type"],
            "eval_score":    t["eval_score"],
        })

    collection.add(ids=ids, documents=docs, metadatas=metas)


def add_message(
    message_id: str,
    content: str,
    message_type: str,
    approach: str,
    industry: str,
    seniority: str,
    response_type: str,
    eval_score: int,
) -> None:
    """
    Add a single message to the store. Called by ingest_feedback.py (Step 10)
    after a response is recorded in the message_feedback table.
    Only messages with a positive response_type are worth storing.
    """
    if response_type not in _POSITIVE_RESPONSES:
        return
    collection = _get_collection()
    collection.add(
        ids=[str(message_id)],
        documents=[content],
        metadatas=[{
            "message_type":  message_type,
            "approach":      approach,
            "industry":      industry,
            "seniority":     seniority,
            "response_type": response_type,
            "eval_score":    eval_score,
        }],
    )


def query_templates(
    industry: str,
    seniority: str,
    message_type: str,
    approach: str = "",
    n_results: int = 3,
) -> list[dict]:
    """
    Retrieve top-performing past messages for a similar lead profile.

    Args:
        industry:     Lead's industry (e.g. "Fintech", "Gaming").
        seniority:    Lead's seniority (e.g. "senior", "executive").
        message_type: "linkedin_invite" or "email".
        approach:     Optional — narrows to a specific angle.
        n_results:    How many examples to return (default 3).

    Returns:
        List of dicts with 'content' and 'metadata' keys.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []

    # Build semantic query from lead context
    query = f"{industry} {seniority} {message_type} {approach}".strip()

    # Metadata filter: only high-performing messages of the right type
    where: dict = {
        "$and": [
            {"message_type": {"$eq": message_type}},
            {"response_type": {"$in": list(_POSITIVE_RESPONSES)}},
        ]
    }
    if approach:
        where["$and"].append({"approach": {"$eq": approach}})

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
            where=where,
        )
    except Exception:
        # Fall back without approach filter if it yields zero results
        where["$and"] = [w for w in where["$and"] if "approach" not in w]
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
            where=where,
        )

    output = []
    docs  = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    for doc, meta in zip(docs, metas):
        output.append({"content": doc, "metadata": meta})
    return output


if __name__ == "__main__":
    init_rag()
