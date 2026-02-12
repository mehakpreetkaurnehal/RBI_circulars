import streamlit as st
import os, re, json, sqlite3, faiss
import numpy as np
from datetime import datetime
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from google import genai
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "rbi_scrape_text.db"
FAISS_DIR = "rbi_scrape_text_fixed"
FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
CHUNK_META_PATH  = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
BM25_PATH        = os.path.join(FAISS_DIR, "bm25_index.json")

EMBED_MODEL_NAME  = "sentence-transformers/all-mpnet-base-v2"
RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

CHUNK_SIZE    = 512
CHUNK_OVERLAP = 100
INITIAL_TOP_K = 50
RERANK_TOP_K  = 20

os.makedirs(FAISS_DIR, exist_ok=True)

def sanitize(text: str) -> str:
    """Clean text of extra whitespace."""
    return re.sub(r"\s+", " ", text).strip()

def build_suggestion_terms(chunks):
    """Precompute suggestion list from titles and chunk keywords."""
    terms = set()
    for c in chunks:
        title = c.get("title", "")
        terms.add(title)
        for w in title.split():
            if len(w) > 2:
                terms.add(w.lower())
    return list(terms)

def get_suggestions(prefix, terms, max_s=6):
    """Return suggestions matching the typed prefix."""
    prefix = prefix.lower()
    return [t for t in terms if t.lower().startswith(prefix)][:max_s]

class HybridRetriever:
    def __init__(self):
        # Load FAISS
        self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        # Load BM25
        with open(BM25_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.bm25_corpus = data["corpus"]
        self.bm25 = BM25Okapi(self.bm25_corpus)

        # Embedding model
        self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)

        # Precompute suggestion terms
        self.suggestion_terms = build_suggestion_terms(self.metadata)

    def retrieve_semantic(self, query, top_k=INITIAL_TOP_K):
        q_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
        dists, idxs = self.faiss_index.search(q_emb, top_k)
        results = []
        for rank, idx in enumerate(idxs[0]):
            if idx < len(self.metadata):
                m = self.metadata[idx].copy()
                m["semantic_score"] = float(1 / (1 + dists[0][rank]))
                results.append(m)
        return results

    def retrieve_bm25(self, query, top_k=INITIAL_TOP_K):
        tokens = query.lower().split()
        scores = self.bm25.get_scores(tokens)
        top_idxs = np.argsort(scores)[-top_k:][::-1]
        results = []
        for idx in top_idxs:
            if idx < len(self.metadata):
                m = self.metadata[idx].copy()
                m["bm25_score"] = float(scores[idx])
                results.append(m)
        return results

    def hybrid_retrieve(self, query, alpha=0.7):
        sem = self.retrieve_semantic(query)
        bm  = self.retrieve_bm25(query)

        combined = {}
        for r in sem:
            combined[r["chunk_text"]] = {**r, "bm25_score":0}
        for r in bm:
            key = r["chunk_text"]
            if key in combined:
                combined[key]["bm25_score"] = r["bm25_score"]
            else:
                combined[key] = {**r, "semantic_score":0}

        results = list(combined.values())
        if results:
            max_sem = max(r["semantic_score"] for r in results)
            max_bm  = max(r["bm25_score"] for r in results)
            for r in results:
                ns = r["semantic_score"]/max_sem if max_sem else 0
                nb = r["bm25_score"]/max_bm  if max_bm  else 0
                r["hybrid_score"] = alpha*ns + (1-alpha)*nb

        results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return results[:INITIAL_TOP_K]

class Reranker:
    def __init__(self):
        self.model = CrossEncoder(RERANK_MODEL_NAME)

    def rerank(self, query, chunks):
        if not chunks:
            return []
        pairs = [[query, c["chunk_text"]] for c in chunks]
        scores = self.model.predict(pairs)
        for c, s in zip(chunks, scores):
            c["rerank_score"] = float(s)
        return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:RERANK_TOP_K]


