import os
import time
import requests
import fitz  # PyMuPDF4LLM
from bs4 import BeautifulSoup

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# === Database Setup ===
engine = create_engine("sqlite:///scrape_and_extract_database.db", echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Circular(Base):
    __tablename__ = "circulars"
    id = Column(Integer, primary_key=True)
    ref_no = Column(String)
    date = Column(String)
    title = Column(String)
    url = Column(String, unique=True)
    html_text = Column(Text)
    pdf_url = Column(String)
    pdf_text = Column(Text)

Base.metadata.create_all(engine)

# === URLs ===
INDEX_URL = "https://www.rbi.org.in/commonman/English/scripts/notification.aspx"
BASE_DOMAIN = "https://www.rbi.org.in"

PDF_DIR = "pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

# --- Helpers ---

def fetch_page(url):
    """Fetch HTML page, with retries."""
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"❌ Failed to fetch {url}: {e}")
        return None

def find_pdf_link(html):
    """Find a PDF link in detail HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            if href.startswith("http"):
                return href
            # relative PDF link
            return BASE_DOMAIN + href
    return None

def download_pdf(pdf_url):
    """Download PDF to local dir."""
    fname = os.path.join(PDF_DIR, pdf_url.split("/")[-1])
    if not os.path.exists(fname):
        print("📥 Downloading:", pdf_url)
        r = requests.get(pdf_url)
        r.raise_for_status()
        with open(fname, "wb") as f:
            f.write(r.content)
    return fname

def extract_pdf_text(path):
    """Extract PDF text via PyMuPDF4LLM."""
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# --- Scrape Index + Details ---

def scrape_index(limit=70):
    html = fetch_page(INDEX_URL)
    if not html:
        return

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    session = Session()
    count = 0

    for row in table.find_all("tr")[1:]:
        if count >= limit:
            break

        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        date = cols[0].text.strip()
        title_tag = cols[2].find("a")
        if not title_tag:
            continue

        title = title_tag.text.strip()
        href = title_tag["href"]
        url = href if href.startswith("http") else BASE_DOMAIN + href

        ref_no = url.split("/")[-1]

        exists = session.query(Circular).filter_by(url=url).first()
        if exists:
            continue

        circ = Circular(
            ref_no=ref_no,
            date=date,
            title=title,
            url=url
        )
        session.add(circ)
        session.commit()
        print(f"[{count+1}] Indexed:", ref_no)

        count += 1

    session.close()
    print(f"\nIndexed {count} circulars.")

def scrape_details():
    session = Session()
    circulars = session.query(Circular).all()

    for circ in circulars:
        print("➡️ Fetching detail for:", circ.ref_no)

        html = fetch_page(circ.url)
        if html:
            circ.html_text = BeautifulSoup(html, "html.parser").get_text(
                separator="\n", strip=True
            )

            # look for PDF
            pdf_link = find_pdf_link(html)
            if pdf_link:
                circ.pdf_url = pdf_link
                try:
                    pdf_path = download_pdf(pdf_link)
                    circ.pdf_text = extract_pdf_text(pdf_path)
                except Exception as e:
                    print("❌ PDF extract error:", e)

        session.commit()
        time.sleep(0.3)

    session.close()

if __name__ == "__main__":
    scrape_index(limit=70)
    scrape_details()
    print("🎉 All done — data stored in database.")

