import streamlit as st

from rbi_rag_pipeline import (
    retrieve_and_rerank,
    build_answer_prompt,
    call_gemini
)

st.set_page_config(
    page_title="RBI Circular Question Answering System",
    layout="wide"
)

st.title("🏦 RBI Circular Question Answering System")
st.markdown(
    "Ask questions related to RBI circulars. "
    "Answers are generated using RAG (FAISS + BM25 + Reranking + Gemini)."
)

query = st.text_input(
    "Enter your question:",
    placeholder="Why did RBI increase the LTV ratio for loans against gold ornaments?"
)

if query:
    with st.spinner("Generating answer..."):
        retrieved = retrieve_and_rerank(query)

        if not retrieved:
            st.error("No relevant RBI circular found.")
        else:
            # Generate answer
            answer_prompt = build_answer_prompt(query, retrieved)
            answer = call_gemini(answer_prompt)

            # ---------------- OUTPUT ----------------
            st.subheader("✅ Answer")
            st.write(answer)

            st.subheader("🔗 Related RBI Circulars")
            for i, c in enumerate(retrieved[:3], 1):
                st.markdown(f"{i}. [{c['pdf_url']}]({c['pdf_url']})")
