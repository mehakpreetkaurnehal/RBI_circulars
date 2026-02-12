# import streamlit as st
# import os, re, json, sqlite3, faiss
# import numpy as np
# from datetime import datetime
# from sentence_transformers import SentenceTransformer, CrossEncoder
# from rank_bm25 import BM25Okapi
# from google import genai
# from dotenv import load_dotenv

# load_dotenv()

# # -------------------------------------------------------------------
# # Constants
# # -------------------------------------------------------------------

# DB_PATH              = "rbi_scrape_text.db"
# FAISS_DIR            = "rbi_scrape_text_fixed"
# FAISS_INDEX_PATH     = os.path.join(FAISS_DIR, "rbi_chunks.index")
# CHUNK_META_PATH      = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
# BM25_PATH            = os.path.join(FAISS_DIR, "bm25_index.json")

# EMBED_MODEL_NAME     = "sentence-transformers/all-mpnet-base-v2"
# RERANK_MODEL_NAME    = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# GEMINI_MODEL         = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# CHUNK_SIZE           = 512
# CHUNK_OVERLAP        = 100
# INITIAL_TOP_K        = 50
# RERANK_TOP_K         = 20

# os.makedirs(FAISS_DIR, exist_ok=True)

# # -------------------------------------------------------------------
# # Helpers
# # -------------------------------------------------------------------

# def sanitize(text):
#     return re.sub(r"\s+", " ", text).strip()


# def extract_key_phrases(text, min_len=4):
#     """
#     Extract keywords/phrases from chunk text.
#     (Simplified: can be later improved with NLP extraction libraries.)
#     """
#     words = re.findall(r"[A-Za-z]{4,}", text)
#     return list(set(words))


# def make_question_style(term):
#     """
#     Convert a phrase into a question style phrase.
#     """
#     term = term.lower().strip()
#     return f"What is {term}?" if not term.endswith("?") else term

# # -------------------------------------------------------------------
# # Index Building
# # (run once externally)
# # -------------------------------------------------------------------

# def build_index():
#     conn = sqlite3.connect(DB_PATH)
#     cur  = conn.cursor()
#     cur.execute("SELECT ref_no, title, issue_date, pdf_url, body_text FROM circulars")
#     rows = cur.fetchall()
#     conn.close()

#     model = SentenceTransformer(EMBED_MODEL_NAME)
#     faiss_index = None
#     chunk_metadata = []
#     bm25_corpus = []

#     for ref_no, title, issue_date, pdf_url, body_text in rows:
#         if not body_text:
#             continue

#         full_text = f"{title}\n\n{sanitize(body_text)}"
#         sentences = re.split(r'(?<=[.!?])\s+', full_text)
#         chunks = []
#         current = []
#         length = 0

#         for sent in sentences:
#             if length + len(sent) > CHUNK_SIZE and current:
#                 chunks.append(" ".join(current))
#                 # create overlap
#                 overlap_sents = []
#                 overlap_len = 0
#                 for s in reversed(current):
#                     if overlap_len + len(s) <= CHUNK_OVERLAP:
#                         overlap_sents.insert(0, s)
#                         overlap_len += len(s)
#                     else:
#                         break
#                 current = overlap_sents
#                 length = overlap_len
#             current.append(sent)
#             length += len(sent)

#         if current:
#             chunks.append(" ".join(current))

#         embeddings = model.encode(chunks, normalize_embeddings=True).astype("float32")

#         if faiss_index is None:
#             faiss_index = faiss.IndexFlatL2(embeddings.shape[1])

#         faiss_index.add(embeddings)

#         for i, chunk_text in enumerate(chunks):
#             chunk_metadata.append({
#                 "ref_no":     ref_no,
#                 "title":      title,
#                 "issue_date": issue_date,
#                 "pdf_url":    pdf_url,
#                 "chunk_text": chunk_text
#             })
#             bm25_corpus.append(chunk_text.lower().split())

#     faiss.write_index(faiss_index, FAISS_INDEX_PATH)
#     with open(CHUNK_META_PATH, "w", encoding="utf-8") as f:
#         json.dump(chunk_metadata, f, indent=2)

#     bm25 = BM25Okapi(bm25_corpus)
#     bm25_data = {
#         "corpus":    bm25_corpus,
#         "doc_freqs": list(bm25.doc_freqs),
#         "idf":       {k:v for k,v in bm25.idf.items()},
#         "avgdl":     bm25.avgdl,
#         "doc_len":   list(bm25.doc_len)
#     }
#     with open(BM25_PATH, "w", encoding="utf-8") as f:
#         json.dump(bm25_data, f)


# # -------------------------------------------------------------------
# # RAG Retrieval & Re-ranking
# # -------------------------------------------------------------------

# class HybridRetriever:
#     def __init__(self):
#         self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
#         with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
#             self.metadata = json.load(f)

#         with open(BM25_PATH, "r", encoding="utf-8") as f:
#             bm25_data = json.load(f)
#         self.bm25_corpus = bm25_data["corpus"]
#         self.bm25         = BM25Okapi(self.bm25_corpus)
#         self.embed_model  = SentenceTransformer(EMBED_MODEL_NAME)

#         self.suggestion_terms = self.build_suggestions()

#     def build_suggestions(self):
#         terms = set()
#         for m in self.metadata:
#             title = m["title"]
#             terms.update(extract_key_phrases(title))
#             terms.update(extract_key_phrases(m["chunk_text"]))
#         return list(terms)

#     def corpussuggestions(self, prefix, max_s=7):
#         prefix = prefix.lower()
#         matches = [t for t in self.suggestion_terms if t.lower().startswith(prefix)]
#         return [make_question_style(m) for m in matches[:max_s]]

#     def retrieve_semantic(self, query, top_k=INITIAL_TOP_K):
#         emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
#         dists, idxs = self.faiss_index.search(emb, top_k)
#         results = []
#         for rank, i in enumerate(idxs[0]):
#             if i < len(self.metadata):
#                 m = self.metadata[i].copy()
#                 m["semantic_score"] = float(1/(1 + dists[0][rank]))
#                 results.append(m)
#         return results

#     def retrieve_bm25(self, query, top_k=INITIAL_TOP_K):
#         tokens = query.lower().split()
#         scores = self.bm25.get_scores(tokens)
#         top_idxs = np.argsort(scores)[-top_k:][::-1]
#         results = []
#         for i in top_idxs:
#             if i < len(self.metadata):
#                 m = self.metadata[i].copy()
#                 m["bm25_score"] = float(scores[i])
#                 results.append(m)
#         return results

#     def hybrid_retrieve(self, query, alpha=0.7):
#         sem = self.retrieve_semantic(query)
#         bm  = self.retrieve_bm25(query)

#         merged = {}
#         for r in sem:
#             merged[r["chunk_text"]] = {**r, "bm25_score":0}
#         for r in bm:
#             key = r["chunk_text"]
#             if key in merged:
#                 merged[key]["bm25_score"] = r["bm25_score"]
#             else:
#                 merged[key] = {**r, "semantic_score":0}

