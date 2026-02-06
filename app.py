# import streamlit as st

# from rbi_rag_pipeline import (
#     retrieve_and_rerank,
#     build_answer_prompt,
#     call_gemini
# )

# st.set_page_config(
#     page_title="RBI Circular Question Answering System",
#     layout="wide"
# )

# st.title("🏦 RBI Circular Question Answering System")
# st.markdown(
#     "Ask questions related to RBI circulars. "
   
# )

# query = st.text_input(
#     "Enter your question:",
#     placeholder="Why did RBI increase the LTV ratio for loans against gold ornaments?"
# )

# if query:
#     with st.spinner("Generating answer..."):
#         retrieved = retrieve_and_rerank(query)

#         if not retrieved:
#             st.error("No relevant RBI circular found.")
#         else:
#             # Generate answer
#             answer_prompt = build_answer_prompt(query, retrieved)
#             answer = call_gemini(answer_prompt)

#             # ---------------- OUTPUT ----------------
#             st.subheader("\t\tAnswer:")
#             st.write(answer)

#             st.subheader("🔗 Related RBI Circulars")
#             for i, c in enumerate(retrieved[:3], 1):
#                 st.markdown(f"{i}. [{c['pdf_url']}]({c['pdf_url']})")


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

st.title("🏦 RBI Circular Question Answering System!")
st.markdown(
    "Ask questions related to RBI circulars. You can ask follow-ups after the previous answer."
)

# Initialize conversation history
if "history" not in st.session_state:
    st.session_state.history = []

# Input area
query = st.text_input(
    "Enter your question below:",
    value="",
    key="user_query",
    placeholder="e.g., Why did RBI increase the LTV ratio for loans against gold ornaments?"
)

# Ask button
if st.button("Ask"):
    if not query.strip():
        st.warning("Please enter a question before submitting.")
    else:
        with st.spinner("Generating answer..."):
            # Retrieve and rerank chunks
            retrieved = retrieve_and_rerank(query)

            if not retrieved:
                answer = "No relevant RBI circular content found."
            else:
                # Generate answer via LLM
                answer_prompt = build_answer_prompt(query, retrieved)
                answer = call_gemini(answer_prompt)

            # Append to history
            st.session_state.history.append({
                "question": query,
                "answer": answer,
                "sources": retrieved
            })

        # Clear the input safely by resetting the widget key
        # Instead of direct assignment, we recreate the input on next rerun
        # st.experimental_rerun()
        st.rerun()

# Show conversation history
if st.session_state.history:
    st.markdown("---")
    st.subheader("💬 Conversation History")
    for i, turn in enumerate(st.session_state.history, start=1):
        st.markdown(f"**Q{i}:** {turn['question']}")
        st.write(turn["answer"])

        if turn["sources"]:
            st.markdown("📄 Related RBI Circulars:")
            for idx, c in enumerate(turn["sources"][:3], 1):
                st.markdown(f"{idx}. [{c['pdf_url']}]({c['pdf_url']})")

        st.markdown("---")
