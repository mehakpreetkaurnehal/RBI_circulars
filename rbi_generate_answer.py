# rbi_generate_answer.py

from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

# Create Gemini client (NEW SDK)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

def generate_answer(query: str, chunks: list):
    context = "\n\n".join(
        [f"- {c['chunk_text']}" for c in chunks]
    )

    prompt = f"""
You are an expert assistant answering questions using RBI circulars only.

Rules:
- Use ONLY the provided context
- Give a complete, well-structured answer
- Do NOT stop mid-sentence
- If the answer is not present, say clearly: "Not found in RBI circulars"

Context:
{context}

Question:
{query}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    return response.text
