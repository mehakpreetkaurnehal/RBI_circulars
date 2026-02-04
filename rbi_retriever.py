import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

FAISS_DIR = "rbi_faiss_store"
FAISS_INDEX_PATH = f"{FAISS_DIR}/rbi_chunks.index"
CHUNK_META_PATH = f"{FAISS_DIR}/rbi_chunk_metadata.json"

EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
TOP_K = 70   # broad retrieval

faiss_index = faiss.read_index(FAISS_INDEX_PATH)

with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
    metadata = json.load(f)

model = SentenceTransformer(EMBED_MODEL_NAME)

def retrieve_chunks(query: str, top_k: int = TOP_K):
    query_emb = model.encode(
        [query],
        normalize_embeddings=True
    ).astype("float32")

    distances, indices = faiss_index.search(query_emb, top_k)

    results = []
    for rank, idx in enumerate(indices[0]):
        results.append({
            **metadata[idx],
            "semantic_score": float(1 - distances[0][rank])
        })

    return results