#         combined = list(merged.values())
#         if combined:
#             max_sem = max(r["semantic_score"] for r in combined)
#             max_bm  = max(r["bm25_score"] for r in combined)
#             for r in combined:
#                 ns = r["semantic_score"]/max_sem if max_sem else 0
#                 nb = r["bm25_score"]/max_bm  if max_bm  else 0
#                 r["hybrid_score"] = alpha*ns + (1-alpha)*nb

#         combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
#         return combined[:INITIAL_TOP_K]


# class Reranker:
#     def __init__(self):
#         self.model = CrossEncoder(RERANK_MODEL_NAME)

#     def rerank(self, query, chunks):
#         if not chunks:
#             return []
#         scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])
#         for c, s in zip(chunks, scores):
#             c["rerank_score"] = float(s)
#         return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:RERANK_TOP_K]


# # -------------------------------------------------------------------
# # Answer Generation & Evaluation
# # -------------------------------------------------------------------

# def build_history_prompt(history):
#     parts = []
#     for turn in history[-4:]:
#         qe = turn["question"]
#         an = turn["answer"]
#         parts.append(f"Q: {qe}\nA: {an}")
#     return "\n\n".join(parts)


# def generate_answer(query, reranked, history):
#     ctx = "\n".join(f"[{i+1}] {c['chunk_text']}\nURL: {c['pdf_url']}" 
#                     for i,c in enumerate(reranked[:7]))
#     hist = build_history_prompt(history) if history else ""
#     prompt = f"""
# You are an expert on RBI circulars.

# History:
# {hist}

# Context:
# {ctx}

# Question:
# {query}

# Answer accurately with source citations.
# """
#     try:
#         client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#         res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
#         return res.text.strip()
#     except Exception as e:
#         return f"Error: {e}"


# def evaluate_answer(answer, context):
#     judge_prompt = f"Is the answer supported by the context?\n\nContext:\n{context}\n\nAnswer:\n{answer}"
#     try:
#         client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#         res = client.models.generate_content(model=GEMINI_MODEL, contents=judge_prompt)
#         return res.text.strip()
#     except:
#         return "Evaluation unavailable."

# def rag_pipeline(query, retriever, reranker, history):
#     rerieval = retriever.hybrid_retrieve(query)
#     reranked = reranker.rerank(query, rerieval)
#     ans = generate_answer(query, reranked, history)
#     ev = evaluate_answer(ans, "\n".join(c["chunk_text"] for c in reranked[:7]))

#     return {
#         "question": query,
#         "answer": ans,
#         "evaluation": ev,
#         "sources": reranked
#     }


# # -------------------------------------------------------------------
# # Streamlit UI
# # -------------------------------------------------------------------

# def run_app():
#     st.set_page_config(page_title="RBI Chat RAG", layout="wide")
#     st.title("🏦 RBI Circular QA Assistant")

#     if "history" not in st.session_state:
#         st.session_state.history = []

#     if "query_text" not in st.session_state:
#         st.session_state.query_text = ""

#     if "trigger" not in st.session_state:
#         st.session_state.trigger = False

#     if "suggestions" not in st.session_state:
#         st.session_state.suggestions = []

#     # Load retriever & reranker
#     if "retriever" not in st.session_state:
#         with st.spinner("Loading models..."):
#             st.session_state.retriever = HybridRetriever()
#             st.session_state.reranker  = Reranker()

#     # Sidebar with chat history
#     with st.sidebar:
#         st.header("📜 Chat History")
#         for i, turn in enumerate(st.session_state.history, 1):
#             st.markdown(f"**{i}. {turn['question']}**")
#             st.write(turn['answer'])

#     # User input
#     q = st.text_input("Ask a question:", key="chat_input")

#     # Load suggestions from prefix
#     if q:
#         st.session_state.suggestions = st.session_state.retriever.corpussuggestions(q)

#     # Show suggestions
#     if st.session_state.suggestions:
#         cols = st.columns(len(st.session_state.suggestions))
#         for idx, sug in enumerate(st.session_state.suggestions):
#             btn_key = f"suggestion_{idx}_{sug.replace(' ', '_')}"
#             if cols[idx].button(sug, key=btn_key):
#                 st.session_state.query_text = sug
#                 st.session_state.trigger = True
            
#     # Enter key submit
#     if st.button("Submit") or st.session_state.trigger:
#         user_q = q.strip() or st.session_state.query_text
#         if user_q:
#             with st.spinner("Thinking..."):
#                 result = rag_pipeline(user_q, st.session_state.retriever, st.session_state.reranker, st.session_state.history)
#                 st.session_state.history.append(result)
#                 st.session_state.query_text = ""
#                 st.session_state.trigger  = False
#                 st.rerun()

#     # Output chat
#     st.markdown("---")
#     for i, turn in enumerate(st.session_state.history[-6:], start=1):
#         st.markdown(f"### Q{i}: {turn['question']}")
#         st.markdown(turn['answer'])
#         st.write(f"🧠 Eval: {turn['evaluation']}")

#         with st.expander("📚 Sources"):
#             for j, src in enumerate(turn["sources"],1):
#                 st.markdown(f"{j}. {src['title']} — [View PDF]({src['pdf_url']})")
#                 st.write(src["chunk_text"][:150] + "...")

# if __name__ == "__main__":
#     run_app()



# this is showing duplicate circulars as well, ui is good but needs more improvement

# import streamlit as st
# import os, re, json, sqlite3, faiss, numpy as np
# from datetime import datetime
# from sentence_transformers import SentenceTransformer, CrossEncoder
# from rank_bm25 import BM25Okapi
# from google import genai
# from dotenv import load_dotenv

# load_dotenv()

# # ───────────────────────────────────────────────────────────────
# # Constants
# # ───────────────────────────────────────────────────────────────

# DB_PATH            = "rbi_scrape_text.db"
# FAISS_DIR          = "rbi_scrape_text_fixed"
# FAISS_INDEX_PATH   = os.path.join(FAISS_DIR, "rbi_chunks.index")
# CHUNK_META_PATH    = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
# BM25_PATH          = os.path.join(FAISS_DIR, "bm25_index.json")

# EMBED_MODEL_NAME   = "sentence-transformers/all-mpnet-base-v2"
# RERANK_MODEL_NAME  = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# GEMINI_MODEL       = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# CHUNK_SIZE         = 512
# CHUNK_OVERLAP      = 100
# INITIAL_TOP_K      = 50
# RERANK_TOP_K       = 20

# os.makedirs(FAISS_DIR, exist_ok=True)

# # ───────────────────────────────────────────────────────────────
# # Helpers
# # ───────────────────────────────────────────────────────────────

# def sanitize(text: str) -> str:
#     return re.sub(r"\s+", " ", text).strip()

# def extract_key_phrases(text):
#     words = re.findall(r"[A-Za-z]{4,}", text)
#     return list(set(words))

# def make_question_style(term):
#     term = term.lower().strip()
#     if term.endswith("?"):
#         return term
#     return f"What is {term}?"

# # ───────────────────────────────────────────────────────────────
# # RAG Components
# # ───────────────────────────────────────────────────────────────

