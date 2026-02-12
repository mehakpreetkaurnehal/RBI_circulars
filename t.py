import os
import time
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

import pdfplumber
import fitz  # PyMuPDF

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------- DATABASE SETUP -----------------

engine = create_engine("sqlite:///t2.db", echo=False)
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

# ---------------- CONSTANTS -----------------

BASE = "https://rbi.org.in/Scripts/"
NOTIFY_INDEX = BASE + "NotificationUser.aspx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

PDF_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Referer": "https://rbidocs.rbi.org.in/",
    "Accept": "application/pdf",
}

PDF_DIR = "t2"
os.makedirs(PDF_DIR, exist_ok=True)

def fetch_notifications():
    print("📡 Fetching RBI notifications list…")
    res = requests.get(NOTIFY_INDEX, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    notifs = []
    for row in soup.select("table.tablebg tr"):
        a = row.find("a", class_="link2")
        if not a:
            continue

        href = a.get("href", "")
        if "Id=" not in href:
            continue

        params = urllib.parse.parse_qs(href.split("?")[1])
        circ_id = params.get("Id", [""])[0]
        mode = params.get("Mode", [""])[0]
        title = a.text.strip()  # title from listing

        notifs.append({"title": title, "id": circ_id, "mode": mode})

    print(f"✔ Found {len(notifs)} notifications")
    return notifs

def extract_pdf_link(item):
    page_url = f"{BASE}NotificationUser.aspx?Id={item['id']}&Mode={item['mode']}"
    time.sleep(0.2)
    r = requests.get(page_url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    pdf_tag = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
    if pdf_tag:
        pdf_url = pdf_tag["href"]
        if not pdf_url.startswith("http"):
            pdf_url = urllib.parse.urljoin(BASE, pdf_url)
        return pdf_url
    return None

def download_pdf(pdf_url):
    fname = os.path.join(PDF_DIR, os.path.basename(pdf_url))
    if os.path.exists(fname):
        return fname

    print("📥 Downloading:", os.path.basename(pdf_url))
    r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
    if r.status_code == 200 and b"%PDF" in r.content[:4]:
        with open(fname, "wb") as f:
            f.write(r.content)
        return fname
    return None

def extract_text_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            lines = []
            for page in pdf.pages:
                words = page.extract_words(use_text_flow=True)
                words.sort(key=lambda w: (round(w["top"], 1), round(w["x0"], 1)))

                current = []
                last_top = None
                for w in words:
                    if last_top is None or abs(w["top"] - last_top) < 3:
                        current.append(w["text"])
                    else:
                        lines.append(" ".join(current))
                        current = [w["text"]]
                    last_top = w["top"]

                if current:
                    lines.append(" ".join(current))

            text = "\n".join(lines).strip()
    except:
        pass

    if not text.strip():
        try:
            doc = fitz.open(pdf_path)
            for p in doc:
                text += p.get_text("text") + "\n"
        except:
            pass

    return text.strip()

def parse_circular_text(text):
    """
    Extracts:
      - full reference number before the issue date
      - issue_date
      - body_text
    """

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    ref_no = ""
    issue_date = ""
    body_lines = []

    date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

    # -------------------------
    # 1) Collect lines up to the date
    # -------------------------
    pre_date_lines = []
    for ln in lines:
        # If line contains a date, remove the date part
        if re.search(date_pattern, ln):
            cleaned = re.sub(date_pattern, "", ln).strip()
            if cleaned:
                pre_date_lines.append(cleaned)
            break
        pre_date_lines.append(ln)

    # -------------------------
    # 2) Filter lines that are reference parts
    #    (lines with slashes or typical RBI code patterns)
    # -------------------------
    ref_parts = []
    for ln in pre_date_lines:
        # A reference part usually contains at least one "/" and alphanumerics
        if "/" in ln and re.search(r"[A-Za-z0-9]", ln):
            # length check to skip really short text
            if len(ln) > 4:
                ref_parts.append(ln)

    ref_no = " ".join(ref_parts).strip()

    # -------------------------
    # 3) Extract issue_date
    # -------------------------
    i = 0
    while i < len(lines):
        m = re.search(date_pattern, lines[i])
        if m:
            issue_date = m.group(0)
            i += 1
            break
        i += 1

    # -------------------------
    # 4) Body text: everything after the date
    # -------------------------
    while i < len(lines):
        body_lines.append(lines[i])
        i += 1

    body_text = " ".join(body_lines).strip()

    return ref_no, issue_date, body_text.strip()

if __name__ == "__main__":

    notifications = fetch_notifications()
    session = Session()
    limit = 100

    for idx, item in enumerate(notifications[:limit], start=1): 
        print(f"\n===== [{idx}] {item['title']} =====")

        pdf_url = extract_pdf_link(item)
        if not pdf_url:
            print("⚠️ No PDF link — skip")
            continue

        pdf_file = download_pdf(pdf_url)
        if not pdf_file:
            print("⚠️ Download failed — skip")
            continue

        raw_text = extract_text_pdf(pdf_file)
        if not raw_text:
            print("⚠️ Text extraction failed — skip")
            continue

        ref_no, issue_date, body_text = parse_circular_text(raw_text)

        # Title from listing
        title = item["title"]

        # avoid duplicates
        if session.query(Circular).filter_by(pdf_url=pdf_url).first():
            print("🔁 Already in DB — skip")
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

        print("✔ Stored:")
        print("    ref_no:", ref_no)
        print("    issue_date:", issue_date)
        print("    title:", title)

        time.sleep(0.3)

    session.close()
    print("\n🎉 Extraction & Storage Complete!")
