import os
import re
import sqlite3
import json
import faiss
from tqdm import tqdm
from sentence_transformers import SentenceTransformer


# DB_PATH = "scrape_rbi_pdf_and_ext.db" 
DB_PATH = "rbi_scrape_text.db"

# FAISS_DIR = "rbi_faiss_store"

FAISS_DIR = "rbi_scrape_text"
os.makedirs(FAISS_DIR, exist_ok=True)

FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "rbi_chunks.index")
CHUNK_META_PATH = os.path.join(FAISS_DIR, "rbi_chunk_metadata.json")

EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"

CHUNK_SIZE = 300      # words
CHUNK_OVERLAP = 50    # words


def sanitize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def chunk_text_with_overlap(text: str, size: int, overlap: int):
    words = text.split()         
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i + size]
        if not chunk:
            break
        chunks.append(" ".join(chunk))
        i += size - overlap
    return chunks


conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
SELECT ref_no, title, issue_date, pdf_url, body_text
FROM circulars
""")

rows = cur.fetchall()
conn.close()

print(f"📄 Loaded {len(rows)} RBI circulars")


print(f"🧠 Loading embedding model: {EMBED_MODEL_NAME}")
model = SentenceTransformer(EMBED_MODEL_NAME)

faiss_index = None
chunk_metadata = []
vector_count = 0

for ref_no, title, issue_date, pdf_url, body_text in tqdm(
    rows, desc="Chunking & embedding"
):
    if not body_text:
        continue

    clean_text = sanitize(body_text)
    chunks = chunk_text_with_overlap(
        clean_text,
        CHUNK_SIZE,
        CHUNK_OVERLAP
    )

    if not chunks:
        continue

    embeddings = model.encode(
        chunks,
        normalize_embeddings=True,
        show_progress_bar=False
    ).astype("float32")

    if faiss_index is None:
        dim = embeddings.shape[1]
        faiss_index = faiss.IndexFlatL2(dim)

    faiss_index.add(embeddings)

    for i, chunk in enumerate(chunks):
        chunk_metadata.append({
            "ref_no": ref_no,
            "title": title,
            "issue_date": issue_date,
            "pdf_url": pdf_url,
            "chunk_index": i,
            "chunk_text": chunk
        })
        vector_count += 1

faiss.write_index(faiss_index, FAISS_INDEX_PATH)

with open(CHUNK_META_PATH, "w", encoding="utf-8") as f:
    json.dump(chunk_metadata, f, indent=2)

print("\nRBI FAISS indexing complete")
print(f"🔢 Total chunks: {vector_count}")
print(f"📁 FAISS index: {FAISS_INDEX_PATH}")
print(f"📄 Metadata: {CHUNK_META_PATH}")
