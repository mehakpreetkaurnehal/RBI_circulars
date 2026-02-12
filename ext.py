# import os
# import time
# import urllib.parse
# import requests
# from bs4 import BeautifulSoup

# import fitz  # PyMuPDF

# # ---------------- SETTINGS ------------------

# BASE = "https://rbi.org.in/Scripts/"
# NOTIFY_INDEX = BASE + "NotificationUser.aspx"
# HEADERS = {"User-Agent": "Mozilla/5.0"}

# # How many to scrape (set as needed)
# MAX_CIRCULARS = 100

# # Local storage
# PDF_DIR = "ext_pdfs"
# TEXT_DIR = "ext_texts"
# os.makedirs(PDF_DIR, exist_ok=True)
# os.makedirs(TEXT_DIR, exist_ok=True)

# # ---------------- FUNCTIONS ------------------

# def fetch_notifications():
#     """Get all circular items from the RBI notifications page."""
#     print(f"📡 Fetching RBI notification list...")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifications = []
#     for row in soup.select("table.tablebg tr"):
#         a = row.find("a", class_="link2")
#         if not a:
#             continue

#         href = a["href"]
#         if "Id=" not in href:
#             continue

#         params = urllib.parse.parse_qs(href.split("?")[1])
#         circular_id = params.get("Id", [""])[0]
#         mode = params.get("Mode", [""])[0]
#         title = a.text.strip()

#         notifications.append({
#             "title": title,
#             "id": circular_id,
#             "mode": mode
#         })
#     print(f"✔ Found {len(notifications)} notifications")
#     return notifications


# def extract_detail(item):
#     """Visit circular and extract PDF link if any."""
#     url = f"{BASE}NotificationUser.aspx?Id={item['id']}&Mode={item['mode']}"
#     time.sleep(0.2)

#     res = requests.get(url, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     # Try find PDF link
#     pdf_tag = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
#     pdf_url = None
#     if pdf_tag:
#         pdf_url = pdf_tag["href"]
#         if not pdf_url.startswith("http"):
#             pdf_url = urllib.parse.urljoin(BASE, pdf_url)

#     # Visible HTML text (fallback)
#     html_text = soup.get_text(separator="\n").strip()

#     return {
#         "pdf_url": pdf_url,
#         "html_text": html_text
#     }


# def download_pdf(url):
#     """Download PDF to local filesystem."""
#     filename = os.path.join(PDF_DIR, url.split("/")[-1])
#     if not os.path.exists(filename):
#         print(f"📥 Downloading PDF: {url.split('/')[-1]}")
#         r = requests.get(url, headers=HEADERS)
#         with open(filename, "wb") as f:
#             f.write(r.content)
#     return filename


# def extract_text_from_pdf(pdf_path):
#     """Extract full text from PDF using PyMuPDF."""
#     doc = fitz.open(pdf_path)
#     text = ""
#     for page in doc:
#         text += page.get_text()
#     return text


# # ---------------- MAIN PIPELINE ------------------

# if __name__ == "__main__":

#     notifications = fetch_notifications()
#     notifications = notifications[:MAX_CIRCULARS]  # limit if needed

#     print(f"🧠 Extracting {len(notifications)} circulars...\n")

#     for idx, item in enumerate(notifications, start=1):

#         print(f"===== [{idx}/{len(notifications)}] {item['title']} =====")

#         detail = extract_detail(item)

#         if detail["pdf_url"]:
#             print("📌 PDF found:", detail["pdf_url"])

#             pdf_file = download_pdf(detail["pdf_url"])
#             pdf_text = extract_text_from_pdf(pdf_file)

#             filename_txt = os.path.join(
#                 TEXT_DIR,
#                 f"{item['id']}_{pdf_file.split('/')[-1].replace('.pdf','.txt')}"
#             )

#             with open(filename_txt, "w", encoding="utf-8") as f:
#                 f.write(pdf_text)

#             print("📝 Extracted text saved:", filename_txt)

#         else:
#             # Some circulars may not have PDF
#             print("⚠️ No PDF — storing HTML text instead")

#             filename_txt = os.path.join(
#                 TEXT_DIR,
#                 f"{item['id']}_no_pdf.txt"
#             )

#             with open(filename_txt, "w", encoding="utf-8") as f:
#                 f.write(detail["html_text"])

#             print("📝 HTML text saved:", filename_txt)

#         print("Waiting a bit…")
#         time.sleep(0.5)

