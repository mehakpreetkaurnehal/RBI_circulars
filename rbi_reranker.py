def rerank_chunks(chunks, top_k=10):
    """
    Rerank using semantic score only
    (BM25 can be added later if needed)
    """
    ranked = sorted(
        chunks,
        key=lambda x: x["semantic_score"],
        reverse=True
    )

    return ranked[:top_k]
