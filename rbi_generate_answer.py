# rbi_generate_answer.py

from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

# Create Gemini client (NEW SDK)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


#version 1
# def generate_answer(query: str, chunks: list):
#     context = "\n\n".join(
#         [f"- {c['chunk_text']}" for c in chunks]
#     )

#     prompt = f"""
# You are an expert assistant answering questions using RBI circulars only.

# Rules:
# - Use ONLY the provided context
# - Give a complete, well-structured answer
# - Do NOT stop mid-sentence
# - If the answer is not present, say clearly: "Not found in RBI circulars"

# Context:
# {context}

# Question:
# {query}
# """

#     response = client.models.generate_content(
#         model=GEMINI_MODEL,
#         contents=prompt
#     )

#     return response.text

# version 2: this is correct but it's giving name of the PDF in answer instead of title of the circular.
def generate_answer(query: str, chunks: list):
    context = "\n\n".join([f"- {c['chunk_text']}" for c in chunks])

#     prompt = f"""
# You are an expert RBI assistant. Use the RBI circular context below and answer the question.

# Rules:
# - Use ONLY the provided context.
# - Provide a clear direct answer.
# - Express the *meaning*, not just extract a sentence.
# - Provide a short explanation that shows how you arrived at the answer.
# - If the answer cannot be found, respond exactly: "Not found in RBI circulars."

# Context:
# {context}

# User question:
# {query}

# Answer:
# """

    prompt = f"""
You are an expert RBI regulatory assistant.

Use the RBI circular context below to answer the user's question.

Rules:
- Use ONLY the provided context.
- Give a clear and direct answer.
- Explain briefly how the answer is derived.
- When referring to a circular, use its official title and/or date if mentioned.
- DO NOT mention PDF filenames, internal document IDs, hashes, or file names.
- If the answer is not explicitly stated in the context, respond exactly:
  "Not found in RBI circulars."

Context:
{context}

User question:
{query}

Answer:
"""


    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    return response.text.strip()