#     print("\n🎉 Done extracting all circulars!")



#code is providing the links but not the text.
# import os
# import time
# import urllib.parse
# import requests
# from bs4 import BeautifulSoup

# import fitz  # PyMuPDF

# # ---------------- SETTINGS ------------------

# BASE = "https://rbi.org.in/Scripts/"
# NOTIFY_INDEX = BASE + "NotificationUser.aspx"
# HEADERS = {"User-Agent": "Mozilla/5.0"}

# # How many circulars to scrape; increase as needed
# MAX_CIRCULARS = 10

# # Local folders
# PDF_DIR = "ext_pdfs"
# TEXT_DIR = "ext_texts"
# os.makedirs(PDF_DIR, exist_ok=True)
# os.makedirs(TEXT_DIR, exist_ok=True)

# # ---------------- FUNCTIONS ------------------

# def fetch_notifications():
#     """Get all circular items from the RBI notifications page."""
#     print(f"📡 Fetching RBI notification list...")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifications = []
#     for row in soup.select("table.tablebg tr"):
#         a = row.find("a", class_="link2")
#         if not a:
#             continue

#         href = a["href"]
#         if "Id=" not in href:
#             continue

#         params = urllib.parse.parse_qs(href.split("?")[1])
#         circular_id = params.get("Id", [""])[0]
#         mode = params.get("Mode", [""])[0]
#         title = a.text.strip()

#         notifications.append({
#             "title": title,
#             "id": circular_id,
#             "mode": mode
#         })

#     print(f"✔ Found {len(notifications)} notifications")
#     return notifications


# def extract_detail(item):
#     """Visit circular and extract PDF link if any."""
#     url = f"{BASE}NotificationUser.aspx?Id={item['id']}&Mode={item['mode']}"
#     time.sleep(0.2)

#     res = requests.get(url, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     pdf_tag = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
#     pdf_url = None
#     if pdf_tag:
#         pdf_url = pdf_tag["href"]
#         if not pdf_url.startswith("http"):
#             pdf_url = urllib.parse.urljoin(BASE, pdf_url)

#     html_text = soup.get_text(separator="\n").strip()

#     return {
#         "pdf_url": pdf_url,
#         "html_text": html_text
#     }


# def download_pdf(url):
#     """Download PDF to local filesystem."""
#     filename = os.path.join(PDF_DIR, url.split("/")[-1])
#     if not os.path.exists(filename):
#         print(f"📥 Downloading PDF: {os.path.basename(filename)}")
#         r = requests.get(url, headers=HEADERS)
#         with open(filename, "wb") as f:
#             f.write(r.content)
#     return filename


# def extract_text_from_pdf(pdf_path):
#     """Extract full text from PDF using PyMuPDF."""
#     doc = fitz.open(pdf_path)
#     text = ""
#     for page in doc:
#         text += page.get_text()
#     return text


# # ---------------- MAIN ------------------

# if __name__ == "__main__":

#     notifications = fetch_notifications()
#     notifications = notifications[:MAX_CIRCULARS]

#     print(f"🧠 Extracting {len(notifications)} circulars...\n")

#     for idx, item in enumerate(notifications, start=1):

#         title_clean = item["title"].replace("/", "_").replace("\\", "_")[:60]
#         print(f"===== [{idx}/{len(notifications)}] {title_clean} =====")

#         detail = extract_detail(item)
#         pdf_url = detail["pdf_url"]

#         if pdf_url:
#             print("📌 PDF found:", pdf_url)

#             # Download & extract
#             pdf_file = download_pdf(pdf_url)
#             pdf_text = extract_text_from_pdf(pdf_file)

#             # Create text file
#             txt_filename = f"{item['id']}_{os.path.basename(pdf_file).replace('.PDF','.txt').replace('.pdf','.txt')}"
#             txt_path = os.path.join(TEXT_DIR, txt_filename)

#             with open(txt_path, "w", encoding="utf-8") as f:
#                 f.write(pdf_text)

#             print("📝 PDF text extracted:", txt_path)

#         else:
#             print("⚠️ No PDF — saving HTML text")

#             txt_filename = f"{item['id']}_no_pdf.txt"
#             txt_path = os.path.join(TEXT_DIR, txt_filename)

#             with open(txt_path, "w", encoding="utf-8") as f:
#                 f.write(detail["html_text"])

#             print("📝 HTML text saved:", txt_path)

#         time.sleep(0.5)

