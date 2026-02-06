
# from google import genai
# from dotenv import load_dotenv
# import os

# load_dotenv()

# client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# def evaluate_answer(query: str, answer: str):
#     prompt = f"""
# You are evaluating an AI-generated answer.

# Query:
# {query}

# Answer:
# {answer}

# Rate relevance from 0 to 1.
# Explain briefly.

# Return JSON only:
# {{
#   "score": number,
#   "reason": string
# }}
# """

#     response = client.models.generate_content(
#         model=GEMINI_MODEL,
#         contents=prompt
#     )

#     return response.text



# rbi_evaluate_answers.py

from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

def evaluate_answer(query: str, answer: str, context: str = None):
    """
    Evaluate the AI-generated answer on:
    - correctness (supported by context)
    - completeness (answer fully addresses the query)
    - meaning (expressed clearly and correctly)
    - if multiple valid ways of phrasing exist
    """

    prompt = f"""
You are evaluating an AI-generated answer.

Query:
{query}

Answer:
{answer}

Context (if available):
{context if context else "No context provided"}

You should evaluate on the following criteria:
1️⃣ **Correctness**: Does the answer correctly reflect facts relevant to the query?
2️⃣ **Completeness**: Does it fully answer the question?
3️⃣ **Meaning**: Does it express the correct meaning, even if phrased differently?
4️⃣ **Support by context**: If context is provided, does the answer rely only on this info?
5️⃣ **Semantic equivalence**: If the answer uses different wording but means the same thing, treat it as correct.

Return **JSON only** with:
- **score (0.0–1.0)**: overall quality (1.0 best)
- **reason**: concise human-readable explanation
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    return response.text.strip()
