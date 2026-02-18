"""
FastAPI Backend for RBI Circular QA Assistant
==============================================
This file wraps your existing RAG pipeline (FAISS, BM25, Reranker, Gemini)
and exposes REST API endpoints for the React frontend.

SETUP:
1. Place this file in the same directory as your `rbi_scrape_text_fixed/` folder
2. Install dependencies:
   pip install fastapi uvicorn google-genai faiss-cpu sentence-transformers rank_bm25 python-dotenv
3. Create .env with: GEMINI_API_KEY=your_key_here
4. Run: uvicorn backend_api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import json
import sqlite3
import numpy as np
import faiss

from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
FAISS_DIR = "rbi_scrape_text_fixed"
FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

CHAT_DB_PATH = "chat_history.db"
MAX_SOURCES = 6
INITIAL_TOP_K = 50
RERANK_TOP_K = 20


# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(CHAT_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question TEXT,
            answer TEXT,
            sources TEXT,
            created_at TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(CHAT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────
# Retriever + Reranker (same as your Streamlit code)
# ─────────────────────────────────────────────
class HybridRetriever:
    def __init__(self):
        print("Loading FAISS index...")
        self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        print(f"FAISS index loaded: {self.faiss_index.ntotal} vectors")

        with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        print(f"Metadata loaded: {len(self.metadata)} chunks")

        with open(BM25_PATH, "r", encoding="utf-8") as f:
            bm25_data = json.load(f)
        self.bm25 = BM25Okapi(bm25_data["corpus"])
        print("BM25 index loaded")

        print(f"Loading embedding model: {EMBED_MODEL_NAME}")
        self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        print("Embedding model loaded")

    def retrieve_semantic(self, query, top_k=INITIAL_TOP_K):
        query_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
        dists, idxs = self.faiss_index.search(query_emb, top_k)
        results = []
        for dist, idx in zip(dists[0], idxs[0]):
            if idx < len(self.metadata):
                doc = self.metadata[idx].copy()
                doc["semantic_score"] = float(1 / (1 + dist))
                results.append(doc)
        return results

    def retrieve_bm25(self, query, top_k=INITIAL_TOP_K):
        tokens = query.lower().split()
        scores = self.bm25.get_scores(tokens)
        top_idxs = np.argsort(scores)[-top_k:][::-1]
        results = []
        for i in top_idxs:
            if i < len(self.metadata):
                doc = self.metadata[i].copy()
                doc["bm25_score"] = float(scores[i])
                results.append(doc)
        return results

    def hybrid_retrieve(self, query):
        sem = self.retrieve_semantic(query)
        bm25 = self.retrieve_bm25(query)
        merged = {}
        for r in sem:
            merged[r["chunk_text"]] = {**r, "bm25_score": 0}
        for r in bm25:
            key = r["chunk_text"]
            if key in merged:
                merged[key]["bm25_score"] = r["bm25_score"]
            else:
                merged[key] = {**r, "semantic_score": 0}
        combined = list(merged.values())
        if combined:
            max_sem = max(r["semantic_score"] for r in combined)
            max_bm = max(r["bm25_score"] for r in combined)
            for r in combined:
                ns = r["semantic_score"] / max_sem if max_sem else 0
                nb = r["bm25_score"] / max_bm if max_bm else 0
                r["hybrid_score"] = 0.7 * ns + 0.3 * nb
        combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return combined[:INITIAL_TOP_K]


class Reranker:
    def __init__(self):
        print(f"Loading reranker: {RERANK_MODEL_NAME}")
        self.model = CrossEncoder(RERANK_MODEL_NAME)
        print("Reranker loaded")

    def rerank(self, query, chunks):
        if not chunks:
            return []
        scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])
        for c, s in zip(chunks, scores):
            c["rerank_score"] = float(s)
        return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:RERANK_TOP_K]


# ─────────────────────────────────────────────
# RAG Pipeline
# ─────────────────────────────────────────────
def build_history_context(history):
    parts = []
    for item in history[-3:]:
        parts.append(f"Q: {item['question']}\nA: {item['answer']}")
    return "\n\n".join(parts)


def generate_answer(query, reranked, history):
    context_text = ""
    for i, c in enumerate(reranked[:5], 1):
        context_text += f"[{i}] {c['chunk_text']}\n"

    hist_txt = build_history_context(history) if history else ""

    prompt = f"""
