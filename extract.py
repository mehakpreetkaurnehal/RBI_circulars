import os
import re
import time
import requests

# PyMuPDF is imported as fitz
import fitz

from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# -------------- DATABASE SETUP --------------

engine = create_engine("sqlite:///Extract.db", echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Circular(Base):
    __tablename__ = "circulars"
    id = Column(Integer, primary_key=True)
    ref_no = Column(String)
    issue_date = Column(String)
    title = Column(String)
    pdf_url = Column(String, unique=True)
    body_text = Column(Text)

Base.metadata.create_all(engine)

# -------------- CONSTANTS ------------------

PDF_DIR = "Extract"
os.makedirs(PDF_DIR, exist_ok=True)

# Use the *new circulars index detail page URL pattern* 
DETAIL_BASE = "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx?Id="

# ---------------- HELPERS -------------------

def fetch_html(url):
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print("Error fetching:", url, e)
        return ""

def extract_pdf_url_from_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a", href=re.compile(r"PDFs/.+\.PDF", re.IGNORECASE))
    if link and "href" in link.attrs:
        href = link["href"]
        if href.startswith("http"):
            return href
        return "https://rbidocs.rbi.org.in/rdocs/Notification/PDFs/" + href.split("/")[-1]
    return None

def download_pdf(pdf_url):
    filename = os.path.join(PDF_DIR, pdf_url.split("/")[-1])
    if os.path.exists(filename):
        return filename
    try:
        r = requests.get(pdf_url, timeout=30)
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
        return filename
    except Exception as e:
        print("PDF download failed:", e)
        return None

def extract_text_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = []
        for pg in doc:
            text.append(pg.get_text())
        doc.close()
        return "\n".join(text)
    except Exception as e:
        print("PDF extraction failed:", e)
        return ""

# ---------------- PARSE PDF TEXT ----------------

def parse_pdf_text(text):
    """
    Better parsing logic:
    - Find circular ref
    - Find issue date
    - Combine all lines between ref & date as full title
    - Everything below date is body
    """

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    ref_no = ""
    issue_date = ""
    title_lines = []
    body_lines = []

    # Patterns
    ref_pattern = r"RBI/\d{4}-\d{2}/\d+"
    date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

    stage = "find_ref"

    for ln in lines:

        # → FIND CIRCULAR REFERENCE
        if stage == "find_ref":
            m = re.search(ref_pattern, ln)
            if m:
                ref_no = m.group(0)
                stage = "collect_title"
            continue

        # → COLLECT TITLE UNTIL DATE
        if stage == "collect_title":
            # look for the date
            m_date = re.search(date_pattern, ln)
            if m_date:
                issue_date = m_date.group(0)
                stage = "collect_body"
                continue
            # if not date yet, this is part of title
            title_lines.append(ln)
            continue

        # → BODY AFTER DATE
        if stage == "collect_body":
            body_lines.append(ln)

    full_title = " ".join(title_lines)

    body_text = "\n".join(body_lines)
    return ref_no, issue_date, full_title, body_text

# ---------------- PROCESS ---------------------

def process_circular_by_id(id_list):
    session = Session()

    for cid in id_list:
        detail_url = f"{DETAIL_BASE}{cid}"
        html = fetch_html(detail_url)

        if not html:
            print(f"Skipping {cid} (no HTML)")
            continue

        pdf_url = extract_pdf_url_from_detail(html)
        if not pdf_url:
            print(f"No PDF found for ID {cid}")
            continue

        exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
        if exists:
            print(f"Already exists: {cid}")
            continue

        pdf_path = download_pdf(pdf_url)
        if not pdf_path:
            print(f"Failed download: {cid}")
            continue

        raw_text = extract_text_from_pdf(pdf_path)
        ref_no, issue_date, title, body_text = parse_pdf_text(raw_text)

        # store in DB
        circ = Circular(
            ref_no = ref_no,
            issue_date = issue_date,
            title = title,
            pdf_url = pdf_url,
            body_text = body_text
        )
        session.add(circ)
        session.commit()
        print(f"Stored → {ref_no} | {issue_date} | {title[:80]}")

        time.sleep(0.3)

    session.close()

# ---------------- RUN ------------------------

if __name__ == "__main__":
    # pull recent 10 circular IDs
    recent_ids = list(range(13240, 13250))
    process_circular_by_id(recent_ids)
    print("Done ✔")