# class HybridRetriever:
#     def __init__(self):
#         # Load FAISS
#         self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
#         with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
#             self.metadata = json.load(f)

#         # Load BM25
#         with open(BM25_PATH, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         self.bm25_corpus = data["corpus"]
#         self.bm25 = BM25Okapi(self.bm25_corpus)

#         # Embedding model
#         self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)

#         # Build suggestion pool
#         self.suggestion_terms = self._build_suggestion_terms()

#     def _build_suggestion_terms(self):
#         terms = set()
#         for m in self.metadata:
#             terms.update(extract_key_phrases(m["title"]))
#             terms.update(extract_key_phrases(m["chunk_text"]))
#         return list(terms)

#     def get_suggestions(self, prefix, n=7):
#         prefix = prefix.lower()
#         matches = [t for t in self.suggestion_terms if t.lower().startswith(prefix)]
#         return [make_question_style(m) for m in matches[:n]]

#     def retrieve_semantic(self, query, top_k=INITIAL_TOP_K):
#         query_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
#         distances, indices = self.faiss_index.search(query_emb, top_k)
#         results = []
#         for rank, idx in enumerate(indices[0]):
#             if idx < len(self.metadata):
#                 r = self.metadata[idx].copy()
#                 r["semantic_score"] = float(1 / (1 + distances[0][rank]))
#                 results.append(r)
#         return results

#     def retrieve_bm25(self, query, top_k=INITIAL_TOP_K):
#         tokens = query.lower().split()
#         scores = self.bm25.get_scores(tokens)
#         top_idxs = np.argsort(scores)[-top_k:][::-1]
#         results = []
#         for i in top_idxs:
#             if i < len(self.metadata):
#                 r = self.metadata[i].copy()
#                 r["bm25_score"] = float(scores[i])
#                 results.append(r)
#         return results

#     def hybrid_retrieve(self, query):
#         sem = self.retrieve_semantic(query)
#         bm25 = self.retrieve_bm25(query)

#         merged = {}
#         for r in sem:
#             merged[r["chunk_text"]] = {**r, "bm25_score": 0}
#         for r in bm25:
#             key = r["chunk_text"]
#             if key in merged:
#                 merged[key]["bm25_score"] = r["bm25_score"]
#             else:
#                 merged[key] = {**r, "semantic_score": 0}

#         results = list(merged.values())
#         if results:
#             max_sem = max(r["semantic_score"] for r in results)
#             max_bm = max(r["bm25_score"] for r in results)
#             for r in results:
#                 norm_sem = r["semantic_score"] / max_sem if max_sem else 0
#                 norm_bm = r["bm25_score"] / max_bm if max_bm else 0
#                 r["hybrid_score"] = 0.7 * norm_sem + 0.3 * norm_bm

#         results.sort(key=lambda x: x["hybrid_score"], reverse=True)
#         return results[:INITIAL_TOP_K]


# class Reranker:
#     def __init__(self):
#         self.model = CrossEncoder(RERANK_MODEL_NAME)

#     def rerank(self, query, chunks):
#         if not chunks:
#             return []
#         scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])
#         for c, s in zip(chunks, scores):
#             c["rerank_score"] = float(s)
#         return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:RERANK_TOP_K]


# # ───────────────────────────────────────────────────────────────
# # Generation / Evaluation
# # ───────────────────────────────────────────────────────────────

# def build_history_context(history):
#     parts = []
#     for turn in history[-3:]:
#         parts.append(f"Q: {turn['question']}\nA: {turn['answer']}")
#     return "\n\n".join(parts)

# def generate_answer(query, reranked, history):
#     context_blocks = ""
#     for i, c in enumerate(reranked[:7], 1):
#         context_blocks += f"[{i}] {c['chunk_text']}\nPDF: {c['pdf_url']}\n\n"

#     hist_txt = build_history_context(history) if history else ""

#     prompt = f"""
# You are an expert RBI regulatory assistant.

# History:
# {hist_txt}

# Context:
# {context_blocks}

# Question:
# {query}

# Answer clearly with source citations (use the provided context).
# """

#     try:
#         client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#         response = client.models.generate_content(
#             model=GEMINI_MODEL,
#             contents=prompt
#         )
#         return response.text.strip()
#     except Exception as e:
#         return f"Error generating answer: {str(e)}"

# def evaluate_answer(answer, context):
#     judge_prompt = f"Check if the answer is supported by the context.\nContext:\n{context}\n\nAnswer:\n{answer}"
#     try:
#         client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#         res = client.models.generate_content(model=GEMINI_MODEL, contents=judge_prompt)
#         return res.text.strip()
#     except:
#         return "Evaluation not available."

# def rag_pipeline(query, retriever, reranker, history):
#     retrieved = retriever.hybrid_retrieve(query)
#     reranked  = reranker.rerank(query, retrieved)
#     answer    = generate_answer(query, reranked, history)
#     eval_rep  = evaluate_answer(answer, "\n".join(c["chunk_text"] for c in reranked[:7]))

#     return {
#         "question": query,
#         "answer": answer,
#         "evaluation": eval_rep,
#         "sources": reranked
#     }

# # ───────────────────────────────────────────────────────────────
# # Streamlit App
# # ───────────────────────────────────────────────────────────────

# def run_app():
#     st.set_page_config(page_title="RBI Circular Chat Assistant", layout="wide")
#     st.title("🏦 RBI Circular QA Assistant")

#     # Initialize session state
#     if "history" not in st.session_state:
#         st.session_state.history = []

#     if "query_text" not in st.session_state:
#         st.session_state.query_text = ""

#     if "submit" not in st.session_state:
#         st.session_state.submit = False

#     if "suggestions" not in st.session_state:
#         st.session_state.suggestions = []

#     # Load models
#     if "retriever" not in st.session_state:
#         with st.spinner("Loading models..."):
#             st.session_state.retriever = HybridRetriever()
#             st.session_state.reranker  = Reranker()

#     # Sidebar → Chat History
#     with st.sidebar:
#         st.header("📜 Recent Conversations")
#         for idx, turn in enumerate(st.session_state.history[::-1], 1):
#             st.markdown(f"**{idx}. {turn['question']}**")
#             st.write(turn['answer'][:120] + "...")

#     # User input
#     query = st.text_input(
#         "Ask your question:",
#         value=st.session_state.query_text,
#         key="input_box"
#     )

#     # Predictive suggestions while typing
#     if query.strip():
#         st.session_state.suggestions = st.session_state.retriever.get_suggestions(query)

#     if st.session_state.suggestions:
#         st.write("Suggestions:")
#         for i, sug in enumerate(st.session_state.suggestions):
#             btn_key = f"sugg_btn_{i}_{sug.replace(' ', '_')}"
#             if st.button(sug, key=btn_key):
#                 st.session_state.query_text = sug
#                 st.session_state.submit = True

