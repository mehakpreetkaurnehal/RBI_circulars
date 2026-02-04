# import os
# import json
# import faiss
# import numpy as np
# from typing import List
# from dotenv import load_dotenv

# from sentence_transformers import SentenceTransformer, CrossEncoder

# load_dotenv()

# FAISS_DIR = os.getenv("RBI_FAISS_DIR", "rbi_faiss_store")
# FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
# CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")

# EMBED_MODEL_NAME = os.getenv(
#     "EMBED_MODEL",
#     "sentence-transformers/all-mpnet-base-v2"
# )

# RERANK_MODEL_NAME = os.getenv(
#     "RERANK_MODEL",
#     "cross-encoder/ms-marco-MiniLM-L-6-v2"
# )

# TOP_K_INITIAL = int(os.getenv("TOP_K_INITIAL", "70"))  # retrieve broadly
# TOP_K_FINAL = int(os.getenv("TOP_K_FINAL", "8"))       # final context size
# MAX_L2_DISTANCE = float(os.getenv("MAX_L2_DISTANCE", "1.5"))

# print(f"🧠 Loading embedding model: {EMBED_MODEL_NAME}")
# embed_model = SentenceTransformer(EMBED_MODEL_NAME)

# print(f"🎯 Loading reranker model: {RERANK_MODEL_NAME}")
# reranker = CrossEncoder(RERANK_MODEL_NAME)

# print("🔄 Loading FAISS index...")
# faiss_index = faiss.read_index(FAISS_INDEX_PATH)

# print("🔄 Loading chunk metadata...")
# with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
#     chunk_metadata = json.load(f)

# assert faiss_index.ntotal == len(chunk_metadata), "FAISS/metadata mismatch"

# try:
#     from rank_bm25 import BM25Okapi
#     tokenized = [c["chunk_text"].split() for c in chunk_metadata]
#     bm25 = BM25Okapi(tokenized)
#     print("⚡ BM25 enabled")
# except ImportError:
#     bm25 = None
#     print("⚠ BM25 not installed (semantic-only retrieval)")

# from google import genai
# from google.genai import types

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# if not GEMINI_API_KEY:
#     raise RuntimeError("Missing GEMINI_API_KEY in .env")

# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash") 


# gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# def call_gemini(prompt: str, max_tokens=1200, temperature=0.2) -> str:
#     resp = gemini_client.models.generate_content(
#         model=GEMINI_MODEL,
#         contents=prompt,
#         config=types.GenerateContentConfig(
#             max_output_tokens=max_tokens,
#             temperature=temperature
#         )
#     )
#     return resp.text.strip()

# def retrieve_and_rerank(query: str) -> List[dict]:
#     # Dense embedding
#     q_emb = embed_model.encode(
#         [query],
#         normalize_embeddings=True
#     ).astype("float32")

#     distances, indices = faiss_index.search(q_emb, TOP_K_INITIAL)

#     candidates = []
#     for dist, idx in zip(distances[0], indices[0]):
#         if dist > MAX_L2_DISTANCE:
#             continue

#         meta = chunk_metadata[idx]
#         candidates.append({
#             **meta,
#             "distance": float(dist),
#             "score_dense": 1.0 / (1.0 + dist)
#         })

#     # BM25 score
#     if bm25:
#         bm25_scores = bm25.get_scores(query.split())
#         for c in candidates:
#             c["score_bm25"] = float(bm25_scores[c["chunk_index"]])

#     # Cross-encoder reranking
#     rerank_inputs = [(query, c["chunk_text"]) for c in candidates]
#     rerank_scores = reranker.predict(rerank_inputs)

#     for i, score in enumerate(rerank_scores):
#         candidates[i]["score_rerank"] = float(score)

#     candidates.sort(key=lambda x: x["score_rerank"], reverse=True)

#     return candidates[:TOP_K_FINAL]

