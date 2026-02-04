#fetched only old circulars, code is good to use

import os
import re
import time
import requests
import fitz  # PyMuPDF4LLM
from bs4 import BeautifulSoup

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------- DATABASE SETUP ----------------
engine = create_engine("sqlite:///scrape_rbi_pdf_and_ext.db", echo=False)
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

# ---------------- CONSTANTS ----------------
INDEX_URL = "https://www.rbi.org.in/commonman/English/scripts/notification.aspx"
PDF_BASE = "https://www.rbi.org.in/commonman/Upload/English/Notification/PDFs/"

PDF_DIR = "pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

# ---------------- HELPER FUNCTIONS ----------------

def fetch_page(url):
    """Get HTML with retry."""
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print("Error fetching:", url, e)
        return None

def download_pdf(pdf_url):
    """Download a PDF if not exists locally."""
    filename = os.path.join(PDF_DIR, pdf_url.split("/")[-1])
    if not os.path.isfile(filename):
        print("📥 Downloading PDF:", pdf_url)
        r = requests.get(pdf_url)
        r.raise_for_status()
        with open(filename, "wb") as f:
            f.write(r.content)
    return filename

def extract_text_from_pdf(pdf_path):
    """Extract full text from PDF using PyMuPDF4LLM."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# ---------------- SCRAPING + EXTRACTION ----------------

def scrape_index(limit=70):
    """Scrape the index page to collect PDF links."""
    html = fetch_page(INDEX_URL)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    pdf_urls = []
    count = 0

    for row in table.find_all("tr")[1:]:
        if count >= limit:
            break

        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        # Title link
        a = cols[2].find("a")
        if not a:
            continue

        href = a.get("href", "").strip()
        # If link itself is PDF
        if ".pdf" in href.lower():
            # build absolute if needed
            if href.startswith("http"):
                pdf_url = href
            else:
                pdf_url = PDF_BASE + href.split("/")[-1]
            pdf_urls.append(pdf_url)
            count += 1

    print(f"Found {len(pdf_urls)} PDF URLs in index.")
    return pdf_urls

def parse_pdf_text(text):
    """Simple heuristics to extract title and date."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    issue_date = ""
    title = ""

    # Try to find Title (the first long line after RBI heading)
    # and Issue Date (pattern like May 5, 2021 or DD MMM YYYY)
    for i, ln in enumerate(lines[:20]):
        # Find date pattern
        if re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s*\d{4}", ln):
            issue_date = ln

        # Title heuristic: all uppercase or title cased after RBI heading
        if i > 0 and len(ln) > 10:
            title = ln
            break

    return issue_date, title

def process_pdfs(pdf_urls):
    """Download, extract, and store PDFs."""
    session = Session()

    for pdf_url in pdf_urls:
        # Normalize
        pdf_url = pdf_url.strip()
        ref_no = pdf_url.split("/")[-1].replace(".pdf", "")

        exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
        if exists:
            print("🔁 Already in DB:", ref_no)
            continue

        try:
            pdf_path = download_pdf(pdf_url)
        except Exception as e:
            print("❌ Failed to download PDF:", pdf_url, e)
            continue

        # Extract text
        try:
            body_text = extract_text_from_pdf(pdf_path)
        except Exception as e:
            print("❌ Failed to extract text:", pdf_url, e)
            body_text = ""

        # Parse structured
        issue_date, title = parse_pdf_text(body_text)

        circ = Circular(
            ref_no=ref_no,
            issue_date=issue_date,
            title=title,
            pdf_url=pdf_url,
            body_text=body_text
        )
        session.add(circ)
        session.commit()

        print(f"✔ Stored {ref_no}, Title: {title[:60]}, Date: {issue_date}")

        time.sleep(0.3)

    session.close()

# ---------------- MAIN ----------------

if __name__ == "__main__":
    pdf_urls = scrape_index(limit=70)
    process_pdfs(pdf_urls)
    print("🎉 Extraction complete — text stored in database_rbi_pdfs.db")