#     # Only generate after explicit submit
#     if st.button("Submit") or st.session_state.submit:
#         q_text = st.session_state.query_text.strip() or query.strip()
#         if q_text:
#             with st.spinner("Generating answer..."):
#                 result = rag_pipeline(q_text, st.session_state.retriever,
#                                       st.session_state.reranker,
#                                       st.session_state.history)

#                 st.session_state.history.append(result)

#                 # Reset input
#                 st.session_state.query_text = ""
#                 st.session_state.submit = False

#                 st.rerun()

#     st.markdown("---")
#     # Display chat
#     for idx, turn in enumerate(st.session_state.history, 1):
#         st.markdown(f"### Q{idx}: {turn['question']}")
#         st.markdown(turn['answer'])
#         st.write(f"🧠 Eval: {turn['evaluation']}")

#         with st.expander("📚 Sources"):
#             for j, src in enumerate(turn["sources"], 1):
#                 st.markdown(f"{j}. {src['title']} — [View PDF]({src['pdf_url']})")
#                 st.write(src["chunk_text"][:200] + "...")

# if __name__ == "__main__":
#     run_app()



# import streamlit as st
# import os, re, json, sqlite3, faiss, numpy as np
# from datetime import datetime
# from sentence_transformers import SentenceTransformer, CrossEncoder
# from rank_bm25 import BM25Okapi
# from google import genai
# from dotenv import load_dotenv

# # Load environment variables (Gemini API key)
# load_dotenv()

# DB_PATH          = "rbi_scrape_text.db"
# CHAT_DB_PATH     = "chat_history.db"

# FAISS_DIR        = "rbi_scrape_text_fixed"
# FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
# CHUNK_META_PATH  = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
# BM25_PATH        = os.path.join(FAISS_DIR, "bm25_index.json")

# EMBED_MODEL_NAME  = "sentence-transformers/all-mpnet-base-v2"
# RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# GEMINI_MODEL      = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# INITIAL_TOP_K     = 50
# RERANK_TOP_K      = 20

# # Make sure the FAISS directory exists
# os.makedirs(FAISS_DIR, exist_ok=True)
# def init_chat_db():
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute("""
#     CREATE TABLE IF NOT EXISTS chat_history (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         question TEXT,
#         answer TEXT,
#         created_at TEXT
#     )
#     """)
#     conn.commit()
#     conn.close()

# init_chat_db()

