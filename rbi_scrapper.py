import os
import re
import time
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------- DATABASE SETUP ----------------

engine = create_engine("sqlite:///rbi_scrapper.db", echo=False)
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

PDF_DIR = "Scrapped_pdfs"
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
    """Extract full text from PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# ---------------- NEW PARSER ----------------

def parse_pdf_text(text):
    """
    Improved parser to extract:
    - Circular reference number (RBI/xxxx)
    - Issue date
    - Title / Subject
    - Body content (everything after title)
    """

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    ref_no = ""
    issue_date = ""
    title = ""
    body_lines = []

    # Regex patterns
    ref_pattern = r"RBI/\d{4}-\d{2}/\d+"
    date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

    stage = "find_ref"

    for ln in lines:

        # ➤ FIND CIRCULAR REF NO
        if stage == "find_ref":
            m = re.search(ref_pattern, ln)
            if m:
                ref_no = m.group(0)
                stage = "find_date"
            continue

        # ➤ FIND ISSUE DATE
        if stage == "find_date":
            m = re.search(date_pattern, ln)
            if m:
                issue_date = m.group(0)
                stage = "find_title"
            continue

        # ➤ FIND TITLE / SUBJECT
        if stage == "find_title":
            # Typically title is after the date & before body text
            # Ensure it's not a salutation like "Madam / Dear Sir"
            if "Madam" in ln or "Dear Sir" in ln or "Sir" in ln:
                continue

            # Use first substantial line as title
            if len(ln) > 10:
                title = ln
                stage = "collect_body"
            continue

        # ➤ COLLECT THE BODY
        if stage == "collect_body":
            body_lines.append(ln)

    body_text = "\n".join(body_lines)

    return ref_no, issue_date, title, body_text

# ---------------- SCRAPING + EXTRACTION ----------------

def scrape_index(limit=70):
    """Scrape the RBI index page to collect PDF links."""
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

        a = cols[2].find("a")
        if not a:
            continue

        href = a.get("href", "").strip()
        if ".pdf" in href.lower():
            if href.startswith("http"):
                pdf_url = href
            else:
                pdf_url = PDF_BASE + href.split("/")[-1]
            pdf_urls.append(pdf_url)
            count += 1

    print(f"Found {len(pdf_urls)} PDF URLs in index.")
    return pdf_urls

def process_pdfs(pdf_urls):
    """Download, extract, parse and store PDFs into DB."""
    session = Session()

    for pdf_url in pdf_urls:
        pdf_url = pdf_url.strip()
        ref_id = pdf_url.split("/")[-1].replace(".pdf", "")

        exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
        if exists:
            print("🔁 Already in DB:", ref_id)
            continue

        try:
            pdf_path = download_pdf(pdf_url)
        except Exception as e:
            print("❌ Failed to download PDF:", pdf_url, e)
            continue

        try:
            raw_text = extract_text_from_pdf(pdf_path)
        except Exception as e:
            print("❌ PDF text extract failed:", e)
            raw_text = ""

        ref_no, issue_date, title, body_text = parse_pdf_text(raw_text)

        if not ref_no and not body_text:
            print("⚠️ Skipping (failed parse)", pdf_url)
            continue

        circ = Circular(
            ref_no=ref_no,
            issue_date=issue_date,
            title=title,
            pdf_url=pdf_url,
            body_text=body_text
        )

        session.add(circ)
        session.commit()

        print(f"✔ Stored: {ref_no} | {issue_date} | {title[:80]}")

        time.sleep(0.2)

    session.close()
    
if __name__ == "__main__":
    pdfs = scrape_index(limit=100)
    process_pdfs(pdfs)
    print("🎉 RBI circular extraction complete!")
