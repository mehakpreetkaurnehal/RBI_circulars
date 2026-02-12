import streamlit as st
import sqlite3
import os
import re
import json
import faiss
import numpy as np

from datetime import datetime
from sentence_transformers import SentenceTransformer, CrossEncoder              
from rank_bm25 import BM25Okapi
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ───────────────────────────────────────────────────────────────
# Settings
# ───────────────────────────────────────────────────────────────

CHAT_DB_PATH = "hist_stored.db"
FAISS_DIR = "rbi_scrape_text_fixed"
FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

MAX_SOURCES = 6
INITIAL_TOP_K = 50
RERANK_TOP_K = 20

# ───────────────────────────────────────────────────────────────
# Initialize Chat DB
# ───────────────────────────────────────────────────────────────

def init_chat_db():
    conn = sqlite3.connect(CHAT_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        question TEXT,
        answer TEXT,
        sources TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

init_chat_db()

def save_chat(session_id, question, answer, sources):
    conn = sqlite3.connect(CHAT_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_history (session_id, question, answer, sources, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, question, answer, json.dumps(sources), datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

def load_sessions():
    conn = sqlite3.connect(CHAT_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT session_id, id, question, answer, sources FROM chat_history ORDER BY created_at ASC"
    )
    rows = cur.fetchall()
    conn.close()

    sessions = {}
    for sid, cid, q, a, src in rows:
        sessions.setdefault(sid, []).append((cid, q, a, src))
    return sessions

# ───────────────────────────────────────────────────────────────
# Retriever + Reranker
# ───────────────────────────────────────────────────────────────

class HybridRetriever:
    def __init__(self):
        self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        with open(BM25_PATH, "r", encoding="utf-8") as f:
            bm25_data = json.load(f)
        self.bm25 = BM25Okapi(bm25_data["corpus"])
        self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)

    def retrieve_semantic(self, query, top_k=INITIAL_TOP_K):
        query_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
        dists, idxs = self.faiss_index.search(query_emb, top_k)
        results = []
        for dist, idx in zip(dists[0], idxs[0]):
            if idx < len(self.metadata):
                doc = self.metadata[idx].copy()
                doc["semantic_score"] = float(1/(1 + dist))
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
            merged[r["chunk_text"]] = {**r, "bm25_score":0}
        for r in bm25:
            key = r["chunk_text"]
            if key in merged:
                merged[key]["bm25_score"] = r["bm25_score"]
            else:
                merged[key] = {**r, "semantic_score":0}

        combined = list(merged.values())
        if combined:
            max_sem = max(r["semantic_score"] for r in combined)
            max_bm  = max(r["bm25_score"] for r in combined)
            for r in combined:
                ns = r["semantic_score"] / max_sem if max_sem else 0
                nb = r["bm25_score"] / max_bm if max_bm else 0
                r["hybrid_score"] = 0.7*ns + 0.3*nb

        combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return combined[:INITIAL_TOP_K]

class Reranker:
    def __init__(self):
        self.model = CrossEncoder(RERANK_MODEL_NAME)

    def rerank(self, query, chunks):
        if not chunks:
            return []
        scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])
        for c, s in zip(chunks, scores):
            c["rerank_score"] = float(s)
        return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:RERANK_TOP_K]

# ───────────────────────────────────────────────────────────────
# RAG Pipeline
# ───────────────────────────────────────────────────────────────

def generate_answer(query, reranked, history):
    context_text = ""
    for i, c in enumerate(reranked[:6], 1):
        context_text += f"[{i}] {c['chunk_text']}\n"

    history_txt = ""
    for q, a, _ in history[-3:]:
        history_txt += f"Q: {q}\nA: {a}\n"

    prompt = f"""
You are an expert RBI regulatory assistant.

History:
{history_txt}

Context:
{context_text}

Question:
{query}

Answer concisely with citation references if available.
"""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return res.text.strip()
    except Exception as e:
        return f"LLM Error: {e}"

def rag_pipeline(query, retriever, reranker, history):
    hybrid = retriever.hybrid_retrieve(query)
    reranked = reranker.rerank(query, hybrid)

    answer_text = generate_answer(query, reranked, history)

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

# ───────────────────────────────────────────────────────────────
# Streamlit UI
# ───────────────────────────────────────────────────────────────

def run_app():
    st.set_page_config(layout="wide", page_title="RBI Circular QA Assistant")

    if "retriever" not in st.session_state:
        with st.spinner("Loading models..."):
            st.session_state.retriever = HybridRetriever()
            st.session_state.reranker  = Reranker()

    sessions = load_sessions()

    with st.sidebar:
        st.markdown("## 🧠 Chat Sessions")
        if st.button("🆕 New Chat"):
            new_session_id = datetime.utcnow().isoformat()
            st.session_state.active_session = new_session_id

        for sid in sessions:
            if st.button(f"Session: {sid}", key=sid):
                st.session_state.active_session = sid

    active = st.session_state.get("active_session", None)
    if active not in sessions:
        sessions[active] = []

    st.markdown(f"## Session — {active}")

    for cid, q, ans, src_json in sessions[active]:
        st.markdown(f"**Q:** {q}")
        st.markdown(ans)

        sources = json.loads(src_json)
        if sources:
            with st.expander("📚 Sources"):
                for url, title in sources.items():
                    st.markdown(f"📄 {title} [🔗]({url})")

        st.write("---")

    st.markdown("""
<style>
.fixed-bottom {
  position: fixed;
  bottom: 10px;
  width: 98%;
}
</style>
""", unsafe_allow_html=True)

    with st.form(key="input_form", clear_on_submit=True):
        query = st.text_input("Ask your question:")
        submitted = st.form_submit_button("Submit")
        if submitted and query:
            history = [(h[1], h[2], h[3]) for h in sessions[active]]
            res = rag_pipeline(
                query.strip(),
                st.session_state.retriever,
                st.session_state.reranker,
                history
            )
            save_chat(active, res["question"], res["answer"], res["sources"])
            st.rerun()

if __name__ == "__main__":
    run_app()
