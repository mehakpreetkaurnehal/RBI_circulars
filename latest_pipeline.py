import os
import re
import sqlite3
import faiss
import json
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime

from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

import streamlit as st
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Constants and Paths
# ────────────────────────────────────────────────────────────────────────────── 

DB_PATH            = "rbi_scrape_text.db"
FAISS_DIR          = "rbi_scrape_text_fixed"
FAISS_INDEX_PATH   = os.path.join(FAISS_DIR, "rbi_chunks.index")
CHUNK_META_PATH    = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
BM25_PATH          = os.path.join(FAISS_DIR, "bm25_index.json")

EMBED_MODEL_NAME   = "sentence-transformers/all-mpnet-base-v2"
RERANK_MODEL_NAME  = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GEMINI_MODEL       = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

CHUNK_SIZE         = 512
CHUNK_OVERLAP      = 100
INITIAL_TOP_K      = 50
RERANK_TOP_K       = 20
TOP_K_TO_SEND      = 7

os.makedirs(FAISS_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def sanitize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def chunk_text_with_sentences(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current_chunk, length = [], [], 0

    for sent in sentences:
        if length + len(sent) > CHUNK_SIZE and current_chunk:
            chunks.append(" ".join(current_chunk))
            overlap_sentences, ol_len = [], 0
            for s in reversed(current_chunk):
                if ol_len + len(s) <= CHUNK_OVERLAP:
                    overlap_sentences.insert(0, s)
                    ol_len += len(s)
                else:
                    break
            current_chunk, length = overlap_sentences, ol_len

        current_chunk.append(sent)
        length += len(sent)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

# ──────────────────────────────────────────────────────────────────────────────
# BUILD INDEX (RUN ONCE)
# ──────────────────────────────────────────────────────────────────────────────

def build_index():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT ref_no, title, issue_date, pdf_url, body_text FROM circulars")
    rows = cur.fetchall()
    conn.close()

    model = SentenceTransformer(EMBED_MODEL_NAME)

    faiss_index = None
    chunk_metadata = []
    bm25_corpus = []

    for ref_no, title, issue_date, pdf_url, body_text in rows:
        if not body_text:
            continue
        full_text = f"{title}\n\n{sanitize(body_text)}"
        chunks    = chunk_text_with_sentences(full_text)
        if not chunks:
            continue

        embeddings = model.encode(chunks, normalize_embeddings=True).astype("float32")

        if faiss_index is None:
            faiss_index = faiss.IndexFlatL2(embeddings.shape[1])

        faiss_index.add(embeddings)

        for i, chunk in enumerate(chunks):
            chunk_metadata.append({
                "ref_no":      ref_no,
                "title":       title,
                "issue_date":  issue_date,
                "pdf_url":     pdf_url,
                "chunk_index": i,
                "chunk_text":  chunk
            })
            bm25_corpus.append(chunk.lower().split())

    faiss.write_index(faiss_index, FAISS_INDEX_PATH)

    with open(CHUNK_META_PATH, "w", encoding="utf-8") as f:
        json.dump(chunk_metadata, f, indent=2)

    bm25 = BM25Okapi(bm25_corpus)
    bm25_data = {
        "corpus":    bm25_corpus,
        "doc_freqs": list(bm25.doc_freqs),
        "idf":       {k: v for k, v in bm25.idf.items()},
        "avgdl":     bm25.avgdl,
        "doc_len":   list(bm25.doc_len)
    }
    with open(BM25_PATH, "w", encoding="utf-8") as f:
        json.dump(bm25_data, f)


# ──────────────────────────────────────────────────────────────────────────────
# RETRIEVER MODULE
# ──────────────────────────────────────────────────────────────────────────────

class HybridRetriever:
    def __init__(self):
        self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        with open(BM25_PATH, "r", encoding="utf-8") as f:
            bm25_data = json.load(f)

        self.bm25_corpus = bm25_data["corpus"]
        self.bm25         = BM25Okapi(self.bm25_corpus)
        self.embed_model  = SentenceTransformer(EMBED_MODEL_NAME)

    def retrieve_semantic(self, query: str, top_k=INITIAL_TOP_K):
        query_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
        distances, indices = self.faiss_index.search(query_emb, top_k)
        results = []
        for rank, idx in enumerate(indices[0]):
            if idx < len(self.metadata):
                r = self.metadata[idx].copy()
                r["semantic_score"] = float(1 / (1 + distances[0][rank]))
                results.append(r)
        return results

    def retrieve_bm25(self, query: str, top_k=INITIAL_TOP_K):
        tokens = query.lower().split()
        scores = self.bm25.get_scores(tokens)
        top_indices = np.argsort(scores)[-top_k:][::-1]
        results = []
        for idx in top_indices:
            if idx < len(self.metadata):
                r = self.metadata[idx].copy()
                r["bm25_score"] = float(scores[idx])
                results.append(r)
        return results

    def hybrid_retrieve(self, query: str, top_k=INITIAL_TOP_K, alpha: float = 0.7):
        sem = self.retrieve_semantic(query, top_k)
        bm  = self.retrieve_bm25(query, top_k)

        merged = {}
        for r in sem:
            key = r["chunk_text"]
            merged[key] = {**r, "bm25_score": 0.0}
        for r in bm:
            key = r["chunk_text"]
            if key in merged:
                merged[key]["bm25_score"] = r["bm25_score"]
            else:
                merged[key] = {**r, "semantic_score": 0.0}

        results = list(merged.values())
        if results:
            max_sem = max(r["semantic_score"] for r in results)
            max_bm  = max(r["bm25_score"] for r in results)
            for r in results:
                norm_sem = r["semantic_score"] / max_sem if max_sem > 0 else 0
                norm_bm  = r["bm25_score"]/ max_bm  if max_bm  > 0 else 0
                r["hybrid_score"] = alpha*norm_sem + (1-alpha)*norm_bm

        results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return results[:top_k]


# ──────────────────────────────────────────────────────────────────────────────
# RERANKER MODULE
# ──────────────────────────────────────────────────────────────────────────────

class Reranker:
    def __init__(self):
        self.model = CrossEncoder(RERANK_MODEL_NAME)

    def rerank(self, query: str, chunks: List[Dict], top_k=RERANK_TOP_K):
        if not chunks:
            return []
        pairs = [[query, c["chunk_text"]] for c in chunks]
        scores = self.model.predict(pairs)
        for c, score in zip(chunks, scores):
            c["rerank"] = float(score)
        return sorted(chunks, key=lambda x: x["rerank"], reverse=True)[:top_k]


# ──────────────────────────────────────────────────────────────────────────────
# QUERY PROCESSING & SUGGESTIONS
# ──────────────────────────────────────────────────────────────────────────────

def preprocess_query(query: str, history: List[Dict]) -> str:
    """Rewrite vague / short / incomplete queries."""
    q = query.strip()
    if len(q.split()) <= 3 or not q.endswith("?"):
        prompt = f"Rewrite into a clear question:\n{q}"
        try:
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            rewritten = res.text.strip()
            if rewritten:
                return rewritten
        except:
            pass
        return q + "?"
    return q

def generate_suggestions(query: str, retriever: HybridRetriever, top_n=5):
    """Generate suggestions for related queries."""
    tokens = query.lower().split()
    suggestions = set()
    for t in tokens:
        for chunk in retriever.bm25_corpus:
            if t in chunk:
                suggestions.update(chunk[:5])
                if len(suggestions) >= top_n:
                    break
        if len(suggestions) >= top_n:
            break
    return list(suggestions)[:top_n]


# ──────────────────────────────────────────────────────────────────────────────
# ANSWER GENERATION & EVALUATION
# ──────────────────────────────────────────────────────────────────────────────

def build_history_prompt(history):
    parts = []
    for turn in history[-3:]:
        parts.append(f"Q: {turn['question']}\nA: {turn['answer']}")
    return "\n\n".join(parts)

def evaluate_answer(answer, context):
    judge_prompt = f"Judge whether the answer is fully supported by the context.\nContext:\n{context}\nAnswer:\n{answer}"
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        res = client.models.generate_content(model=GEMINI_MODEL, contents=judge_prompt)
        return res.text.strip()
    except:
        return "Evaluation unavailable."


def generate_answer(query, chunks, history):
    context = "\n\n".join(f"[{i+1}] {c['chunk_text']}" for i,c in enumerate(chunks[:TOP_K_TO_SEND]))
    history_prompt = build_history_prompt(history) if history else ""
    prompt = f"""
You are an RBI circular expert.

Previous:
{history_prompt}

Context:
{context}

Question:
{query}

Answer with citations.
"""
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return res.text.strip()
    except Exception as e:
        return f"Error: {e}"


def rag_pipeline(query, retriever, reranker, history):
    q = preprocess_query(query, history)
    suggestions = generate_suggestions(q, retriever)

    retrieved = retriever.hybrid_retrieve(q)
    reranked  = reranker.rerank(q, retrieved)

    answer = generate_answer(q, reranked, history)
    eval_report = evaluate_answer(answer, "\n".join(c["chunk_text"] for c in reranked[:TOP_K_TO_SEND]))

    return {
        "query_used":      q,
        "suggestions":     suggestions,
        "answer":          answer,
        "evaluation":      eval_report,
        "sources":         reranked
    }


# ──────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI
# ──────────────────────────────────────────────────────────────────────────────

def run_streamlit_app():
    st.set_page_config(page_title="RBI Circular RAG", layout="wide")
    st.title("🏦 RBI Circular Q&A with Suggestions & Evaluation")
    st.write("Ask anything from the RBI circular database.")

    if "history" not in st.session_state:
        st.session_state.history = []

    if "query_text" not in st.session_state:
        st.session_state.query_text = ""

    if "trigger_query" not in st.session_state:
        st.session_state.trigger_query = False

    if "retriever" not in st.session_state:
        with st.spinner("Loading models..."):
            st.session_state.retriever = HybridRetriever()
            st.session_state.reranker  = Reranker()
            st.success("Models loaded.")

    def submit():
        st.session_state.trigger_query = True

    query_input = st.text_input(
        "Enter your question:",
        key="query_text",
        on_change=submit
    )

    if st.session_state.trigger_query and query_input.strip():
        with st.spinner("Generating answer..."):
            result = rag_pipeline(
                st.session_state.query_text,
                st.session_state.retriever,
                st.session_state.reranker,
                st.session_state.history
            )

            st.session_state.history.append({
                "question": result["query_used"],
                "answer":   result["answer"],
                "sources":  result["sources"],
                "context_chunks": result["sources"]
            })

            st.session_state.trigger_query = False
            st.session_state.query_text = ""

            st.experimental_rerun()

    if st.session_state.history:
        st.markdown("---")
        for i, turn in enumerate(reversed(st.session_state.history), 1):
            st.markdown(f"### Q{i}: {turn['question']}")
            st.markdown(turn["answer"])

            with st.expander("📚 Sources"):
                for j, src in enumerate(turn["sources"], 1):
                    st.markdown(f"**{j}. {src['title']}** (Ref: {src['ref_no']})")
                    st.text(src["chunk_text"][:200] + "...")

            st.markdown("---")

    st.sidebar.markdown("## Suggestions")
    if st.session_state.history:
        last_q = st.session_state.history[-1]["question"]
        sug = generate_suggestions(last_q, st.session_state.retriever)
        for s in sug:
            if st.button(f"Try: {s}"):
                st.session_state.query_text = s
                submit()

if __name__ == "__main__":
    run_streamlit_app()
