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

# Database setup
engine = create_engine("sqlite:///scrape_text.db", echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Circular(Base):
    __tablename__ = "circulars"
    id = Column(Integer, primary_key=True)
    circular_number = Column(String)
    date_of_issue = Column(String)
    department = Column(String)
    subject = Column(String)
    detail_id = Column(String, unique=True)
    detail_url = Column(String, unique=True)
    html_text = Column(Text)
    pdf_url = Column(String)
    pdf_text = Column(Text)

Base.metadata.create_all(engine)

# Selenium setup
options = webdriver.ChromeOptions()
options.add_argument("--headless")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

INDEX_URL = "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx"
PDF_DIR = "pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

def download_pdf(pdf_url):
    filename = os.path.join(PDF_DIR, pdf_url.split("/")[-1])
    if not os.path.exists(filename):
        resp = requests.get(pdf_url)
        resp.raise_for_status()
        with open(filename, "wb") as f:
            f.write(resp.content)
    return filename

def extract_pdf_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def find_pdf_link(html):
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "PDFs/" in href and href.lower().endswith(".pdf"):
            return href if href.startswith("http") else f"https://rbidocs.rbi.org.in/rdocs/Notification/PDFs/{os.path.basename(href)}"
    return None

def scrape_rbi_circulars(limit=70):
    driver.get(INDEX_URL)
    time.sleep(5)  # wait for JS to load

    index_html = driver.page_source
    soup = BeautifulSoup(index_html, "html.parser")

    rows = soup.find_all("tr")[1:]
    session = Session()
    count = 0

    for row in rows:
        if count >= limit:
            break
        cols = row.find_all("td")
        if len(cols) < 5: continue

        circ_num = cols[0].text.strip()
        date = cols[1].text.strip()
        dept = cols[2].text.strip()
        subject = cols[3].text.strip()
        link_tag = cols[4].find("a")
        if not link_tag: continue

        href = link_tag["href"].strip()
        detail_id = href.split("Id=")[-1].split("&")[0]
        detail_url = f"https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx?Id={detail_id}"

        if session.query(Circular).filter_by(detail_id=detail_id).first():
            continue

        circ = Circular(
            circular_number=circ_num,
            date_of_issue=date,
            department=dept,
            subject=subject,
            detail_id=detail_id,
            detail_url=detail_url
        )
        session.add(circ)
        session.commit()
        count += 1

    print(f"Indexed {count} circulars.")

    circulars = session.query(Circular).all()
    for circ in circulars:
        driver.get(circ.detail_url)
        time.sleep(4)
        detail_html = driver.page_source
        circ.html_text = BeautifulSoup(detail_html, "html.parser").get_text(separator="\n", strip=True)

        pdf_link = find_pdf_link(detail_html)
        if pdf_link:
            circ.pdf_url = pdf_link
            try:
                pdf_file = download_pdf(pdf_link)
                circ.pdf_text = extract_pdf_text(pdf_file)
            except Exception:
                pass
        session.commit()

    session.close()
    driver.quit()
    print("Done.")

if __name__ == "__main__":
    scrape_rbi_circulars(limit=70)
