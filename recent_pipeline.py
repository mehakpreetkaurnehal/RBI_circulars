# # Feb 13, 2026: working well but needs improvements

# import streamlit as st
# import os
# import re
# import json
# import sqlite3
# import faiss
# import numpy as np
# from datetime import datetime
# from sentence_transformers import SentenceTransformer, CrossEncoder
# from rank_bm25 import BM25Okapi
# from google import genai
# from dotenv import load_dotenv

# load_dotenv()

# CHAT_DB_PATH = "Changed.db"

# FAISS_DIR = "rbi_scrape_text_fixed"
# FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
# CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
# BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

# EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
# RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# def normalize_text(text: str) -> str:
#     text = text.lower()
#     text = re.sub(r"[^\w\s]", " ", text)  # remove punctuation
#     text = re.sub(r"\s+", " ", text).strip()
#     return text


# def tokenize_with_ngrams(text: str, use_bigrams: bool):
#     words = normalize_text(text).split()
#     if not use_bigrams:
#         return words

#     bigrams = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
#     return words + bigrams


# def coverage_score(query: str, text: str) -> float:
#     q_words = set(normalize_text(query).split())
#     t_words = set(normalize_text(text).split())
#     if not q_words:
#         return 0.0
#     return len(q_words & t_words) / len(q_words)


# def init_chat_db():
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute("""
#     CREATE TABLE IF NOT EXISTS chat_history (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         question TEXT,
#         answer TEXT,
#         sources TEXT,
#         created_at TEXT
#     )
#     """)
#     conn.commit()
#     conn.close()

# init_chat_db()