#     print("\n🎉 Extraction complete!")


# provinding correct links for the Circulars, but not the text extracted is well.

# import os
# import time
# import urllib.parse
# import requests
# from bs4 import BeautifulSoup

# import fitz  # PyMuPDF
# from PIL import Image
# import pytesseract

# # ---------------- SETTINGS ------------------

# BASE = "https://rbi.org.in/Scripts/"
# NOTIFY_INDEX = BASE + "NotificationUser.aspx"
# HEADERS = {"User-Agent": "Mozilla/5.0"}

# # How many circulars to fetch
# MAX_CIRCULARS = 10

# # Directories
# PDF_DIR = "ext_pdfs"
# TEXT_DIR = "ext_texts"
# os.makedirs(PDF_DIR, exist_ok=True)
# os.makedirs(TEXT_DIR, exist_ok=True)

# # ---------------- FUNCTIONS ------------------

# def fetch_notifications():
#     print("📡 Fetching RBI notification list...")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifications = []
#     for row in soup.select("table.tablebg tr"):
#         a = row.find("a", class_="link2")
#         if not a:
#             continue

#         href = a["href"]
#         if "Id=" not in href:
#             continue

#         params = urllib.parse.parse_qs(href.split("?")[1])
#         circular_id = params.get("Id", [""])[0]
#         mode = params.get("Mode", [""])[0]
#         title = a.text.strip()

#         notifications.append({
#             "title": title,
#             "id": circular_id,
#             "mode": mode
#         })

#     print(f"✔ Found {len(notifications)} notifications")
#     return notifications


# def extract_detail(item):
#     url = f"{BASE}NotificationUser.aspx?Id={item['id']}&Mode={item['mode']}"
#     time.sleep(0.2)

#     res = requests.get(url, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     pdf_tag = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
#     pdf_url = None
#     if pdf_tag:
#         pdf_url = pdf_tag["href"]
#         if not pdf_url.startswith("http"):
#             pdf_url = urllib.parse.urljoin(BASE, pdf_url)

#     html_text = soup.get_text(separator="\n").strip()

#     return {"pdf_url": pdf_url, "html_text": html_text}


# def download_pdf(url):
#     fname = os.path.join(PDF_DIR, url.split("/")[-1])
#     if not os.path.exists(fname):
#         print(f"📥 Downloading {os.path.basename(fname)}")
#         r = requests.get(url, headers=HEADERS)
#         with open(fname, "wb") as f:
#             f.write(r.content)
#     return fname


# def extract_text_with_pymupdf(pdf_path):
#     """Extract text with PyMuPDF blocks + fallback."""
#     doc = fitz.open(pdf_path)
#     text = ""

#     for page in doc:
#         # first try normal text
#         page_text = page.get_text("text")
#         if page_text.strip():
#             text += page_text
#         else:
#             # try block extraction and images
#             blocks = page.get_text("dict")["blocks"]
#             for b in blocks:
#                 if b["type"] == 0:  # text block
#                     for line in b["lines"]:
#                         for span in line["spans"]:
#                             text += span["text"] + " "
#                 elif b["type"] == 1:  # image block → OCR
#                     img = page.get_pixmap()
#                     img_pil = Image.frombytes(
#                         "RGB", [img.width, img.height], img.samples
#                     )
#                     ocr_text = pytesseract.image_to_string(img_pil)
#                     text += ocr_text

#     return text


# # ---------------- MAIN ------------------

# if __name__ == "__main__":
#     notifications = fetch_notifications()
#     notifications = notifications[:MAX_CIRCULARS]

#     print(f"🧠 Extracting {len(notifications)} circulars...\n")

#     for idx, item in enumerate(notifications, start=1):
#         clean_title = item["title"].replace("/", "_")[:60]
#         print(f"===== [{idx}/{len(notifications)}] {clean_title} =====")

#         detail = extract_detail(item)

#         if detail["pdf_url"]:
#             print("📌 PDF:", detail["pdf_url"])

#             pdf_file = download_pdf(detail["pdf_url"])
#             text = extract_text_with_pymupdf(pdf_file)

#             out_fname = f"{item['id']}_{os.path.basename(pdf_file).replace('.pdf','.txt')}"
#             out_path = os.path.join(TEXT_DIR, out_fname)

#             with open(out_path, "w", encoding="utf-8") as f:
#                 f.write(text)

#             print("📝 Text extracted:", out_path)

