
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

def evaluate_answer(query: str, answer: str):
    prompt = f"""
You are evaluating an AI-generated answer.

Query:
{query}

Answer:
{answer}

Rate relevance from 0 to 1.
Explain briefly.

Return JSON only:
{{
  "score": number,
  "reason": string
}}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    return response.text