def build_history_prompt(history):
    """Build context for followups."""
    parts = []
    for turn in history[-4:]:
        parts.append(f"Q: {turn['question']}\nA: {turn['answer']}")
    return "\n\n".join(parts)

def evaluate_answer(answer, context):
    """Ask LLM to judge groundedness."""
    judge_prompt = (
        f"Check if every statement in the answer is supported by the context.\n"
        f"Context:\n{context}\nAnswer:\n{answer}"
    )
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        res = client.models.generate_content(model=GEMINI_MODEL, contents=judge_prompt)
        return res.text.strip()
    except:
        return "Unavailable"


def generate_answer(query, reranked, history):
    context = "\n\n".join(f"[{i+1}] {c['chunk_text']}" for i,c in enumerate(reranked[:8]))
    hist = build_history_prompt(history) if history else ""
    prompt = f"""
You are an expert RBI assistant.

History:
{hist}

Context:
{context}

Question:
{query}

Answer accurately with citations.
"""

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return res.text.strip()
    except Exception as e:
        return f"Error: {e}"


def rag_pipeline(query, retriever, reranker, history):
    # Retrieve and re-rank
    retrieved = retriever.hybrid_retrieve(query)
    reranked  = reranker.rerank(query, retrieved)

    # Generate answer
    answer = generate_answer(query, reranked, history)
    eval_rep = evaluate_answer(answer, "\n".join(c["chunk_text"] for c in reranked[:8]))

    return {
        "query": query,
        "answer": answer,
        "evaluation": eval_rep,
        "sources": reranked
    }

def run_app():
    st.set_page_config(page_title="RBI Circular Chat", layout="wide")
    st.title("🏦 RBI Circular Q&A Chat")

    if "history" not in st.session_state:
        st.session_state.history = []

    if "query" not in st.session_state:
        st.session_state.query = ""

    if "submit" not in st.session_state:
        st.session_state.submit = False

    if "suggestions" not in st.session_state:
        st.session_state.suggestions = []

    if "retriever" not in st.session_state:
        with st.spinner("Loading models…"):
            st.session_state.retriever = HybridRetriever()
            st.session_state.reranker  = Reranker()

    # Sidebar history
    with st.sidebar:
        st.header("📜 Chat History")
        for i, turn in enumerate(st.session_state.history):
            st.markdown(f"**{i+1}. {turn['question']}**")
            st.write(turn['answer'])

    # Suggestion logic
    user_input = st.text_input("Ask a question:", value=st.session_state.query, key="chat_input")

    if user_input.strip():
        st.session_state.suggestions = get_suggestions(user_input, st.session_state.retriever.suggestion_terms)

    # Show suggestions below box
    if st.session_state.suggestions:
        cols = st.columns(len(st.session_state.suggestions))
        for idx, sug in enumerate(st.session_state.suggestions):
            if cols[idx].button(sug):
                st.session_state.query = sug
                st.session_state.submit = True

    # Submit on Enter
    if st.button("Submit") or st.session_state.submit:
        query = user_input.strip()
        if query:
            with st.spinner("Thinking..."):
                result = rag_pipeline(query, st.session_state.retriever, st.session_state.reranker, st.session_state.history)

                st.session_state.history.append({
                    "question": query,
                    "answer": result["answer"],
                    "sources": result["sources"]
                })

                st.session_state.query = ""
                st.session_state.submit = False

                st.rerun()

    # Show chat messages
    st.markdown("---")
    for i, turn in enumerate(st.session_state.history[-5:]):
        st.markdown(f"**User:** {turn['question']}")
        st.markdown(f"**AI:** {turn['answer']}")
        st.write(f"🧠 Eval: {turn.get('evaluation','—')}")

        with st.expander("Sources"):
            for j, s in enumerate(turn['sources'],1):
                st.write(f"{j}. {s['title']} ({s['ref_no']})")
                st.write(s['chunk_text'][:200] + "...")

if __name__ == "__main__":
    run_app()