# # =========================
# # PROMPTS
# # =========================
# def build_answer_prompt(question: str, chunks: List[dict]) -> str:
#     blocks = []
#     for c in chunks:
#         snippet = c["chunk_text"][:900].rsplit(" ", 1)[0]
#         blocks.append(
#             f"[Circular: {c['title']} | Date: {c['issue_date']} | URL: {c['pdf_url']}]\n{snippet}"
#         )

#     context = "\n\n---\n\n".join(blocks)

#     return f"""
# You are an RBI regulatory expert.

# Rules:
# - Use ONLY the provided context
# - Do NOT hallucinate
# - Provide a complete answer (do not stop mid-sentence)
# - If information is missing, clearly say so

# QUESTION:
# {question}

# CONTEXT:
# {context}

# Provide a structured, factual answer.
# """

# def build_judge_prompt(question: str, answer: str, chunks: List[dict]) -> str:
#     context = "\n\n---\n\n".join(c["chunk_text"][:300] for c in chunks)

#     return f"""
# You are a strict RBI policy reviewer.

# QUESTION:
# {question}

# CONTEXT:
# {context}

# GENERATED ANSWER:
# {answer}

# Evaluate using ONLY the context.

# Return:
# Grounded: Yes/No
# Hallucinated: Yes/No (list statements if yes)
# Completeness: High/Medium/Low
# Score: 1-5
# Justification:
# """

# # =========================
# # MAIN LOOP
# # =========================
# def main():
#     print("\n📌 RBI RAG pipeline ready (type 'exit' to quit)\n")

#     while True:
#         q = input("❓ Question: ").strip()
#         if not q:
#             continue
#         if q.lower() == "exit":
#             break

#         retrieved = retrieve_and_rerank(q)
#         if not retrieved:
#             print("❌ No relevant RBI context found.")
#             continue

#         print("\n🔍 Top reranked chunks:")
#         for i, c in enumerate(retrieved, 1):
#             print(f"{i}. {c['title']} | rerank={c['score_rerank']:.3f}")

#         # Answer generation
#         answer_prompt = build_answer_prompt(q, retrieved)
#         answer = call_gemini(answer_prompt)

#         # Evaluation
#         judge_prompt = build_judge_prompt(q, answer, retrieved)
#         judge_report = call_gemini(judge_prompt, max_tokens=500, temperature=0.0)

#         # Output
#         print("\n=== ANSWER ===\n")
#         print(answer)

#         print("\n=== JUDGE REPORT ===\n")
#         print(judge_report)

#         print("\n=== SOURCES ===")
#         for c in retrieved:
#             print(c["pdf_url"])
#         print("\n" + "=" * 60 + "\n")

# if __name__ == "__main__":
#     main()



import os
import json
import faiss
import numpy as np
from typing import List
from dotenv import load_dotenv

from sentence_transformers import SentenceTransformer, CrossEncoder

load_dotenv()

FAISS_DIR = os.getenv("RBI_FAISS_DIR", "rbi_faiss_store")
FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")

EMBED_MODEL_NAME = os.getenv(
    "EMBED_MODEL",
    "sentence-transformers/all-mpnet-base-v2"
)

RERANK_MODEL_NAME = os.getenv(
    "RERANK_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

TOP_K_INITIAL = int(os.getenv("TOP_K_INITIAL", "70"))
TOP_K_FINAL = int(os.getenv("TOP_K_FINAL", "8"))
MAX_L2_DISTANCE = float(os.getenv("MAX_L2_DISTANCE", "1.5"))

print(f"🧠 Loading embedding model: {EMBED_MODEL_NAME}")
embed_model = SentenceTransformer(EMBED_MODEL_NAME)

print(f"🎯 Loading reranker model: {RERANK_MODEL_NAME}")
reranker = CrossEncoder(RERANK_MODEL_NAME)

print("🔄 Loading FAISS index...")
faiss_index = faiss.read_index(FAISS_INDEX_PATH)

print("🔄 Loading chunk metadata...")
with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
    chunk_metadata = json.load(f)

assert faiss_index.ntotal == len(chunk_metadata), "FAISS / metadata mismatch"

try:
    from rank_bm25 import BM25Okapi
    tokenized = [c["chunk_text"].split() for c in chunk_metadata]
    bm25 = BM25Okapi(tokenized)
    print("⚡ BM25 enabled")
except ImportError:
    bm25 = None
    print("⚠ BM25 not installed (semantic-only)")
from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in .env")

GEMINI_MODEL = "models/gemini-2.5-flash"

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

def call_gemini(prompt: str, max_tokens=1200, temperature=0.2) -> str:
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature
        )
    )
    return response.text.strip()

