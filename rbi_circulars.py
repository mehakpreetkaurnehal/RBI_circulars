import os
import time
import requests
import fitz  # PyMuPDF4LLM
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# -------------------------------
# SETUP DATABASE
# -------------------------------
engine = create_engine("sqlite:///rbi_circulars.db", echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Circular(Base):
    __tablename__ = "circulars"
    id = Column(Integer, primary_key=True)
    circular_number = Column(String)
    date_of_issue = Column(String)
    department = Column(String)
    subject = Column(String)
    detail_url = Column(String, unique=True)
    html_text = Column(Text)
    pdf_url = Column(String)
    pdf_text = Column(Text)

Base.metadata.create_all(engine)

# -------------------------------
# SELENIUM SETUP
# -------------------------------
options = webdriver.ChromeOptions()
options.headless = True
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

INDEX_URL = "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx"

PDF_DIR = "pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

# -------------------------------
# HELPER FUNCTIONS
# -------------------------------
def download_pdf(pdf_url):
    fname = os.path.join(PDF_DIR, pdf_url.split("/")[-1])
    if not os.path.exists(fname):
        print("📥 Downloading:", pdf_url)
        r = requests.get(pdf_url)
        r.raise_for_status()
        with open(fname, "wb") as f:
            f.write(r.content)
    return fname

def extract_pdf_text(pdf_path):
    """Extract PDF text using PyMuPDF4LLM"""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def find_pdf_link(html):
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # RBI PDF circular links contain "PDFs/" in path
        if "PDFs" in href and href.lower().endswith(".pdf"):
            if href.startswith("http"):
                return href
            # handle relative paths
            return "https://rbidocs.rbi.org.in/rdocs/Notification/PDFs/" + os.path.basename(href)
    return None

# -------------------------------
# SCRAPE AND SAVE
# -------------------------------
def scrape_circulars(limit=70):
    # Step 1: Load and render the index page
    print("🔎 Loading RBI Circular Index page...")
    driver.get(INDEX_URL)
    time.sleep(5)  # wait for JavaScript

    index_html = driver.page_source
    soup = BeautifulSoup(index_html, "html.parser")

    rows = soup.find_all("tr")[1:]  # skip header
    session = Session()
    count = 0

    # Step 2: Parse the table
    for row in rows:
        if count >= limit:
            break

        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        circular_number = cols[0].text.strip()
        date_of_issue = cols[1].text.strip()
        department = cols[2].text.strip()
        subject = cols[3].text.strip()
        detail_link_tag = cols[4].find("a")
        if not detail_link_tag:
            continue

        detail_href = detail_link_tag["href"]
        detail_url = "https://www.rbi.org.in/scripts/" + detail_href

        # Avoid duplicates
        exists = session.query(Circular).filter_by(detail_url=detail_url).first()
        if exists:
            continue

        circ = Circular(
            circular_number=circular_number,
            date_of_issue=date_of_issue,
            department=department,
            subject=subject,
            detail_url=detail_url,
        )
        session.add(circ)
        session.commit()
        print(f"[{count+1}] Indexed: {circular_number}")
        count += 1

    print("\n📌 Indexing complete.")
    print("📄 Now fetching details...")

    # Step 3: Visit each circular detail page
    circulars = session.query(Circular).all()
    for circ in circulars:
        print(f"➡️ Fetching detail for: {circ.circular_number}")
        driver.get(circ.detail_url)
        time.sleep(4)
        detail_html = driver.page_source

        # Extract HTML text
        html_text = BeautifulSoup(detail_html, "html.parser").get_text(separator="\n", strip=True)
        circ.html_text = html_text

        # Find PDF link
        pdf_link = find_pdf_link(detail_html)
        if pdf_link:
            circ.pdf_url = pdf_link
            pdf_path = download_pdf(pdf_link)
            circ.pdf_text = extract_pdf_text(pdf_path)
            print("  ✔ PDF processed")
        else:
            print("  ⚠ No PDF link found")

        session.commit()
        time.sleep(0.5)

    session.close()
    driver.quit()
    print("🎉 Done — circulars stored in database.db")

if __name__ == "__main__":
    scrape_circulars(limit=70)
