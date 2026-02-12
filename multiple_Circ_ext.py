# extracting only one circular
import os, re, time, sqlite3
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import fitz
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

INDEX_URL = "https://rbi.org.in/scripts/BS_CircularIndexDisplay.aspx"
DETAIL_URL_BASE = "https://rbi.org.in/scripts/BS_CircularIndexDisplay.aspx?Id="
PDF_BASE = "https://rbidocs.rbi.org.in/rdocs/Notification/PDFs/"

DB_PATH = "multiple_circ_ext.db"
PDF_DIR = "multiple_circ_ext"
os.makedirs(PDF_DIR, exist_ok=True)

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS circulars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            circular_number TEXT UNIQUE,
            dor_number TEXT,
            date_of_issue TEXT,
            department TEXT,
            subject TEXT,
            meant_for TEXT,
            pdf_url TEXT,
            pdf_filename TEXT,
            body_text TEXT,
            extraction_method TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_circular_number ON circulars(circular_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_date ON circulars(date_of_issue)")
    conn.commit()
    conn.close()
    print("Database initialized")


def scrape_index_table_selenium(limit=None):
    print(f"⏳ Launching browser for index page")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.get(INDEX_URL)

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    except Exception as e:
        print("❌ Table did not load:", e)
        driver.quit()
        return []

    html = driver.page_source
    driver.quit()

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    if not table:
        print("❌ Could not find the index table")
        return []

    all_rows = table.find_all("tr")
    print(f"💡 Found {len(all_rows)} table rows")

    header = None
    for i, tr in enumerate(all_rows):
        txt = tr.get_text().lower()
        if "circular number" in txt and "date" in txt:
            header = i
            break

    if header is None:
        print("❌ Could not find header row")
        return []

    data_rows = all_rows[header+1:]
    print(f"📄 Found {len(data_rows)} circular rows")

    circulars = []
    for i, row in enumerate(data_rows):
        if limit and i >= limit:
            break

        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        circ_no = cols[0].get_text(strip=True)
        if not circ_no:
            continue

        date_of_issue = cols[1].get_text(strip=True)
        department = cols[2].get_text(strip=True)
        subject = cols[3].get_text(strip=True) if len(cols) > 3 else ""
        meant_for = cols[4].get_text(strip=True) if len(cols) > 4 else ""

        link = cols[0].find("a")
        detail_url = None
        if link and "href" in link.attrs:
            href = link["href"]
            m = re.search(r"Id=(\d+)", href)
            if m:
                detail_url = DETAIL_URL_BASE + m.group(1)

        circulars.append({
            "circular_number": circ_no,
            "date_of_issue": date_of_issue,
            "department": department,
            "subject": subject,
            "meant_for": meant_for,
            "detail_url": detail_url
        })

    print(f"→ Scraped {len(circulars)} circulars")
    return circulars

def get_pdf_url_from_detail(detail_url):
    try:
        r = requests.get(detail_url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower():
                if href.startswith("http"):
                    return href
                else:
                    return PDF_BASE + href.split("/")[-1]
        return None
    except Exception as e:
        print("  ⚠ Error getting PDF URL:", e)
        return None

def download_pdf(pdf_url):
    try:
        fn = os.path.join(PDF_DIR, pdf_url.split("/")[-1])
        if os.path.exists(fn):
            return fn
        r = requests.get(pdf_url, timeout=30)
        r.raise_for_status()
        with open(fn, "wb") as f:
            f.write(r.content)
        return fn
    except Exception as e:
        print("  ❌ PDF download failed:", e)
        return None

def extract_text_from_pdf(path):
    text_pages = []
    doc = fitz.open(path)
    for p in doc:
        text_pages.append(p.get_text())
    doc.close()
    return "\n".join(text_pages)

def extract_text_from_web(detail_url):
    try:
        r = requests.get(detail_url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(separator="\n", strip=True)
    except:
        return ""

def parse_circular_content(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    dor = ""
    for l in lines[:10]:
        if "DOR" in l:
            m = re.search(r"(DOR[^/\s]+)", l, re.IGNORECASE)
            if m:
                dor = m.group(1)
                break
    return {"dor_number": dor, "full_text": text}

def process_circulars(limit=None):
    init_database()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    circulars = scrape_index_table_selenium(limit)
    if not circulars:
        print("No circulars found")
        return

    stats = {"new":0, "skip":0, "fail":0}

    for idx, circ in enumerate(circulars, start=1):
        print(f"[{idx}/{len(circulars)}] {circ['circular_number']}")

        cur.execute("SELECT 1 FROM circulars WHERE circular_number=?", (circ["circular_number"],))
        if cur.fetchone():
            print("  — already exists")
            stats["skip"] += 1
            continue

        body = ""
        extraction_method="none"
        pdf_url=None
        pdf_fname=""

        if circ["detail_url"]:
            pdf_url = get_pdf_url_from_detail(circ["detail_url"])
            if pdf_url:
                pdf_path = download_pdf(pdf_url)
                if pdf_path:
                    body = extract_text_from_pdf(pdf_path)
                    extraction_method="pdf"
                    pdf_fname=os.path.basename(pdf_path)

        if not body:
            body = extract_text_from_web(circ["detail_url"])
            extraction_method="web"

        if not body:
            stats["fail"] += 1
            print("  ❌ Extraction failed")
            continue

        parsed = parse_circular_content(body)
        cur.execute("""
            INSERT INTO circulars
            (circular_number, dor_number, date_of_issue, department, subject, meant_for,
             pdf_url, pdf_filename, body_text, extraction_method)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            circ["circular_number"], parsed["dor_number"], circ["date_of_issue"],
            circ["department"], circ["subject"], circ["meant_for"],
            pdf_url or "", pdf_fname, parsed["full_text"], extraction_method
        ))
        conn.commit()
        stats["new"] += 1

    conn.close()

    print("\n=== STATS ===")
    print(f"New: {stats['new']} | Skipped: {stats['skip']} | Failed: {stats['fail']}")

if __name__ == "__main__":
    process_circulars(limit=200)
