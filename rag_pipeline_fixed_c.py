"""
Complete Fixed RBI RAG Pipeline
- Multi-line title extraction
- Better chunking with sentence boundaries
- Cross-encoder re-ranking
- Hybrid search (semantic + BM25)
- Conversation context
- Proper error handling

    FAISS index: rbi_scrape_text_fixed\rbi_chunks.index
    Metadata: rbi_scrape_text_fixed\rbi_chunk_metadata.json
    BM25 index: rbi_scrape_text_fixed\bm25_index.json
"""

import os
import re
import sqlite3
import json
import faiss
import numpy as np
from typing import List, Dict, Tuple, Optional
from tqdm import tqdm

# Models
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

# LLM
from google import genai
from dotenv import load_dotenv

# UI
import streamlit as st

load_dotenv()

DB_PATH = "rbi_scrape_text.db"
FAISS_DIR = "rbi_scrape_text_fixed"
os.makedirs(FAISS_DIR, exist_ok=True)

FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")
BM25_PATH = os.path.join(FAISS_DIR, "bm25_index.json")

# Models
EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Chunking (character-based, not word-based)
CHUNK_SIZE = 512  # characters
CHUNK_OVERLAP = 100  # characters

# Retrieval
INITIAL_TOP_K = 50  # Initial semantic retrieval
RERANK_TOP_K = 20  # After re-ranking

def sanitize(text: str) -> str:
    """Clean text."""
    return re.sub(r"\s+", " ", text).strip()

def chunk_text_with_sentences(text: str, chunk_size: int = CHUNK_SIZE, 
                              overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Chunk text respecting sentence boundaries.
    Better than word-based splitting.
    """
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_length = len(sentence)
        
        if current_length + sentence_length > chunk_size and current_chunk:
            # Save current chunk
            chunks.append(" ".join(current_chunk))
            
            # Start new chunk with overlap
            # Keep last few sentences for context
            overlap_sentences = []
            overlap_length = 0
            for s in reversed(current_chunk):
                if overlap_length + len(s) <= overlap:
                    overlap_sentences.insert(0, s)
                    overlap_length += len(s)
                else:
                    break
            
            current_chunk = overlap_sentences
            current_length = overlap_length
        
        current_chunk.append(sentence)
        current_length += sentence_length
    
    # Add final chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def build_index():
    """Build FAISS index and BM25 index."""
    print(f"{'='*70}")
    print(f"  BUILDING INDEXES")
    print(f"{'='*70}\n")
    
    # Load from database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT ref_no, title, issue_date, pdf_url, body_text
        FROM circulars
    """)
    rows = cur.fetchall()
    conn.close()
    
    print(f"📄 Loaded {len(rows)} circulars\n")
    
    # Load embedding model
    print(f"🧠 Loading embedding model: {EMBED_MODEL_NAME}")
    model = SentenceTransformer(EMBED_MODEL_NAME)
    
    # Initialize
    faiss_index = None
    chunk_metadata = []
    bm25_corpus = []  # For BM25
    
    for ref_no, title, issue_date, pdf_url, body_text in tqdm(
        rows, desc="Chunking & embedding"
    ):
        if not body_text:
            continue
        
        # Combine title and body for context
        full_text = f"{title}\n\n{sanitize(body_text)}"
        
        # Create chunks (sentence-aware)
        chunks = chunk_text_with_sentences(full_text, CHUNK_SIZE, CHUNK_OVERLAP)
        
        if not chunks:
            continue
        
        # Generate embeddings
        embeddings = model.encode(
            chunks,
            normalize_embeddings=True,
            show_progress_bar=False
        ).astype("float32")
        
        # Initialize FAISS index
        if faiss_index is None:
            dim = embeddings.shape[1]
            faiss_index = faiss.IndexFlatL2(dim)
        
        # Add to FAISS
        faiss_index.add(embeddings)
        
        # Store metadata and BM25 corpus
        for i, chunk in enumerate(chunks):
            chunk_metadata.append({
                "ref_no": ref_no,
                "title": title,
                "issue_date": issue_date,
                "pdf_url": pdf_url,
                "chunk_index": i,
                "chunk_text": chunk
            })
            
            # Tokenize for BM25
            bm25_corpus.append(chunk.lower().split())
    
    # Save FAISS
    faiss.write_index(faiss_index, FAISS_INDEX_PATH)
    
    # Save metadata
    with open(CHUNK_META_PATH, "w", encoding="utf-8") as f:
        json.dump(chunk_metadata, f, indent=2)
    
    # Build and save BM25
    print("\n🔤 Building BM25 index...")
    bm25 = BM25Okapi(bm25_corpus)
    
    # Save BM25 parameters (we'll rebuild on load)
    bm25_data = {
        "corpus": bm25_corpus,
        "doc_freqs": list(bm25.doc_freqs),
        "idf": {k: v for k, v in bm25.idf.items()},
        "avgdl": bm25.avgdl,
        "doc_len": list(bm25.doc_len)
    }
    
    with open(BM25_PATH, "w", encoding="utf-8") as f:
        json.dump(bm25_data, f)
    
    print(f"\n{'='*70}")
    print(f"  INDEX BUILD COMPLETE")
    print(f"{'='*70}")
    print(f"Total chunks: {len(chunk_metadata)}")
    print(f"FAISS index: {FAISS_INDEX_PATH}")
    print(f"Metadata: {CHUNK_META_PATH}")
    print(f"BM25 index: {BM25_PATH}")
    print(f"{'='*70}\n")