# def save_chat(question, answer):
#     """Save question and answer to the chat_history database."""
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute(
#         "INSERT INTO chat_history (question, answer, created_at) VALUES (?, ?, ?)",
#         (question, answer, datetime.utcnow().isoformat())
#     )
#     conn.commit()
#     conn.close()

# def get_all_history():
#     """Retrieve all saved chat history."""
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute("SELECT question, answer FROM chat_history ORDER BY id ASC")
#     rows = cur.fetchall()
#     conn.close()
#     return rows

# def sanitize(text: str) -> str:
#     return re.sub(r"\s+", " ", text).strip()

# def extract_key_phrases(text):
#     words = re.findall(r"[A-Za-z]{4,}", text)
#     return list(set(words))

# def make_question_style(term):
#     term = term.lower().strip()
#     return term if term.endswith("?") else f"What is {term}?"


# class HybridRetriever:
#     def __init__(self):
#         self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
#         with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
#             self.metadata = json.load(f)

#         with open(BM25_PATH, "r", encoding="utf-8") as f:
#             bm25_data = json.load(f)
#         self.bm25_corpus = bm25_data["corpus"]
#         self.bm25 = BM25Okapi(self.bm25_corpus)

#         self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)
#         self.suggestion_terms = self._build_suggestions()

#     def _build_suggestions(self):
#         terms = set()
#         for m in self.metadata:
#             terms.update(extract_key_phrases(m["title"]))
#             terms.update(extract_key_phrases(m["chunk_text"]))
#         return list(terms)

#     def get_suggestions(self, prefix, n=7):
#         prefix = prefix.lower()
#         matches = [t for t in self.suggestion_terms if t.lower().startswith(prefix)]
#         return [make_question_style(m) for m in matches[:n]]

#     def retrieve_semantic(self, query, top_k=INITIAL_TOP_K):
#         emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
#         dists, idxs = self.faiss_index.search(emb, top_k)
#         results = []
#         for dist, idx in zip(dists[0], idxs[0]):
#             if idx < len(self.metadata):
#                 r = self.metadata[idx].copy()
#                 r["semantic_score"] = float(1/(1+dist))
#                 results.append(r)
#         return results

#     def retrieve_bm25(self, query, top_k=INITIAL_TOP_K):
#         tokens = query.lower().split()
#         scores = self.bm25.get_scores(tokens)
#         top_idxs = np.argsort(scores)[-top_k:][::-1]
#         results = []
#         for i in top_idxs:
#             if i < len(self.metadata):
#                 r = self.metadata[i].copy()
#                 r["bm25_score"] = float(scores[i])
#                 results.append(r)
#         return results

#     def hybrid_retrieve(self, query):
#         sem = self.retrieve_semantic(query)
#         bm25 = self.retrieve_bm25(query)
#         merged = {}

#         for r in sem:
#             merged[r["chunk_text"]] = {**r, "bm25_score":0}
#         for r in bm25:
#             key = r["chunk_text"]
#             if key in merged:
#                 merged[key]["bm25_score"] = r["bm25_score"]
#             else:
#                 merged[key] = {**r, "semantic_score":0}

#         all_results = list(merged.values())
#         if all_results:
#             max_sem = max(r["semantic_score"] for r in all_results)
#             max_bm  = max(r["bm25_score"] for r in all_results)

#             for r in all_results:
#                 ns = r["semantic_score"]/max_sem if max_sem else 0
#                 nb = r["bm25_score"]/max_bm if max_bm else 0
#                 r["hybrid_score"] = 0.7*ns + 0.3*nb

#         all_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
#         return all_results[:INITIAL_TOP_K]

# class Reranker:
#     def __init__(self):
#         self.model = CrossEncoder(RERANK_MODEL_NAME)

#     def rerank(self, query, chunks):
#         if not chunks:
#             return []
#         scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])
#         for c, s in zip(chunks, scores):
#             c["rerank_score"] = float(s)
#         return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:RERANK_TOP_K]

# def build_history_context(history):
#     parts = []
#     for q,a in history[-3:]:
#         parts.append(f"Q: {q}\nA: {a}")
#     return "\n\n".join(parts)

# def generate_answer(query, reranked, history):
#     context_str = ""
#     for i, c in enumerate(reranked[:5],1):
#         context_str += f"[{i}] {c['chunk_text']}\nPDF: {c['pdf_url']}\n\n"

#     hist_txt = build_history_context(history) if history else ""

#     prompt = f"""
# You are an expert RBI regulatory assistant.

# History:
# {hist_txt}

# Context:
# {context_str}

# Question:
# {query}

# Answer accurately with citations from the context.
# """

#     try:
#         client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#         res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
#         return res.text.strip()
#     except Exception as e:
#         return f"Error: {str(e)}"

# def evaluate_answer(ans, context):
#     judge_prompt = f"Check if the answer is supported by the context.\n\nContext:\n{context}\n\nAnswer:\n{ans}"
#     try:
#         client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#         rep = client.models.generate_content(model=GEMINI_MODEL, contents=judge_prompt)
#         return rep.text.strip()
#     except:
#         return "Evaluation unavailable"

# def rag_pipeline(query, retriever, reranker, history):
#     retrieved = retriever.hybrid_retrieve(query)
#     reranked = reranker.rerank(query, retrieved)

#     answer = generate_answer(query, reranked, history)
#     evaluation = evaluate_answer(answer, "\n".join(c["chunk_text"] for c in reranked[:5]))

#     # only keep top source
#     top_source = reranked[0] if reranked else {}

#     return {
#         "question": query,
#         "answer": answer,
#         "evaluation": evaluation,
#         "source": top_source
#     }

# def run_app():
#     st.set_page_config(page_title="RBI Circular QA Assistant", layout="wide")
#     st.title("🏦 RBI Circular Chat Assistant")

#     # Load chat history from DB
#     history_db = get_all_history()

#     # Initialize session state
#     if "query_text" not in st.session_state:
#         st.session_state.query_text = ""

#     if "suggestions" not in st.session_state:
#         st.session_state.suggestions = []

#     if "retriever" not in st.session_state:
#         with st.spinner("Loading models..."):
#             st.session_state.retriever = HybridRetriever()
#             st.session_state.reranker  = Reranker()

#     # Sidebar → Recent Conversations
#     with st.sidebar:
#         st.header("📜 All Chat History")
#         for i, (q,a) in enumerate(history_db[::-1], 1):
#             st.markdown(f"**{i}. {q}**")
#             st.write(a[:120] + "...")

#     # User input
#     query = st.text_input("Ask your question:", value=st.session_state.query_text, key="main_input")

#     # Suggestions while typing
#     if query.strip():
#         st.session_state.suggestions = st.session_state.retriever.get_suggestions(query)

#     if st.session_state.suggestions:
#         st.write("Suggestions:")
#         for idx,s in enumerate(st.session_state.suggestions):
#             btn_key = f"sugg_{idx}_{s.replace(' ', '_')}"
#             if st.button(s, key=btn_key):
#                 st.session_state.query_text = s

#     # Submit on Enter / Submit button
#     if st.button("Submit") or st.session_state.query_text.strip():
#         user_q = st.session_state.query_text.strip() or query.strip()
#         if user_q:
#             with st.spinner("Generating answer..."):
#                 result = rag_pipeline(
#                     user_q,
#                     st.session_state.retriever,
#                     st.session_state.reranker,
#                     history_db
#                 )

#                 # save chat
#                 save_chat(result["question"], result["answer"])

#                 # refresh state
#                 st.session_state.query_text = ""
#                 st.rerun()

#     # -----------------------------------------------------------------
#     # Display chat history in main area
#     # -----------------------------------------------------------------
#     st.markdown("---")
#     for i, (q,a) in enumerate(get_all_history(),1):
#         st.markdown(f"### Q{i}: {q}")
#         st.markdown(a)

#         # Show evaluation summary
#         #st.write(f"🧠 Eval: {result['evaluation']}")

#         with st.expander("📚 Source"):
#             src = get_all_history()

#         # done
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

# # ───────────────────────────────────────────────────────────────
# # Database / Path Settings
# # ───────────────────────────────────────────────────────────────

# DB_PATH = "rbi_scrape_text.db"
# CHAT_DB_PATH = "chat_history_.db"

# FAISS_DIR = "rbi_scrape_text_fixed"
# FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
# CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
# BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

# EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
# RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# INITIAL_TOP_K = 50
# RERANK_TOP_K = 20

# os.makedirs(FAISS_DIR, exist_ok=True)

# # ───────────────────────────────────────────────────────────────
# # Initialize Chat DB (with source column)
# # ───────────────────────────────────────────────────────────────

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

# def get_chat_by_id(chat_id):
#     conn = sqlite3.connect(CHAT_DB_PATH)
#     cur = conn.cursor()
#     cur.execute(
#         "SELECT question, answer, sources FROM chat_history WHERE id = ?",
#         (chat_id,)
#     )
#     row = cur.fetchone()
#     conn.close()
#     return row

# # ───────────────────────────────────────────────────────────────
# # Helpers
# # ───────────────────────────────────────────────────────────────

# def sanitize(text: str) -> str:
#     return re.sub(r"\s+", " ", text).strip()

# def extract_key_phrases(text):
#     words = re.findall(r"[A-Za-z]{4,}", text)
#     return list(set(words))

# def make_question_style(term):
#     term = term.lower().strip()
#     if term.endswith("?"):
#         return term
#     return f"What is {term}?"

# # ───────────────────────────────────────────────────────────────
# # Retriever + Reranker
# # ───────────────────────────────────────────────────────────────

# class HybridRetriever:
#     def __init__(self):
#         self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
#         with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
#             self.metadata = json.load(f)

#         with open(BM25_PATH, "r", encoding="utf-8") as f:
#             bm25_data = json.load(f)
#         self.bm25 = BM25Okapi(bm25_data["corpus"])

#         self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)
#         self.suggestion_terms = self._build_suggestions()

#     def _build_suggestions(self):
#         terms = set()
#         for m in self.metadata:
#             terms.update(extract_key_phrases(m["title"]))
#             terms.update(extract_key_phrases(m["chunk_text"]))
#         return list(terms)

#     def get_suggestions(self, prefix, limit=7):
#         prefix = prefix.lower()
#         matches = [t for t in self.suggestion_terms if t.lower().startswith(prefix)]
#         return [make_question_style(m) for m in matches[:limit]]

#     def retrieve_semantic(self, query, top_k=INITIAL_TOP_K):
#         query_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
#         dists, idxs = self.faiss_index.search(query_emb, top_k)
#         results = []
#         for dist, idx in zip(dists[0], idxs[0]):
#             if idx < len(self.metadata):
#                 doc = self.metadata[idx].copy()
#                 doc["semantic_score"] = float(1/(1 + dist))
#                 results.append(doc)
#         return results

#     def retrieve_bm25(self, query, top_k=INITIAL_TOP_K):
#         tokens = query.lower().split()
#         scores = self.bm25.get_scores(tokens)
#         top_idxs = np.argsort(scores)[-top_k:][::-1]
#         results = []
#         for i in top_idxs:
#             if i < len(self.metadata):
#                 doc = self.metadata[i].copy()
#                 doc["bm25_score"] = float(scores[i])
#                 results.append(doc)
#         return results

#     def hybrid_retrieve(self, query):
#         sem = self.retrieve_semantic(query)
#         bm25 = self.retrieve_bm25(query)

#         merged = {}
#         for r in sem:
#             merged[r["chunk_text"]] = {**r, "bm25_score":0}
#         for r in bm25:
#             key = r["chunk_text"]
#             if key in merged:
#                 merged[key]["bm25_score"] = r["bm25_score"]
#             else:
#                 merged[key] = {**r, "semantic_score":0}

#         combined = list(merged.values())
#         if combined:
#             max_sem = max(r["semantic_score"] for r in combined)
#             max_bm  = max(r["bm25_score"] for r in combined)
#             for r in combined:
#                 ns = r["semantic_score"]/max_sem if max_sem else 0
#                 nb = r["bm25_score"]/max_bm if max_bm else 0
#                 r["hybrid_score"] = 0.7*ns + 0.3*nb

#         combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
#         return combined[:INITIAL_TOP_K]

# class Reranker:
#     def __init__(self):
#         self.model = CrossEncoder(RERANK_MODEL_NAME)

#     def rerank(self, query, chunks):
#         if not chunks:
#             return []
#         scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])
#         for c, s in zip(chunks, scores):
#             c["rerank_score"] = float(s)
#         return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:RERANK_TOP_K]

# # ───────────────────────────────────────────────────────────────
# # Answer Gen + RAG Pipeline
# # ───────────────────────────────────────────────────────────────

# def build_history_context(history):
#     parts = []
#     for q, a, _ in history[-3:]:
#         parts.append(f"Q: {q}\nA: {a}")
#     return "\n\n".join(parts)

# def generate_answer(query, reranked, history):
#     ctx = ""
#     for i, c in enumerate(reranked[:5], 1):
#         ctx += f"[{i}] {c['chunk_text']}\n"
#     hist_txt = build_history_context(history) if history else ""
#     prompt = f"""
# You are an expert RBI regulatory assistant.

# History:
# {hist_txt}

# Context:
# {ctx}

# Question:
# {query}

# Answer with concise explanation and citation references.
# """
#     try:
#         client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#         res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
#         return res.text.strip()
#     except Exception as e:
#         return f"LLM Error: {e}"

# def rag_pipeline(query, retriever, reranker, history):
#     reranked = reranker.rerank(query, retriever.hybrid_retrieve(query))
#     answer_text = generate_answer(query, reranked, history)
#     sources = list({c["pdf_url"] for c in reranked if c.get("pdf_url")})
#     return {"question": query, "answer": answer_text, "sources": sources}

# # ───────────────────────────────────────────────────────────────
# # Streamlit UI
# # ───────────────────────────────────────────────────────────────

# def run_app():
#     st.set_page_config(page_title="RBI Circular QA", layout="wide")
#     st.title("🏦 RBI Circular QA Assistant")

#     if "retriever" not in st.session_state:
#         with st.spinner("Loading models..."):
#             st.session_state.retriever = HybridRetriever()
#             st.session_state.reranker  = Reranker()

#     history_db = load_chat_history()

#     # ---------------- Sidebar ----------------
#     with st.sidebar:
#         st.header("📜 Questions")
#         for chat_id, q, _, _ in history_db[::-1]:
#             label = q if len(q) <= 50 else q[:47] + "..."
#             if st.button(label, key=f"hist_{chat_id}"):
#                 st.session_state.selected_chat = chat_id

#     # ---------------- Main UI ----------------
#     selected = st.session_state.get("selected_chat")

#     # If a saved chat was clicked
#     if selected:
#         q, ans, src_json = get_chat_by_id(selected)
#         sources = json.loads(src_json) if src_json else []
#         st.markdown(f"## 🔹 {q}")
#         st.markdown(ans)
#         st.markdown("### 📚 Sources")
#         for s in sources:
#             st.markdown(f"- [View Source PDF]({s})")
#         st.write("---")

#     # New query input
#     query = st.text_input("Ask a new question:")

#     if st.button("Submit"):
#         if query.strip():
#             with st.spinner("Generating answer..."):
#                 res = rag_pipeline(
#                     query.strip(),
#                     st.session_state.retriever,
#                     st.session_state.reranker,
#                     [(h[1], h[2], h[3]) for h in history_db]
#                 )
#                 save_chat(res["question"], res["answer"], res["sources"])
#                 st.session_state.selected_chat = None
#                 st.rerun()

#     st.write("")

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

# # ───────────────────────────────────────────────────────────────
# # Database / Path Settings
# # ───────────────────────────────────────────────────────────────

# DB_PATH = "rbi_scrape_text.db"
# CHAT_DB_PATH = "chat_history__.db"

# FAISS_DIR = "rbi_scrape_text_fixed"
# FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
# CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
# BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

# EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
# RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# INITIAL_TOP_K = 50
# RERANK_TOP_K = 20

# os.makedirs(FAISS_DIR, exist_ok=True)

# # ───────────────────────────────────────────────────────────────
# # Initialize Chat DB (with source column)
# # ───────────────────────────────────────────────────────────────

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

# # ───────────────────────────────────────────────────────────────
# # Helpers
# # ───────────────────────────────────────────────────────────────

# def sanitize(text: str) -> str:
#     return re.sub(r"\s+", " ", text).strip()

# # ───────────────────────────────────────────────────────────────
# # Retriever + Reranker
# # ───────────────────────────────────────────────────────────────

# class HybridRetriever:
#     def __init__(self):
#         self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
#         with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
#             self.metadata = json.load(f)

#         with open(BM25_PATH, "r", encoding="utf-8") as f:
#             bm25_data = json.load(f)
#         self.bm25 = BM25Okapi(bm25_data["corpus"])

#         self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)

#     def retrieve_semantic(self, query, top_k=INITIAL_TOP_K):
#         query_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
#         dists, idxs = self.faiss_index.search(query_emb, top_k)
#         results = []
#         for dist, idx in zip(dists[0], idxs[0]):
#             if idx < len(self.metadata):
#                 doc = self.metadata[idx].copy()
#                 doc["semantic_score"] = float(1/(1 + dist))
#                 results.append(doc)
#         return results

#     def retrieve_bm25(self, query, top_k=INITIAL_TOP_K):
#         tokens = query.lower().split()
#         scores = self.bm25.get_scores(tokens)
#         top_idxs = np.argsort(scores)[-top_k:][::-1]
#         results = []
#         for i in top_idxs:
#             if i < len(self.metadata):
#                 doc = self.metadata[i].copy()
#                 doc["bm25_score"] = float(scores[i])
#                 results.append(doc)
#         return results

#     def hybrid_retrieve(self, query):
#         sem = self.retrieve_semantic(query)
#         bm25 = self.retrieve_bm25(query)

#         merged = {}
#         for r in sem:
#             merged[r["chunk_text"]] = {**r, "bm25_score":0}
#         for r in bm25:
#             key = r["chunk_text"]
#             if key in merged:
#                 merged[key]["bm25_score"] = r["bm25_score"]
#             else:
#                 merged[key] = {**r, "semantic_score":0}

#         combined = list(merged.values())
#         if combined:
#             max_sem = max(r["semantic_score"] for r in combined)
#             max_bm  = max(r["bm25_score"] for r in combined)
#             for r in combined:
#                 ns = r["semantic_score"]/max_sem if max_sem else 0
#                 nb = r["bm25_score"]/max_bm if max_bm else 0
#                 r["hybrid_score"] = 0.7*ns + 0.3*nb

#         combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
#         return combined[:INITIAL_TOP_K]

# class Reranker:
#     def __init__(self):
#         self.model = CrossEncoder(RERANK_MODEL_NAME)

#     def rerank(self, query, chunks):
#         if not chunks:
#             return []
#         scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])
#         for c, s in zip(chunks, scores):
#             c["rerank_score"] = float(s)
#         return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:RERANK_TOP_K]

# # ───────────────────────────────────────────────────────────────
# # Answer Gen + RAG Pipeline
# # ───────────────────────────────────────────────────────────────

# def build_history_context(history):
#     parts = []
#     for q, a, _ in history[-3:]:
#         parts.append(f"Q: {q}\nA: {a}")
#     return "\n\n".join(parts)

# def generate_answer(query, reranked, history):
#     ctx = ""
#     for i, c in enumerate(reranked[:5], 1):
#         ctx += f"[{i}] {c['chunk_text']}\n"
#     hist_txt = build_history_context(history) if history else ""
#     prompt = f"""
# You are an expert RBI regulatory assistant.

# History:
# {hist_txt}

# Context:
# {ctx}

# Question:
# {query}

# Answer with concise explanation and citation references.
# """
#     try:
#         client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#         res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
#         return res.text.strip()
#     except Exception as e:
#         return f"LLM Error: {e}"

# def rag_pipeline(query, retriever, reranker, history):
#     reranked = reranker.rerank(query, retriever.hybrid_retrieve(query))
#     answer_text = generate_answer(query, reranked, history)
#     sources = list({c["pdf_url"] for c in reranked if c.get("pdf_url")})
#     return {"question": query, "answer": answer_text, "sources": sources}

# # ───────────────────────────────────────────────────────────────
# # Streamlit UI
# # ───────────────────────────────────────────────────────────────

# def run_app():
#     st.set_page_config(page_title="RBI Circular QA", layout="wide")
#     st.title("🏦 RBI Circular QA Assistant")

#     if "retriever" not in st.session_state:
#         with st.spinner("Loading models..."):
#             st.session_state.retriever = HybridRetriever()
#             st.session_state.reranker = Reranker()

#     history_db = load_chat_history()

#     # ---------------- Sidebar ----------------
#     with st.sidebar:
#         st.header("📜 Chat History")
#         for chat_id, q, _, _ in history_db[::-1]:
#             label = q if len(q) <= 40 else q[:37] + "..."
#             if st.button(label, key=f"hist_{chat_id}"):
#                 st.session_state.navigate_to = chat_id

#     # ---------------- Main Chat Panel ----------------
#     selected = st.session_state.get("navigate_to", None)

#     # If navigating to a past message, just scroll to it
#     if selected:
#         st.markdown("---")
#         st.markdown("### 📌 Jumped To:")
#         for cid, q, ans, src_json in history_db:
#             if cid == selected:
#                 sources = json.loads(src_json)
#                 st.markdown(f"**Q:** {q}")
#                 st.markdown(ans)
#                 if sources:
#                     st.markdown("**Sources:**")
#                     for s in sources:
#                         st.markdown(f"- [View Source PDF]({s})")
#                 st.markdown("---")
#         st.session_state.navigate_to = None

#     # Show full threaded chat
#     for cid, q, ans, src_json in history_db:
#         sources = json.loads(src_json) if src_json else []
#         st.markdown(f"**Q:** {q}")
#         st.markdown(ans)
#         if sources:
#             st.markdown("**Sources:**")
#             for s in sources:
#                 st.markdown(f"- [View Source PDF]({s})")
#         st.write("---")

#     # New Query Input
#     query = st.text_input("Ask a new question:")

#     if st.button("Submit"):
#         if query.strip():
#             with st.spinner("Generating answer..."):
#                 res = rag_pipeline(
#                     query.strip(),
#                     st.session_state.retriever,
#                     st.session_state.reranker,
#                     [(h[1], h[2], h[3]) for h in history_db]
#                 )
#                 save_chat(res["question"], res["answer"], res["sources"])
#                 st.rerun()

#     st.write("")

# if __name__ == "__main__":
#     run_app()



#best one till now

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

# CHAT_DB_PATH = "History.db"

# FAISS_DIR = "rbi_scrape_text_fixed"
# FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
# CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
# BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

# EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
# RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# INITIAL_TOP_K = 50
# RERANK_TOP_K = 20

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

#     def retrieve_semantic(self, query, top_k=INITIAL_TOP_K):
#         query_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
#         dists, idxs = self.faiss_index.search(query_emb, top_k)
#         results = []
#         for dist, idx in zip(dists[0], idxs[0]):
#             if idx < len(self.metadata):
#                 doc = self.metadata[idx].copy()
#                 doc["semantic_score"] = float(1/(1 + dist))
#                 results.append(doc)
#         return results

#     def retrieve_bm25(self, query, top_k=INITIAL_TOP_K):
#         tokens = query.lower().split()
#         scores = self.bm25.get_scores(tokens)
#         top_idxs = np.argsort(scores)[-top_k:][::-1]
#         results = []
#         for i in top_idxs:
#             if i < len(self.metadata):
#                 doc = self.metadata[i].copy()
#                 doc["bm25_score"] = float(scores[i])
#                 results.append(doc)
#         return results

#     def hybrid_retrieve(self, query):
#         sem = self.retrieve_semantic(query)
#         bm25 = self.retrieve_bm25(query)
#         merged = {}
#         for r in sem:
#             merged[r["chunk_text"]] = {**r, "bm25_score":0}
#         for r in bm25:
#             key = r["chunk_text"]
#             if key in merged:
#                 merged[key]["bm25_score"] = r["bm25_score"]
#             else:
#                 merged[key] = {**r, "semantic_score":0}
#         combined = list(merged.values())
#         if combined:
#             max_sem = max(r["semantic_score"] for r in combined)
#             max_bm  = max(r["bm25_score"] for r in combined)
#             for r in combined:
#                 ns = r["semantic_score"]/max_sem if max_sem else 0
#                 nb = r["bm25_score"]/max_bm if max_bm else 0
#                 r["hybrid_score"] = 0.7*ns + 0.3*nb
#         combined.sort(key=lambda x: x["hybrid_score"], reverse=True)
#         return combined[:INITIAL_TOP_K]

# class Reranker:
#     def __init__(self):
#         self.model = CrossEncoder(RERANK_MODEL_NAME)

#     def rerank(self, query, chunks):
#         if not chunks:
#             return []
#         scores = self.model.predict([[query, c["chunk_text"]] for c in chunks])
#         for c, s in zip(chunks, scores):
#             c["rerank_score"] = float(s)
#         return sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)[:RERANK_TOP_K]

# def build_history_context(history):
#     parts = []
#     for q, a, _ in history[-3:]:
#         parts.append(f"Q: {q}\nA: {a}")
#     return "\n\n".join(parts)

# def generate_answer(query, reranked, history):
#     context_text = ""
#     for i, c in enumerate(reranked[:5], 1):
#         context_text += f"[{i}] {c['chunk_text']}\n"
#     hist_txt = build_history_context(history) if history else ""
#     prompt = f"""
# You are an expert RBI regulatory assistant.

# History:
# {hist_txt}

# Context:
# {context_text}

# Question:
# {query}

# Answer with concise explanation and mention sources.
# """
#     client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
#     try:
#         res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
#         return res.text.strip()
#     except Exception as e:
#         return f"LLM Error: {e}"

# def rag_pipeline(query, retriever, reranker, history):
#     reranked = reranker.rerank(query, retriever.hybrid_retrieve(query))
#     answer_text = generate_answer(query, reranked, history)
#     unique_sources = {}
#     for c in reranked:
#         url = c.get("pdf_url")
#         title = c.get("title", "RBI Circular")
#         if url:
#             unique_sources[url] = title
#     return {"question": query, "answer": answer_text, "sources": unique_sources}

# def run_app():
#     st.set_page_config(page_title="RBI Circular QA", layout="wide")
#     st.title("🏦 RBI Circular QA Assistant")

#     if "retriever" not in st.session_state:
#         with st.spinner("Loading models..."):
#             st.session_state.retriever = HybridRetriever()
#             st.session_state.reranker  = Reranker()

#     history_db = load_chat_history()

#     # Sidebar
#     with st.sidebar:
#         st.header("📜 Chat History")
#         for chat_id, q, _, _ in history_db[::-1]:
#             label = q if len(q) <= 40 else q[:37] + "..."
#             if st.button(label, key=f"hist_{chat_id}"):
#                 st.session_state.navigate_to = chat_id

#     selected = st.session_state.get("navigate_to", None)

#     if selected:
#         for cid, q, ans, src_json in history_db:
#             if cid == selected:
#                 st.markdown(f"### 📌 {q}")
#                 st.markdown(ans)
#                 sources = json.loads(src_json)
#                 if sources:
#                     st.markdown("#### 📚 Sources")
#                     for url, title in sources.items():
#                         st.markdown(f"📄 {title}   [🔗]({url})")
#                 st.markdown("---")
#         st.session_state.navigate_to = None

#     # Chat panel (full)
#     for cid, q, ans, src_json in history_db:
#         sources = json.loads(src_json)
#         st.markdown(f"**Q:** {q}")
#         st.markdown(ans)
#         if sources:
#             st.markdown("**Sources:**")
#             for url, title in sources.items():
#                 st.markdown(f"📄 {title}   [🔗]({url})")
#         st.write("---")

#     # NEW QUESTION FORM
#     with st.form("ask_form", clear_on_submit=True):
#         query = st.text_input("Ask a new question:")
#         submitted = st.form_submit_button("Submit")
#         if submitted and query.strip():
#             with st.spinner("Generating answer..."):
#                 res = rag_pipeline(
#                     query.strip(),
#                     st.session_state.retriever,
#                     st.session_state.reranker,
#                     [(h[1], h[2], h[3]) for h in history_db]
#                 )
#                 save_chat(res["question"], res["answer"], res["sources"])
#                 st.rerun()

# if __name__ == "__main__":
#     run_app()


# it's also properly working

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
# Settings
CHAT_DB_PATH = "_History.db"
FAISS_DIR = "rbi_scrape_text_fixed"
FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

MAX_SOURCES = 6  # show only top 6 sources

INITIAL_TOP_K = 50
RERANK_TOP_K = 20

# Initialize Chat DB
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

# Retriever + Reranker
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
                ns = r["semantic_score"]/max_sem if max_sem else 0
                nb = r["bm25_score"]/max_bm if max_bm else 0
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

# RAG Pipeline
def build_history_context(history):
    parts = []
    for q, a, _ in history[-3:]:
        parts.append(f"Q: {q}\nA: {a}")
    return "\n\n".join(parts)

def generate_answer(query, reranked, history):
    context_text = ""
    for i, c in enumerate(reranked[:5], 1):
        context_text += f"[{i}] {c['chunk_text']}\n"
    hist_txt = build_history_context(history) if history else ""
    prompt = f"""
You are an expert RBI regulatory assistant.

History:
{hist_txt}

Context:
{context_text}

Question:
{query}

Answer concisely with citation references.
"""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        text = res.text.strip()
        return text
    except Exception as e:
        return f"LLM Error: {e}"

def rag_pipeline(query, retriever, reranker, history):
    reranked = reranker.rerank(query, retriever.hybrid_retrieve(query))
    answer_text = generate_answer(query, reranked, history)

    # if irrelevant, no sources
    if "no information" in answer_text.lower():
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


# Streamlit UI

def run_app():
    st.set_page_config(layout="wide", page_title="RBI Circular QA Assistant")

    if "retriever" not in st.session_state:
        with st.spinner("Loading models..."):
            st.session_state.retriever = HybridRetriever()
            st.session_state.reranker  = Reranker()

    chat_history = load_chat_history()

    # ───────────────── Sidebar
    with st.sidebar:
        st.markdown("## 🧠 Chat History")

        # New Chat button does NOT clear sidebar history
        if st.button("🆕 New Chat"):
            # Clear only main chat display state, not DB
            st.session_state.clear_history_view = True

        # show history in reverse order (latest first)
        for cid, q, _, _ in chat_history[::-1]:
            label = q if len(q) <= 30 else q[:27] + "..."
            # give consistent spacing and style
            if st.button(f"🗨️  {label}", key=f"hist_{cid}"):
                st.session_state.jump_to = cid

    # ───────────────── Main Chat Panel
    selected = st.session_state.get("jump_to", None)
    clear_view = st.session_state.get("clear_history_view", False)

    # if New Chat was clicked
    if clear_view:
        st.markdown("### 🆕 New Chat Started")
        st.write("Ask a new question below")
        st.session_state.jump_to = None
        st.session_state.clear_history_view = False

    # if user clicked history
    elif selected:
        for cid, q, ans, src_json in chat_history:
            if cid == selected:
                st.markdown(f"### ↩︎ {q}")
                st.markdown(ans)
                sources = json.loads(src_json)
                if sources:
                    st.markdown("**Sources:**")
                    for url, title in sources.items():
                        st.markdown(f"📄 {title} [🔗]({url})")
                st.markdown("---")
        st.session_state.jump_to = None

    # default: show threaded chat
    else:
        for cid, q, ans, src_json in chat_history:
            sources = json.loads(src_json)
            st.markdown(f"**Q:** {q}")
            st.markdown(ans)
            if sources:
                st.markdown("**Sources:**")
                for url, title in sources.items():
                    st.markdown(f"📄 {title} [🔗]({url})")
            st.write("---")

    # ───────────────── Bottom Input (fixed)
    with st.form(key="ask_form", clear_on_submit=True):
        query = st.text_input("Ask a new question:", "")
        submitted = st.form_submit_button("Submit")
        if submitted and query.strip():
            with st.spinner("Generating answer..."):
                res = rag_pipeline(
                    query.strip(),
                    st.session_state.retriever,
                    st.session_state.reranker,
                    [(h[1], h[2], h[3]) for h in chat_history]
                )
                save_chat(res["question"], res["answer"], res["sources"])
                st.rerun()


if __name__ == "__main__":
    run_app()