#         else:
#             print("⚠️ No PDF — saving HTML text")
#             out_fname = f"{item['id']}_html.txt"
#             out_path = os.path.join(TEXT_DIR, out_fname)
#             with open(out_path, "w", encoding="utf-8") as f:
#                 f.write(detail["html_text"])
#             print("📝 HTML text saved:", out_path)

#         time.sleep(0.4)

#     print("\n🎉 Extraction complete!")




import os
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup

import pdfplumber
import fitz  # PyMuPDF

# ---------------- SETTINGS ------------------

BASE = "https://rbi.org.in/Scripts/"
NOTIFY_INDEX = BASE + "NotificationUser.aspx"

# Standard browser headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                  " AppleWebKit/537.36 (KHTML, like Gecko)"
                  " Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

PDF_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Referer": "https://rbidocs.rbi.org.in/",
    "Accept": "application/pdf"
}

# How many circulars to fetch
MAX_CIRCULARS = 10

PDF_DIR = "rbi_pdfs"
TEXT_DIR = "rbi_texts"

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(TEXT_DIR, exist_ok=True)

# ---------------- FUNCTIONS ------------------

def fetch_notifications():
    """Fetch RBI circular list."""
    print("📡 Fetching RBI notification list…")
    res = requests.get(NOTIFY_INDEX, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    notifications = []
    for row in soup.select("table.tablebg tr"):
        a = row.find("a", class_="link2")
        if not a:
            continue

        href = a["href"]
        if "Id=" not in href:
            continue

        params = urllib.parse.parse_qs(href.split("?")[1])
        circ_id = params.get("Id", [""])[0]
        mode = params.get("Mode", [""])[0]
        title = a.text.strip()

        notifications.append({
            "title": title,
            "id": circ_id,
            "mode": mode
        })
    print(f"✔ Found {len(notifications)} circulars")
    return notifications


def extract_pdf_link(item):
    """Go to circular page and extract PDF link."""
    url = f"{BASE}NotificationUser.aspx?Id={item['id']}&Mode={item['mode']}"
    time.sleep(0.2)

    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    pdf_tag = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
    if pdf_tag:
        pdf_url = pdf_tag["href"]
        if not pdf_url.startswith("http"):
            pdf_url = urllib.parse.urljoin(BASE, pdf_url)
        return pdf_url
    return None


def download_pdf(pdf_url):
    """Download PDF using browser-like headers and validate."""
    fname = os.path.join(PDF_DIR, os.path.basename(pdf_url))
    if os.path.exists(fname):
        return fname

    print(f"📥 Downloading PDF: {os.path.basename(pdf_url)}")

    r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
    content = r.content

    # Validate PDF header
    if content[:4] != b"%PDF":
        print("❌ Not a real PDF — skipping")
        return None

    with open(fname, "wb") as f:
        f.write(content)

    return fname


def extract_text_pdfplumber(pdf_path):
    """Extract text using pdfplumber first."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception as e:
        print("⚠️ pdfplumber error:", e)
    return text


def extract_text_pymupdf(pdf_path):
    """Fallback extraction with PyMuPDF."""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text("text") + "\n"
    except Exception as e:
        print("⚠️ PyMuPDF error:", e)
    return text


# ---------------- MAIN ------------------

if __name__ == "__main__":

    notifications = fetch_notifications()
    notifications = notifications[:MAX_CIRCULARS]

    print(f"🧠 Extracting {len(notifications)} circulars…\n")

    for idx, item in enumerate(notifications, start=1):
        title = item["title"].replace("/", "_")[:60]
        print(f"===== [{idx}/{len(notifications)}] {title} =====")

        pdf_url = extract_pdf_link(item)
        if not pdf_url:
            print("⚠️ No PDF link found — skipping text")
            continue

        pdf_file = download_pdf(pdf_url)
        if not pdf_file:
            print("⚠️ Download failed — skipping")
            continue

        # Try extraction
        text = extract_text_pdfplumber(pdf_file)
        if not text.strip():
            print("🔁 pdfplumber empty — trying PyMuPDF…")
            text = extract_text_pymupdf(pdf_file)

        if not text.strip():
            text = "[TEXT EXTRACTION FAILED]"

        out_name = f"{item['id']}_{os.path.basename(pdf_file).replace('.pdf','.txt')}"
        out_path = os.path.join(TEXT_DIR, out_name)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)

        print("📝 Saved:", out_path)
        time.sleep(0.4)

    print("\n🎉 Done extracting!")