class HybridRetriever:
    """Hybrid retrieval combining FAISS (semantic) and BM25 (keyword)."""
    
    def __init__(self):
        """Initialize retriever."""
        print("🔍 Loading retrieval models...")
        
        # Load FAISS
        self.faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        
        # Load metadata
        with open(CHUNK_META_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        
        # Load BM25
        with open(BM25_PATH, "r", encoding="utf-8") as f:
            bm25_data = json.load(f)
        
        self.bm25_corpus = bm25_data["corpus"]
        self.bm25 = BM25Okapi(self.bm25_corpus)
        
        # Load embedding model
        self.embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        
        print(f"✓ Loaded {len(self.metadata)} chunks\n")
    
    def retrieve_semantic(self, query: str, top_k: int = INITIAL_TOP_K) -> List[Dict]:
        """Semantic retrieval using FAISS."""
        query_emb = self.embed_model.encode(
            [query],
            normalize_embeddings=True
        ).astype("float32")
        
        distances, indices = self.faiss_index.search(query_emb, top_k)
        
        results = []
        for rank, idx in enumerate(indices[0]):
            if idx < len(self.metadata):
                result = self.metadata[idx].copy()
                result["semantic_score"] = float(1 / (1 + distances[0][rank]))
                results.append(result)
        
        return results
    
    def retrieve_bm25(self, query: str, top_k: int = INITIAL_TOP_K) -> List[Dict]:
        """Keyword retrieval using BM25."""
        query_tokens = query.lower().split()
        scores = self.bm25.get_scores(query_tokens)
        
        # Get top-k indices
        top_indices = np.argsort(scores)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            if idx < len(self.metadata):
                result = self.metadata[idx].copy()
                result["bm25_score"] = float(scores[idx])
                results.append(result)
        
        return results
    
    def hybrid_retrieve(self, query: str, top_k: int = INITIAL_TOP_K,
                       alpha: float = 0.7) -> List[Dict]:
        """
        Hybrid retrieval combining semantic and BM25.
        
        Args:
            query: Search query
            top_k: Number of results
            alpha: Weight for semantic (1-alpha for BM25)
        """
        # Get both results
        semantic_results = self.retrieve_semantic(query, top_k)
        bm25_results = self.retrieve_bm25(query, top_k)
        
        # Merge and normalize scores
        all_results = {}
        
        # Add semantic scores
        for result in semantic_results:
            key = result["chunk_text"]
            all_results[key] = {
                **result,
                "semantic_score": result["semantic_score"],
                "bm25_score": 0.0
            }
        
        # Add BM25 scores
        for result in bm25_results:
            key = result["chunk_text"]
            if key in all_results:
                all_results[key]["bm25_score"] = result["bm25_score"]
            else:
                all_results[key] = {
                    **result,
                    "semantic_score": 0.0,
                    "bm25_score": result["bm25_score"]
                }
        
        # Calculate hybrid score
        results = list(all_results.values())
        
        # Normalize scores to [0, 1]
        if results:
            max_semantic = max(r["semantic_score"] for r in results)
            max_bm25 = max(r["bm25_score"] for r in results)
            
            for r in results:
                norm_semantic = r["semantic_score"] / max_semantic if max_semantic > 0 else 0
                norm_bm25 = r["bm25_score"] / max_bm25 if max_bm25 > 0 else 0
                r["hybrid_score"] = alpha * norm_semantic + (1 - alpha) * norm_bm25
        
        # Sort by hybrid score
        results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        
        return results[:top_k]

class Reranker:
    """Re-rank using cross-encoder."""
    
    def __init__(self):
        """Initialize re-ranker."""
        print(f"🎯 Loading re-ranker: {RERANK_MODEL_NAME}")
        self.model = CrossEncoder(RERANK_MODEL_NAME)
        print("✓ Re-ranker loaded\n")
    
    def rerank(self, query: str, chunks: List[Dict], 
               top_k: int = RERANK_TOP_K) -> List[Dict]:
        """Re-rank chunks using cross-encoder."""
        if not chunks:
            return []
        
        # Prepare pairs
        pairs = [[query, c["chunk_text"]] for c in chunks]
        
        # Get scores
        scores = self.model.predict(pairs)
        
        # Add scores
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)
        
        # Sort and return top-k
        reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]