# def save_chat(question, answer, sources):
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute(
#         "INSERT INTO chat_history (question, answer, sources, created_at) VALUES (?, ?, ?, ?)",
#         (question, answer, json.dumps(sources), datetime.utcnow().isoformat())
#     )
#     conn.commit()
#     conn.close()


# def load_chat_history():
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute(
#         "SELECT id, question, answer, sources FROM chat_history ORDER BY id ASC"
#     )
#     rows = cur.fetchall()
#     conn.close()
#     return rows


# class HybridRetriever:
#     def __init__(self):
#         self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)

#         with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
#             self.metadata = json.load(f)

#         with open(BM25_PATH, "r", encoding="utf-8") as f:
#             bm25_data = json.load(f)

#         self.bm25 = BM25Okapi(bm25_data["corpus"])
#         self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)

#     # ---------------- SEMANTIC ----------------

#     def retrieve_semantic(self, query, top_k):
#         clean_query = normalize_text(query)

#         query_emb = self.embed_model.encode(
#             [clean_query],
#             normalize_embeddings=True
#         ).astype("float32")

#         dists, idxs = self.faiss_index.search(query_emb, top_k)

#         results = []
#         for dist, idx in zip(dists[0], idxs[0]):
#             if idx < len(self.metadata):
#                 doc = self.metadata[idx].copy()
#                 doc["semantic_score"] = float(1 / (1 + dist))
#                 results.append(doc)

#         return results

#     # ---------------- BM25 ----------------

#     def retrieve_bm25(self, query, top_k, use_bigrams):
#         tokens = tokenize_with_ngrams(query, use_bigrams)

#         scores = self.bm25.get_scores(tokens)
#         top_idxs = np.argsort(scores)[-top_k:][::-1]

#         results = []
#         for i in top_idxs:
#             if i < len(self.metadata):
#                 doc = self.metadata[i].copy()
#                 doc["bm25_score"] = float(scores[i])
#                 results.append(doc)

#         return results

#     # ---------------- HYBRID ----------------

#     def hybrid_retrieve(
#         self,
#         query,
#         top_k,
#         use_bigrams,
#         w_semantic,
#         w_bm25,
#         w_coverage
#     ):
#         sem = self.retrieve_semantic(query, top_k)
#         bm25 = self.retrieve_bm25(query, top_k, use_bigrams)

#         merged = {}

#         for r in sem:
#             merged[r["chunk_text"]] = {**r, "bm25_score": 0}

#         for r in bm25:
#             key = r["chunk_text"]
#             if key in merged:
#                 merged[key]["bm25_score"] = r["bm25_score"]
#             else:
#                 merged[key] = {**r, "semantic_score": 0}

#         combined = list(merged.values())

#         if combined:
#             max_sem = max(r["semantic_score"] for r in combined)
#             max_bm = max(r["bm25_score"] for r in combined)

#             for r in combined:
#                 ns = r["semantic_score"] / max_sem if max_sem else 0
#                 nb = r["bm25_score"] / max_bm if max_bm else 0
#                 cov = coverage_score(query, r["chunk_text"])

#                 r["hybrid_score"] = (
#                     w_semantic * ns +
#                     w_bm25 * nb +
#                     w_coverage * cov
#                 )

#         combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
#         return combined[:top_k]


# class Reranker:
#     def __init__(self):
#         self.model = CrossEncoder(RERANK_MODEL_NAME)

#     def rerank(self, query, chunks, top_k):
#         if not chunks:
#             return []

#         scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])

#         for c, s in zip(chunks, scores):
#             c["rerank_score"] = float(s)

#         return sorted(
#             chunks,
#             key=lambda x: x["rerank_score"],
#             reverse=True
#         )[:top_k]


# def generate_answer(query, reranked, history):
#     context_text = ""

#     for i, c in enumerate(reranked[:5], 1):
#         context_text += f"[{i}] {c['chunk_text']}\n"

#     prompt = f"""
# You are an expert RBI regulatory assistant.

# STRICT RULES:
# - Consider all words in the question together
# - Do not answer using partial keyword matches
# - Use only the provided context
# - If not found, say: Information not available

# Context:
# {context_text}

# Question:
# {query}

# Answer:
# """

#     client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

#     try:
#         res = client.models.generate_content(
#             model=GEMINI_MODEL,
#             contents=prompt
#         )
#         return res.text.strip()
#     except Exception as e:
#         return f"LLM Error: {e}"

# def rag_pipeline(query, retriever, reranker, params):
#     hybrid = retriever.hybrid_retrieve(
#         query=query,
#         top_k=params["initial_top_k"],
#         use_bigrams=params["use_bigrams"],
#         w_semantic=params["w_semantic"],
#         w_bm25=params["w_bm25"],
#         w_coverage=params["w_coverage"],
#     )

#     reranked = reranker.rerank(
#         query,
#         hybrid,
#         params["rerank_top_k"]
#     )

#     answer_text = generate_answer(query, reranked, [])

#     unique_sources = {}
#     for c in reranked:
#         url = c.get("pdf_url")
#         title = c.get("title", "RBI Circular")
#         if url:
#             unique_sources[url] = title

#     return {
#         "question": query,
#         "answer": answer_text,
#         "sources": unique_sources
#     }


# # =========================================================
# # STREAMLIT UI
# # =========================================================

# def run_app():
#     st.set_page_config(page_title="RBI Circular QA", layout="wide")
#     st.title("🏦 RBI Circular QA Assistant")

#     # ---------- SIDEBAR CONTROLS ----------

#     st.sidebar.header("⚙️ Retrieval Controls")

#     use_bigrams = st.sidebar.checkbox("Enable BM25 Bigrams", value=False)

#     w_semantic = st.sidebar.slider("Semantic Weight", 0.0, 1.0, 0.6)
#     w_bm25 = st.sidebar.slider("BM25 Weight", 0.0, 1.0, 0.25)
#     w_coverage = st.sidebar.slider("Coverage Weight", 0.0, 1.0, 0.15)

#     initial_top_k = st.sidebar.slider("Initial Top-K", 10, 30, 15)
#     rerank_top_k = st.sidebar.slider("Rerank Top-K", 5, 50, 20)

#     params = {
#         "use_bigrams": use_bigrams,
#         "w_semantic": w_semantic,
#         "w_bm25": w_bm25,
#         "w_coverage": w_coverage,
#         "initial_top_k": initial_top_k,
#         "rerank_top_k": rerank_top_k,
#     }

#     # ---------- LOAD MODELS ----------

#     if "retriever" not in st.session_state:
#         with st.spinner("Loading models..."):
#             st.session_state.retriever = HybridRetriever()
#             st.session_state.reranker = Reranker()

#     history_db = load_chat_history()

#     # ---------- CHAT DISPLAY ----------

#     for cid, q, ans, src_json in history_db:
#         sources = json.loads(src_json)

#         st.markdown(f"**Q:** {q}")
#         st.markdown(ans)

#         if sources:
#             with st.expander("📚 Sources"):
#                 for url, title in sources.items():
#                     st.markdown(f"📄 {title} [🔗]({url})")

#         st.write("---")

#     # ---------- INPUT ----------

#     with st.form("ask_form", clear_on_submit=True):
#         query = st.text_input("Ask a new question:")
#         submitted = st.form_submit_button("Submit")

#         if submitted and query.strip():
#             with st.spinner("Generating answer..."):
#                 res = rag_pipeline(
#                     query.strip(),
#                     st.session_state.retriever,
#                     st.session_state.reranker,
#                     params
#                 )

#                 save_chat(res["question"], res["answer"], res["sources"])
#                 st.rerun()


# if __name__ == "__main__":
#     run_app()




# import streamlit as st
# import os
# import re
# import json
# import sqlite3
# import faiss
# import numpy as np
# from datetime import datetime
# from sentence_transformers import SentenceTransformer, CrossEncoder
# from rank_bm25 import BM25Okapi
# from google import genai
# from dotenv import load_dotenv

# load_dotenv()

# CHAT_DB_PATH = "Changed.db"

# FAISS_DIR = "rbi_scrape_text_fixed"
# FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
# CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
# BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

# EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
# RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# def normalize_text(text: str) -> str:
#     text = text.lower()
#     text = re.sub(r"[^\w\s]", " ", text)  # remove punctuation
#     text = re.sub(r"\s+", " ", text).strip()
#     return text


# def tokenize_with_ngrams(text: str, use_bigrams: bool):
#     words = normalize_text(text).split()
#     if not use_bigrams:
#         return words

#     bigrams = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
#     return words + bigrams


# def coverage_score(query: str, text: str) -> float:
#     q_words = set(normalize_text(query).split())
#     t_words = set(normalize_text(text).split())
#     if not q_words:
#         return 0.0
#     return len(q_words & t_words) / len(q_words)


# def init_chat_db():
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute("""
#     CREATE TABLE IF NOT EXISTS chat_history (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         question TEXT,
#         answer TEXT,
#         sources TEXT,
#         created_at TEXT
#     )
#     """)
#     conn.commit()
#     conn.close()

# init_chat_db()


# def save_chat(question, answer, sources):
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute(
#         "INSERT INTO chat_history (question, answer, sources, created_at) VALUES (?, ?, ?, ?)",
#         (question, answer, json.dumps(sources), datetime.utcnow().isoformat())
#     )
#     conn.commit()
#     conn.close()


# def load_chat_history():
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute(
#         "SELECT id, question, answer, sources FROM chat_history ORDER BY id ASC"
#     )
#     rows = cur.fetchall()
#     conn.close()
#     return rows


# class HybridRetriever:
#     def __init__(self):
#         self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)

#         with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
#             self.metadata = json.load(f)

#         with open(BM25_PATH, "r", encoding="utf-8") as f:
#             bm25_data = json.load(f)

#         self.bm25 = BM25Okapi(bm25_data["corpus"])
#         self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)

#     # ---------------- SEMANTIC ----------------

#     def retrieve_semantic(self, query, top_k):
#         clean_query = normalize_text(query)

#         query_emb = self.embed_model.encode(
#             [clean_query],
#             normalize_embeddings=True
#         ).astype("float32")

#         dists, idxs = self.faiss_index.search(query_emb, top_k)

#         results = []
#         for dist, idx in zip(dists[0], idxs[0]):
#             if idx < len(self.metadata):
#                 doc = self.metadata[idx].copy()
#                 doc["semantic_score"] = float(1 / (1 + dist))
#                 results.append(doc)

#         return results

#     # ---------------- BM25 ----------------

#     def retrieve_bm25(self, query, top_k, use_bigrams):
#         tokens = tokenize_with_ngrams(query, use_bigrams)

#         scores = self.bm25.get_scores(tokens)
#         top_idxs = np.argsort(scores)[-top_k:][::-1]

#         results = []
#         for i in top_idxs:
#             if i < len(self.metadata):
#                 doc = self.metadata[i].copy()
#                 doc["bm25_score"] = float(scores[i])
#                 results.append(doc)

#         return results

#     # ---------------- HYBRID ----------------

#     def hybrid_retrieve(
#         self,
#         query,
#         top_k,
#         use_bigrams,
#         w_semantic,
#         w_bm25,
#         w_coverage
#     ):
#         sem = self.retrieve_semantic(query, top_k)
#         bm25 = self.retrieve_bm25(query, top_k, use_bigrams)

#         merged = {}

#         for r in sem:
#             merged[r["chunk_text"]] = {**r, "bm25_score": 0}

#         for r in bm25:
#             key = r["chunk_text"]
#             if key in merged:
#                 merged[key]["bm25_score"] = r["bm25_score"]
#             else:
#                 merged[key] = {**r, "semantic_score": 0}

#         combined = list(merged.values())

#         if combined:
#             max_sem = max(r["semantic_score"] for r in combined)
#             max_bm = max(r["bm25_score"] for r in combined)

#             for r in combined:
#                 ns = r["semantic_score"] / max_sem if max_sem else 0
#                 nb = r["bm25_score"] / max_bm if max_bm else 0
#                 cov = coverage_score(query, r["chunk_text"])

#                 r["hybrid_score"] = (
#                     w_semantic * ns +
#                     w_bm25 * nb +
#                     w_coverage * cov
#                 )

#         combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
#         return combined[:top_k]


# class Reranker:
#     def __init__(self):
#         self.model = CrossEncoder(RERANK_MODEL_NAME)

#     def rerank(self, query, chunks, top_k):
#         if not chunks:
#             return []

#         scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])

#         for c, s in zip(chunks, scores):
#             c["rerank_score"] = float(s)

#         return sorted(
#             chunks,
#             key=lambda x: x["rerank_score"],
#             reverse=True
#         )[:top_k]

# def generate_answer(query, reranked, history):
#     context_text = ""

#     for i, c in enumerate(reranked[:5], 1):
#         context_text += f"[{i}] {c['chunk_text']}\n"

#     prompt = f"""
# You are an expert RBI regulatory assistant.

# INSTRUCTIONS:
# - First give a SHORT clear explanation of the concept in 2–4 lines.
# - Then support it using the provided context.
# - Consider all words in the question together.
# - Do NOT answer using only partial keyword matches.
# - Use only the provided context.
# - If information is not available, say: Information not available.

# Context:
# {context_text}

# Question:
# {query}

# Answer format:
# Brief Explanation:
# <your explanation>

# Supporting Details:
# <optional details based on context>
# """

#     client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

#     try:
#         res = client.models.generate_content(
#             model=GEMINI_MODEL,
#             contents=prompt
#         )
#         return res.text.strip()
#     except Exception as e:
#         return f"LLM Error: {e}"

# def rag_pipeline(query, retriever, reranker, params):
#     hybrid = retriever.hybrid_retrieve(
#         query=query,
#         top_k=params["initial_top_k"],
#         use_bigrams=params["use_bigrams"],
#         w_semantic=params["w_semantic"],
#         w_bm25=params["w_bm25"],
#         w_coverage=params["w_coverage"],
#     )

#     reranked = reranker.rerank(
#         query,
#         hybrid,
#         params["rerank_top_k"]
#     )

#     answer_text = generate_answer(query, reranked, [])

#     # ✅ STRONG DEDUPLICATION
#     seen_urls = set()
#     unique_sources = {}

#     for c in reranked:
#         url = c.get("pdf_url")
#         title = c.get("title", "RBI Circular")

#         if not url:
#             continue

#         clean_url = url.strip().lower()

#         if clean_url in seen_urls:
#             continue

#         seen_urls.add(clean_url)
#         unique_sources[url] = title

#         # optional cap (recommended)
#         if len(unique_sources) >= 6:
#             break

#     return {
#         "question": query,
#         "answer": answer_text,
#         "sources": unique_sources
#     }


# # =========================================================
# # STREAMLIT UI
# # =========================================================

# def run_app():
#     st.set_page_config(page_title="RBI Circular QA", layout="wide")
#     st.title("🏦 RBI Circular QA Assistant")

#     # ---------- SIDEBAR CONTROLS ----------

#     st.sidebar.header("⚙️ Retrieval Controls")

#     use_bigrams = st.sidebar.checkbox("Enable BM25 Bigrams", value=False)

#     w_semantic = st.sidebar.slider("Semantic Weight", 0.0, 1.0, 0.6)
#     w_bm25 = st.sidebar.slider("BM25 Weight", 0.0, 1.0, 0.25)
#     w_coverage = st.sidebar.slider("Coverage Weight", 0.0, 1.0, 0.15)

#     initial_top_k = st.sidebar.slider("Initial Top-K", 10, 30, 15)
#     rerank_top_k = st.sidebar.slider("Rerank Top-K", 5, 50, 20)

#     params = {
#         "use_bigrams": use_bigrams,
#         "w_semantic": w_semantic,
#         "w_bm25": w_bm25,
#         "w_coverage": w_coverage,
#         "initial_top_k": initial_top_k,
#         "rerank_top_k": rerank_top_k,
#     }

#     # ---------- LOAD MODELS ----------

#     if "retriever" not in st.session_state:
#         with st.spinner("Loading models..."):
#             st.session_state.retriever = HybridRetriever()
#             st.session_state.reranker = Reranker()

#     history_db = load_chat_history()

#     # ---------- CHAT DISPLAY ----------

#     for cid, q, ans, src_json in history_db:
#         sources = json.loads(src_json)

#         st.markdown(f"**Q:** {q}")
#         st.markdown(ans)

#         if sources:
#             # with st.expander("📚 Sources"):
#             #     for url, title in sources.items():
#             #         st.markdown(f"📄 {title} [🔗]({url})")
                    
#             with st.expander("📚 Sources"):
#                 for i, (url, title) in enumerate(sources.items(), 1):
#                     st.markdown(f"{i}. 📄 **{title}**  [🔗]({url})")


#         st.write("---")

#     # ---------- INPUT ----------

#     with st.form("ask_form", clear_on_submit=True):
#         query = st.text_input("Ask a new question:")
#         submitted = st.form_submit_button("Submit")

#         if submitted and query.strip():
#             with st.spinner("Generating answer..."):
#                 res = rag_pipeline(
#                     query.strip(),
#                     st.session_state.retriever,
#                     st.session_state.reranker,
#                     params
#                 )

#                 save_chat(res["question"], res["answer"], res["sources"])
#                 st.rerun()


# if __name__ == "__main__":
#     run_app()




import streamlit as st
import os
import re
import json
import sqlite3
import faiss
import numpy as np
from datetime import datetime
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from google import genai
from dotenv import load_dotenv

load_dotenv()

CHAT_DB_PATH = "Changed.db"

FAISS_DIR = "rbi_scrape_text_fixed"
FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_with_ngrams(text: str, use_bigrams: bool):
    words = normalize_text(text).split()
    if not use_bigrams:
        return words

    bigrams = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
    return words + bigrams


def coverage_score(query: str, text: str) -> float:
    q_words = set(normalize_text(query).split())
    t_words = set(normalize_text(text).split())
    if not q_words:
        return 0.0
    return len(q_words & t_words) / len(q_words)


def init_chat_db():
    conn = sqlite3.connect(CHAT_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        answer TEXT,
        sources TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

init_chat_db()


def save_chat(question, answer, sources):
    conn = sqlite3.connect(CHAT_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_history (question, answer, sources, created_at) VALUES (?, ?, ?, ?)",
        (question, answer, json.dumps(sources), datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def load_chat_history():
    conn = sqlite3.connect(CHAT_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, question, answer, sources FROM chat_history ORDER BY id ASC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


class HybridRetriever:
    def __init__(self):
        self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)

        with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        with open(BM25_PATH, "r", encoding="utf-8") as f:
            bm25_data = json.load(f)

        self.bm25 = BM25Okapi(bm25_data["corpus"])
        self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)

    # ---------------- SEMANTIC ----------------

    def retrieve_semantic(self, query, top_k):
        clean_query = normalize_text(query)

        query_emb = self.embed_model.encode(
            [clean_query],
            normalize_embeddings=True
        ).astype("float32")

        dists, idxs = self.faiss_index.search(query_emb, top_k)

        results = []
        for dist, idx in zip(dists[0], idxs[0]):
            if idx < len(self.metadata):
                doc = self.metadata[idx].copy()
                doc["semantic_score"] = float(1 / (1 + dist))
                results.append(doc)

        return results

    # ---------------- BM25 ----------------

    def retrieve_bm25(self, query, top_k, use_bigrams):
        tokens = tokenize_with_ngrams(query, use_bigrams)

        scores = self.bm25.get_scores(tokens)
        top_idxs = np.argsort(scores)[-top_k:][::-1]

        results = []
        for i in top_idxs:
            if i < len(self.metadata):
                doc = self.metadata[i].copy()
                doc["bm25_score"] = float(scores[i])
                results.append(doc)

        return results

    # ---------------- HYBRID ----------------

    def hybrid_retrieve(
        self,
        query,
        top_k,
        use_bigrams,
        w_semantic,
        w_bm25,
        w_coverage
    ):
        sem = self.retrieve_semantic(query, top_k)
        bm25 = self.retrieve_bm25(query, top_k, use_bigrams)

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
                cov = coverage_score(query, r["chunk_text"])

                r["hybrid_score"] = (
                    w_semantic * ns +
                    w_bm25 * nb +
                    w_coverage * cov
                )

        combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return combined[:top_k]


class Reranker:
    def __init__(self):
        self.model = CrossEncoder(RERANK_MODEL_NAME)

    def rerank(self, query, chunks, top_k):
        if not chunks:
            return []

        scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])

        for c, s in zip(chunks, scores):
            c["rerank_score"] = float(s)

        return sorted(
            chunks,
            key=lambda x: x["rerank_score"],
            reverse=True
        )[:top_k]

def generate_answer(query, reranked, history):
    context_text = ""

    for i, c in enumerate(reranked[:5], 1):
        context_text += f"[{i}] {c['chunk_text']}\n"

    prompt = f"""
You are an expert RBI regulatory assistant.

INSTRUCTIONS:
- First give a SHORT clear explanation of the concept in 2–4 lines.
- Then support it using the provided context.
- Consider all words in the question together.
- Do NOT answer using only partial keyword matches.
- Use only the provided context.
- If information is not available, say: Information not available.

Context:
{context_text}

Question:
{query}

Answer format:
Brief Explanation:
<your explanation>

Supporting Details:
<optional details based on context>
"""

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    try:
        res = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return res.text.strip()
    except Exception as e:
        return f"LLM Error: {e}"

def rag_pipeline(query, retriever, reranker, params):
    hybrid = retriever.hybrid_retrieve(
        query=query,
        top_k=params["initial_top_k"],
        use_bigrams=params["use_bigrams"],
        w_semantic=params["w_semantic"],
        w_bm25=params["w_bm25"],
        w_coverage=params["w_coverage"],
    )

    reranked = reranker.rerank(
        query,
        hybrid,
        params["rerank_top_k"]
    )

    answer_text = generate_answer(query, reranked, [])

    # ✅ STRONG DEDUPLICATION
    seen_urls = set()
    unique_sources = {}

    for c in reranked:
        url = c.get("pdf_url")
        title = c.get("title", "RBI Circular")

        if not url:
            continue

        clean_url = url.strip().lower()

        if clean_url in seen_urls:
            continue

        seen_urls.add(clean_url)
        unique_sources[url] = title

        # optional cap (recommended)
        if len(unique_sources) >= 6:
            break

    return {
        "question": query,
        "answer": answer_text,
        "sources": unique_sources
    }


# =========================================================
# STREAMLIT UI
# =========================================================

def run_app():
    st.set_page_config(page_title="RBI Circular QA", layout="wide")
    st.title("🏦 RBI Circular QA Assistant")

    # ---------- SIDEBAR CONTROLS ----------

    st.sidebar.header("⚙️ Retrieval Controls")

    use_bigrams = st.sidebar.checkbox("Enable BM25 Bigrams", value=False)

    w_semantic = st.sidebar.slider("Semantic Weight", 0.0, 1.0, 0.6)
    w_bm25 = st.sidebar.slider("BM25 Weight", 0.0, 1.0, 0.25)
    w_coverage = st.sidebar.slider("Coverage Weight", 0.0, 1.0, 0.15)

    initial_top_k = st.sidebar.slider("Initial Top-K", 10, 30, 15)
    rerank_top_k = st.sidebar.slider("Rerank Top-K", 5, 50, 20)

    params = {
        "use_bigrams": use_bigrams,
        "w_semantic": w_semantic,
        "w_bm25": w_bm25,
        "w_coverage": w_coverage,
        "initial_top_k": initial_top_k,
        "rerank_top_k": rerank_top_k,
    }

    # ---------- LOAD MODELS ----------

    if "retriever" not in st.session_state:
        with st.spinner("Loading models..."):
            st.session_state.retriever = HybridRetriever()
            st.session_state.reranker = Reranker()

    history_db = load_chat_history()

    # ---------- CHAT DISPLAY ----------

    for cid, q, ans, src_json in history_db:
        sources = json.loads(src_json)

        st.markdown(f"**Q:** {q}")
        st.markdown(ans)

        if sources:
            # with st.expander("📚 Sources"):
            #     for url, title in sources.items():
            #         st.markdown(f"📄 {title} [🔗]({url})")
                    
            with st.expander("📚 Sources"):
                for i, (url, title) in enumerate(sources.items(), 1):
                    st.markdown(f"{i}. 📄 **{title}**  [🔗]({url})")


        st.write("---")

    # ---------- INPUT ----------

    with st.form("ask_form", clear_on_submit=True):
        query = st.text_input("Ask a new question:")
        submitted = st.form_submit_button("Submit")

        if submitted and query.strip():
            with st.spinner("Generating answer..."):
                res = rag_pipeline(
                    query.strip(),
                    st.session_state.retriever,
                    st.session_state.reranker,
                    params
                )

                save_chat(res["question"], res["answer"], res["sources"])
                st.rerun()


if __name__ == "__main__":
    run_app()