You are an expert RBI regulatory assistant. You must ONLY answer based on the provided context from RBI circulars.
If the context does not contain relevant information, say "I don't have information about this in the available RBI circulars."

Previous Conversation:
{hist_txt}

Context from RBI Circulars:
{context_text}

Question:
{query}

Answer concisely with citation references like [1], [2] etc. referring to the context numbers above.
"""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return res.text.strip()
    except Exception as e:
        return f"LLM Error: {e}"


def rag_pipeline(query, retriever, reranker, history):
    reranked = reranker.rerank(query, retriever.hybrid_retrieve(query))
    answer_text = generate_answer(query, reranked, history)

    # If irrelevant, no sources
    if "no information" in answer_text.lower() or "don't have information" in answer_text.lower():
        return {"question": query, "answer": answer_text, "sources": {}}

    unique_sources = {}
    count = 0
    for c in reranked:
        if count >= MAX_SOURCES:
            break
        url = c.get("pdf_url")
        title = c.get("title", "RBI Circular")
        if url and url not in unique_sources:
            unique_sources[url] = title
            count += 1

    return {"question": query, "answer": answer_text, "sources": unique_sources}


# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────

# Global model instances
retriever = None
reranker_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global retriever, reranker_instance
    print("=" * 50)
    print("Starting RBI Circular QA Backend...")
    print("=" * 50)
    init_db()
    retriever = HybridRetriever()
    reranker_instance = Reranker()
    print("=" * 50)
    print("Backend ready! Accepting requests.")
    print("=" * 50)
    yield
    print("Shutting down...")


app = FastAPI(
    title="RBI Circular QA API",
    description="RAG-based QA system for RBI Circulars",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str
    session_id: str
    history: Optional[list[dict]] = []


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: dict


# ─────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    chunks_loaded = len(retriever.metadata) if retriever else 0
    return {
        "status": "healthy",
        "chunks_loaded": chunks_loaded,
        "model": GEMINI_MODEL,
    }


@app.post("/api/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if not retriever or not reranker_instance:
        raise HTTPException(status_code=503, detail="Models not loaded yet")

    # Run RAG pipeline
    result = rag_pipeline(
        req.question.strip(),
        retriever,
        reranker_instance,
        req.history or [],
    )

    # Save to database
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cur = conn.cursor()

    # Create session if it doesn't exist
    cur.execute("SELECT session_id FROM sessions WHERE session_id = ?", (req.session_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (req.session_id, req.question[:50], now, now),
        )
    else:
        cur.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, req.session_id),
        )

    # Save message
    cur.execute(
        "INSERT INTO messages (session_id, question, answer, sources, created_at) VALUES (?, ?, ?, ?, ?)",
        (req.session_id, result["question"], result["answer"], json.dumps(result["sources"]), now),
    )
    conn.commit()
    conn.close()

    return AskResponse(
        question=result["question"],
        answer=result["answer"],
        sources=result["sources"],
    )


@app.get("/api/sessions")
async def get_sessions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
    sessions = []
    for row in cur.fetchall():
        cur2 = conn.cursor()
        cur2.execute(
            "SELECT id, question, answer, sources, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (row["session_id"],),
        )
        messages = []
        for msg in cur2.fetchall():
            messages.append({
                "id": msg["id"],
                "question": msg["question"],
                "answer": msg["answer"],
                "sources": json.loads(msg["sources"]),
                "created_at": msg["created_at"],
            })
        sessions.append({
            "session_id": row["session_id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "messages": messages,
        })
    conn.close()
    return sessions


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    cur.execute(
        "SELECT id, question, answer, sources, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    )
    messages = []
    for msg in cur.fetchall():
        messages.append({
            "id": msg["id"],
            "question": msg["question"],
            "answer": msg["answer"],
            "sources": json.loads(msg["sources"]),
            "created_at": msg["created_at"],
        })
    conn.close()

    return {
        "session_id": row["session_id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "messages": messages,
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cur.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


@app.delete("/api/sessions")
async def clear_all_sessions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages")
    cur.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