def retrieve_and_rerank(query: str) -> List[dict]:
    q_emb = embed_model.encode(
        [query],
        normalize_embeddings=True
    ).astype("float32")

    distances, indices = faiss_index.search(q_emb, TOP_K_INITIAL)

    candidates = []
    for dist, idx in zip(distances[0], indices[0]):
        if dist > MAX_L2_DISTANCE:
            continue

        meta = chunk_metadata[idx]
        candidates.append({
            **meta,
            "distance": float(dist),
            "score_dense": 1.0 / (1.0 + dist)
        })

    if bm25:
        bm25_scores = bm25.get_scores(query.split())
        for c in candidates:
            c["score_bm25"] = float(bm25_scores[c["chunk_index"]])

    rerank_inputs = [(query, c["chunk_text"]) for c in candidates]
    rerank_scores = reranker.predict(rerank_inputs)

    for i, score in enumerate(rerank_scores):
        candidates[i]["score_rerank"] = float(score)

    candidates.sort(key=lambda x: x["score_rerank"], reverse=True)

    return candidates[:TOP_K_FINAL]

def build_answer_prompt(question: str, chunks: List[dict]) -> str:
    blocks = []
    for c in chunks:
        snippet = c["chunk_text"][:900].rsplit(" ", 1)[0]
        blocks.append(
            f"[Circular: {c['title']} | Date: {c['issue_date']} | URL: {c['pdf_url']}]\n{snippet}"
        )

    context = "\n\n---\n\n".join(blocks)

    return f"""
You are an RBI regulatory expert.

Rules:
- Use ONLY the provided context
- Do NOT hallucinate
- Provide a complete answer (do not stop mid-sentence)
- If information is missing, clearly say so

QUESTION:
{question}

CONTEXT:
{context}

Provide a structured, factual answer.
IMPORTANT:
- If the question asks about duration or date and the context contains a date,
  you MUST mention the date explicitly.
- Do NOT say "not specified" if a date exists.

"""

def build_judge_prompt(question: str, answer: str, chunks: List[dict]) -> str:
    context = "\n\n---\n\n".join(c["chunk_text"][:300] for c in chunks)

    return f"""
You are a strict RBI policy reviewer.

QUESTION:
{question}

CONTEXT:
{context}

GENERATED ANSWER:
{answer}

Evaluate using ONLY the context.

Return:
Grounded: Yes/No
Hallucinated: Yes/No (list statements if yes)
Completeness: High/Medium/Low
Score: 1-5
Justification:
"""

def main():
    print("\n📌 RBI RAG pipeline ready (type 'exit' to quit)\n")

    while True:
        q = input("❓ Question: ").strip()
        if not q:
            continue
        if q.lower() == "exit":
            break

        retrieved = retrieve_and_rerank(q)
        if not retrieved:
            print("❌ No relevant RBI context found.")
            continue

        print("\n🔍 Top reranked chunks:")
        for i, c in enumerate(retrieved, 1):
            print(f"{i}. {c['title']} | rerank={c['score_rerank']:.3f}")

        answer_prompt = build_answer_prompt(q, retrieved)
        answer = call_gemini(answer_prompt)

        judge_prompt = build_judge_prompt(q, answer, retrieved)
        judge_report = call_gemini(judge_prompt, max_tokens=500, temperature=0.0)

        print("\n=== ANSWER ===\n")
        print(answer)

        print("\n=== JUDGE REPORT ===\n")
        print(judge_report)

        print("\n=== SOURCES ===")
        for c in retrieved:
            print(c["pdf_url"])

        print("\n" + "=" * 60 + "\n")

if __name__ == "__main__":
    main()