def generate_answer(query: str, chunks: List[Dict], 
                   conversation_history: List[Dict] = None) -> str:
    """Generate answer using Gemini with conversation context."""
    
    # Build context with source attribution
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title", "Unknown")
        date = chunk.get("issue_date", "N/A")
        ref = chunk.get("ref_no", "N/A")
        text = chunk["chunk_text"]
        
        context_parts.append(
            f"[Source {i}] {title} ({ref}, {date})\n{text}"
        )
    
    context = "\n\n".join(context_parts)
    
    # Add conversation history if available
    history_text = ""
    if conversation_history:
        history_parts = []
        for turn in conversation_history[-3:]:  # Last 3 turns
            history_parts.append(f"Q: {turn['question']}\nA: {turn['answer']}")
        history_text = "\n\n".join(history_parts)
    
    # Build prompt
    history_section = f"Previous conversation:\n{history_text}\n\n" if history_text else ""
        
    prompt = f"""You are an expert RBI regulatory assistant with access to official RBI circulars.

    {history_section}Current question: {query}

    Context from RBI circulars:
    {context}

    Instructions:
    1. Answer ONLY based on the provided context
    2. Cite sources using [Source X] notation
    3. If information is not in the context, say "This information is not available in the provided circulars"
    4. Be clear, concise, and accurate
    5. If the question is a follow-up, use conversation history for context
    6. DO NOT mention PDF filenames or internal IDs

    Answer:"""

   
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return response.text.strip()
    
    except Exception as e:
        return f"Error generating answer: {str(e)}"

def rag_pipeline(query: str, retriever: HybridRetriever, 
                reranker: Reranker, conversation_history: List[Dict] = None) -> Dict:
    """Complete RAG pipeline."""
    
    # Step 1: Hybrid retrieval
    retrieved_chunks = retriever.hybrid_retrieve(query, top_k=INITIAL_TOP_K)
    
    # Step 2: Re-rank
    reranked_chunks = reranker.rerank(query, retrieved_chunks, top_k=RERANK_TOP_K)
    
    # Step 3: Generate answer
    answer = generate_answer(query, reranked_chunks, conversation_history)
    
    return {
        "answer": answer,
        "sources": reranked_chunks[:5],  # Top 5 sources
        "num_retrieved": len(retrieved_chunks),
        "num_reranked": len(reranked_chunks)
    }

def run_streamlit_app():
    """Run Streamlit UI."""
    st.set_page_config(
        page_title="RBI Circular Q&A System",
        page_icon="🏦",
        layout="wide"
    )
    
    st.title("🏦 RBI Circular Question Answering System")
    st.markdown("Ask questions about RBI circulars. Supports follow-up questions!")
    
    # Initialize session state
    if "history" not in st.session_state:
        st.session_state.history = []
    
    if "retriever" not in st.session_state:
        with st.spinner("Loading models..."):
            try:
                st.session_state.retriever = HybridRetriever()
                st.session_state.reranker = Reranker()
                st.success("✓ Models loaded successfully!")
            except Exception as e:
                st.error(f"Error loading models: {e}")
                st.stop()
    
    # Query input
    col1, col2 = st.columns([4, 1])
    
    with col1:
        query = st.text_input(
            "Your question:",
            placeholder="e.g., What are the KYC requirements for banks?",
            key="query_input"
        )
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        ask_button = st.button("🔍 Ask", use_container_width=True)
    
    if ask_button and query.strip():
        with st.spinner("Searching and generating answer..."):
            try:
                # Run RAG pipeline
                result = rag_pipeline(
                    query,
                    st.session_state.retriever,
                    st.session_state.reranker,
                    st.session_state.history
                )
                
                # Add to history
                st.session_state.history.append({
                    "question": query,
                    "answer": result["answer"],
                    "sources": result["sources"]
                })
                
                st.rerun()
                
            except Exception as e:
                st.error(f"Error: {e}")
    
    # Display conversation history
    if st.session_state.history:
        st.markdown("---")
        
        for i, turn in enumerate(reversed(st.session_state.history), 1):
            with st.container():
                st.markdown(f"### Q{len(st.session_state.history) - i + 1}: {turn['question']}")
                st.markdown(turn["answer"])
                
                # Show sources
                with st.expander("📚 View Sources"):
                    for j, source in enumerate(turn["sources"], 1):
                        st.markdown(f"**{j}. {source['title']}**")
                        st.markdown(f"*Ref: {source['ref_no']} | Date: {source['issue_date']}*")
                        st.markdown(f"Score: {source.get('rerank_score', 0):.4f}")
                        st.text(source["chunk_text"][:300] + "...")
                        st.markdown(f"[View PDF]({source['pdf_url']})")
                        st.markdown("---")
                
                st.markdown("---")
        
        # Clear history button
        if st.button("🗑️ Clear History"):
            st.session_state.history = []
            st.rerun()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        # Build index
        build_index()
    
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test pipeline
        print("Testing RAG pipeline...\n")
        
        retriever = HybridRetriever()
        reranker = Reranker()
        
        test_queries = [
            "What are KYC requirements?",
            "Basel III liquidity standards",
            "Net Stable Funding Ratio"
        ]
        
        for query in test_queries:
            print(f"\nQuery: {query}")
            print("="*70)
            
            result = rag_pipeline(query, retriever, reranker)
            
            print(f"\nAnswer:\n{result['answer']}\n")
            print(f"Retrieved: {result['num_retrieved']}, Re-ranked: {result['num_reranked']}")
            print("\nTop 3 Sources:")
            for i, s in enumerate(result['sources'][:3], 1):
                print(f"{i}. {s['title']} (Score: {s['rerank_score']:.4f})")
            print("\n" + "="*70)
    
    else:
        # Run Streamlit app
        run_streamlit_app()