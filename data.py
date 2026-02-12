# this code fetches the URLs of the circulars
# import os
# import time
# import re
# import urllib.parse
# import base64
# from io import BytesIO

# import requests
# from bs4 import BeautifulSoup

# import pdfplumber
# import fitz  # PyMuPDF

# from sqlalchemy import create_engine, Column, Integer, String, Text
# from sqlalchemy.orm import sessionmaker, declarative_base

# # Selenium parts
# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager

# # ---------------- DATABASE SETUP -----------------

# engine = create_engine("sqlite:///data.db", echo=False)
# Session = sessionmaker(bind=engine)
# Base = declarative_base()

# class Circular(Base):
#     __tablename__ = "circulars"
#     id = Column(Integer, primary_key=True)
#     ref_no = Column(String)
#     issue_date = Column(String)
#     title = Column(String)
#     pdf_url = Column(String, unique=True)
#     body_text = Column(Text)

# Base.metadata.create_all(engine)

# # ---------------- GLOBAL SETTINGS -----------------

# BASE = "https://rbi.org.in/Scripts/"
# NOTIFY_INDEX = BASE + "NotificationUser.aspx"

# HEADERS = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                   "AppleWebKit/537.36 (KHTML, like Gecko) "
#                   "Chrome/120.0.0.0 Safari/537.36",
#     "Accept": "*/*"
# }

# PDF_DIR = "data"
# os.makedirs(PDF_DIR, exist_ok=True)

# # ---------------- FETCH NOTIFICATIONS ----------------

# def fetch_notifications():
#     print("📡 Fetching RBI notification list…")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifs = []
#     for row in soup.select("table.tablebg tr"):
#         a = row.find("a", class_="link2")
#         if not a:
#             continue

#         href = a["href"]
#         if "Id=" not in href:
#             continue

#         params = urllib.parse.parse_qs(href.split("?")[1])
#         circ_id = params.get("Id", [""])[0]
#         mode = params.get("Mode", [""])[0]
#         title = a.text.strip()

#         notifs.append({"title": title, "id": circ_id, "mode": mode})

#     print(f"✔ Found {len(notifs)} notifications")
#     return notifs

# # ---------------- EXTRACT PDF LINK ----------------

# def extract_pdf_link(item):
#     url = f"{BASE}NotificationUser.aspx?Id={item['id']}&Mode={item['mode']}"
#     time.sleep(0.2)

#     r = requests.get(url, headers=HEADERS)
#     soup = BeautifulSoup(r.text, "html.parser")

#     pdf_tag = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
#     if pdf_tag:
#         pdf_url = pdf_tag["href"]
#         if not pdf_url.startswith("http"):
#             pdf_url = urllib.parse.urljoin(BASE, pdf_url)
#         return pdf_url
#     return None

# # ---------------- DOWNLOAD PDF VIA SELENIUM ----------------

# def download_pdf_via_selenium(pdf_url):
#     chrome_options = Options()
#     chrome_options.add_argument("--headless")
#     chrome_options.add_argument("--disable-gpu")
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_experimental_option("prefs", {
#         "download.prompt_for_download": False,
#         "plugins.always_open_pdf_externally": True
#     })

#     driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
#                               options=chrome_options)

#     driver.get("about:blank")
#     time.sleep(1)

#     # JavaScript fetch + Base64 conversion
#     js = """
#     const url = arguments[0];
#     const callback = arguments[arguments.length - 1];

#     fetch(url)
#       .then(resp => resp.arrayBuffer())
#       .then(buf => {
#           let binary = '';
#           let bytes = new Uint8Array(buf);
#           for (let i = 0; i < bytes.length; i++) {
#               binary += String.fromCharCode(bytes[i]);
#           }
#           callback(btoa(binary));
#       })
#       .catch(err => callback("ERROR:" + err.toString()));
#     """

#     base64_pdf = driver.execute_async_script(js, pdf_url)
#     driver.quit()

#     if isinstance(base64_pdf, str) and base64_pdf.startswith("ERROR:"):
#         print("❌ Selenium PDF fetch error:", base64_pdf)
#         return None

#     try:
#         pdf_bytes = base64.b64decode(base64_pdf)
#         return pdf_bytes
#     except Exception as e:
#         print("❌ Base64 decode failed:", e)
#         return None

# # ---------------- TEXT EXTRACTION ----------------

# def extract_text_from_pdf_bytes(pdf_bytes):
#     text = ""
#     try:
#         with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
#             for page in pdf.pages:
#                 t = page.extract_text()
#                 if t:
#                     text += t + "\n"
#     except Exception as e:
#         print("⚠️ pdfplumber error:", e)

#     if not text.strip():
#         try:
#             doc = fitz.open(stream=pdf_bytes, filetype="pdf")
#             for p in doc:
#                 text += p.get_text("text") + "\n"
#         except Exception as e:
#             print("⚠️ PyMuPDF fallback:", e)

#     return text.strip()

# # ---------------- PARSE METADATA ----------------

# def parse_pdf_text(text):
#     lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

#     ref_no = ""
#     issue_date = ""
#     title = ""
#     body_lines = []

#     ref_pattern = r"[A-Z]+\.\w+(\.\w+)*\.[0-9/]+"
#     date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

#     stage = "find_ref"
#     for ln in lines:

#         if stage == "find_ref":
#             m = re.search(ref_pattern, ln)
#             if m:
#                 ref_no = m.group(0)
#                 stage = "find_date"
#             continue

#         if stage == "find_date":
#             m = re.search(date_pattern, ln)
#             if m:
#                 issue_date = m.group(0)
#                 stage = "title_or_salutation"
#             continue

#         if stage == "title_or_salutation":
#             salutations = ["Dear Sir", "Madam / Dear Sir", "Dear Sir / Madam", "Sir / Madam"]
#             if any(s in ln for s in salutations):
#                 stage = "title_after_sal"
#                 continue
#             else:
#                 title = ln
#                 stage = "collect_body"
#                 continue

#         if stage == "title_after_sal":
#             title = ln
#             stage = "collect_body"
#             continue

#         if stage == "collect_body":
#             body_lines.append(ln)

#     return ref_no, issue_date, title, "\n".join(body_lines)

# # ---------------- MAIN LOOP ----------------

# if __name__ == "__main__":

#     notifications = fetch_notifications()
#     session = Session()

#     for idx, item in enumerate(notifications, start=1):

#         print(f"\n===== [{idx}] {item['title']} =====")

#         pdf_url = extract_pdf_link(item)
#         if not pdf_url:
#             print("❌ No PDF found — skipping")
#             continue

#         print("🔗 PDF URL:", pdf_url)

#         pdf_bytes = download_pdf_via_selenium(pdf_url)
#         if not pdf_bytes:
#             print("❌ Failed to fetch PDF — skipping")
#             continue

#         text = extract_text_from_pdf_bytes(pdf_bytes)
#         if not text:
#             print("⚠️ No text extracted — skipping")
#             continue

#         ref_no, issue_date, title, body_text = parse_pdf_text(text)

#         if not title:
#             title = item["title"]

#         exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
#         if exists:
#             print("🔁 Already stored — skipping")
#         else:
#             circ = Circular(
#                 ref_no=ref_no,
#                 issue_date=issue_date,
#                 title=title,
#                 pdf_url=pdf_url,
#                 body_text=body_text
#             )
#             session.add(circ)
#             session.commit()
#             print("✔ Stored:", title)

#         time.sleep(0.5)

#     session.close()
#     print("\n🎉 Extraction & DB storage complete!")



# data is stored in the database but it misses many values in the cell.....

# import os
# import time
# import re
# import urllib.parse
# import requests
# from bs4 import BeautifulSoup

# import pdfplumber
# import fitz  # PyMuPDF

# from sqlalchemy import create_engine, Column, Integer, String, Text
# from sqlalchemy.orm import sessionmaker, declarative_base

# # ---------------- DATABASE SETUP -----------------

# engine = create_engine("sqlite:///data.db", echo=False)
# Session = sessionmaker(bind=engine)
# Base = declarative_base()

# class Circular(Base):
#     __tablename__ = "circulars"
#     id = Column(Integer, primary_key=True)
#     ref_no = Column(String)
#     issue_date = Column(String)
#     title = Column(String)
#     pdf_url = Column(String, unique=True)
#     body_text = Column(Text)

# Base.metadata.create_all(engine)

# # ---------------- CONSTANTS -----------------

# BASE = "https://rbi.org.in/Scripts/"
# NOTIFY_INDEX = BASE + "NotificationUser.aspx"

# HEADERS = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                   "AppleWebKit/537.36 (KHTML, like Gecko) "
#                   "Chrome/120.0.0.0 Safari/537.36",
#     "Accept": "*/*",
# }

# PDF_HEADERS = {
#     "User-Agent": HEADERS["User-Agent"],
#     "Referer": "https://rbidocs.rbi.org.in/",
#     "Accept": "application/pdf",
# }

# PDF_DIR = "data_pdfs"
# os.makedirs(PDF_DIR, exist_ok=True)

# # ---------------- FETCH NOTIFICATIONS ----------------

# def fetch_notifications():
#     print("📡 Fetching list of RBI notifications…")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifications = []
#     for row in soup.select("table.tablebg tr"):
#         a = row.find("a", class_="link2")
#         if not a:
#             continue

#         href = a.get("href", "")
#         if "Id=" not in href:
#             continue

#         params = urllib.parse.parse_qs(href.split("?")[1])
#         circ_id = params.get("Id", [""])[0]
#         mode = params.get("Mode", [""])[0]
#         title = a.text.strip()

#         notifications.append({
#             "title": title,
#             "id": circ_id,
#             "mode": mode
#         })

#     print(f"✔ Found {len(notifications)} notifications")
#     return notifications

# # ---------------- PDF URL EXTRACTION ----------------

# def extract_pdf_link(item):
#     url = f"{BASE}NotificationUser.aspx?Id={item['id']}&Mode={item['mode']}"
#     time.sleep(0.2)

#     r = requests.get(url, headers=HEADERS)
#     soup = BeautifulSoup(r.text, "html.parser")

#     pdf_tag = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
#     if pdf_tag:
#         pdf_url = pdf_tag["href"]
#         if not pdf_url.startswith("http"):
#             pdf_url = urllib.parse.urljoin(BASE, pdf_url)
#         return pdf_url

#     return None

# # ---------------- DOWNLOAD PDF ----------------

# def download_pdf(pdf_url):
#     filename = os.path.join(PDF_DIR, os.path.basename(pdf_url))
#     if os.path.exists(filename):
#         return filename

#     print("📥 Downloading:", os.path.basename(pdf_url))
#     r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
#     if r.status_code == 200 and r.headers.get("Content-Type","").lower().startswith("application/pdf"):
#         with open(filename, "wb") as f:
#             f.write(r.content)
#         return filename
#     else:
#         print("⚠️ Could not download PDF (status code:", r.status_code, ")")
#         return None

# # ---------------- EXTRACT PDF TEXT ----------------

# def extract_text_from_pdf(pdf_path):
#     text = ""
#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             for p in pdf.pages:
#                 page_text = p.extract_text()
#                 if page_text:
#                     text += page_text + "\n"
#     except Exception:
#         pass

#     if not text.strip():
#         try:
#             doc = fitz.open(pdf_path)
#             for p in doc:
#                 text += p.get_text("text") + "\n"
#         except Exception:
#             pass

#     return text.strip()

# # ---------------- PARSE METADATA ----------------

# def parse_pdf_text(text):
#     lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

#     ref_no = ""
#     issue_date = ""
#     title = ""
#     body_lines = []

#     ref_pattern = r"[A-Z]+\.\w+(\.\w+)*\.[0-9/]+"
#     date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

#     stage = "find_ref"
#     for ln in lines:

#         if stage == "find_ref":
#             m = re.search(ref_pattern, ln)
#             if m:
#                 ref_no = m.group(0)
#                 stage = "find_date"
#             continue

#         if stage == "find_date":
#             m = re.search(date_pattern, ln)
#             if m:
#                 issue_date = m.group(0)
#                 stage = "title_or_sal"
#             continue

#         if stage == "title_or_sal":
#             salutations = ["Dear Sir", "Madam / Dear Sir", "Dear Sir / Madam", "Sir / Madam"]
#             if any(s in ln for s in salutations):
#                 stage = "title_after_sal"
#                 continue
#             else:
#                 title = ln
#                 stage = "collect_body"
#                 continue

#         if stage == "title_after_sal":
#             title = ln
#             stage = "collect_body"
#             continue

#         if stage == "collect_body":
#             body_lines.append(ln)

#     return ref_no, issue_date, title, "\n".join(body_lines)

# # ---------------- MAIN EXECUTION ----------------

# if __name__ == "__main__":

#     notifications = fetch_notifications()
#     session = Session()

#     for idx, item in enumerate(notifications, start=1):

#         print(f"\n===== [{idx}] {item['title']} =====")

#         pdf_url = extract_pdf_link(item)
#         if not pdf_url:
#             print("⚠️ No PDF link found — skipping")
#             continue

#         print("📌 PDF URL:", pdf_url)

#         pdf_file = download_pdf(pdf_url)
#         if not pdf_file:
#             print("⚠️ Download failed — skipping")
#             continue

#         text = extract_text_from_pdf(pdf_file)
#         if not text:
#             print("⚠️ No text extracted — skipping")
#             continue

#         ref_no, issue_date, title, body_text = parse_pdf_text(text)
#         if not title:
#             title = item["title"]

#         exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
#         if exists:
#             print("🔁 Already in database — skipping")
#         else:
#             circ = Circular(
#                 ref_no=ref_no,
#                 issue_date=issue_date,
#                 title=title,
#                 pdf_url=pdf_url,
#                 body_text=body_text
#             )
#             session.add(circ)
#             session.commit()
#             print("✔ Stored:", title)

#         time.sleep(0.3)

#     session.close()
#     print("\n🎉 Done!")



# import os
# import time
# import re
# import urllib.parse
# import requests
# from bs4 import BeautifulSoup

# import pdfplumber
# import fitz  # PyMuPDF

# from sqlalchemy import create_engine, Column, Integer, String, Text
# from sqlalchemy.orm import sessionmaker, declarative_base

# # ---------------- DATABASE SETUP -----------------

# engine = create_engine("sqlite:///data.db", echo=False)
# Session = sessionmaker(bind=engine)
# Base = declarative_base()

# class Circular(Base):
#     __tablename__ = "circulars"
#     id = Column(Integer, primary_key=True)
#     ref_no = Column(String)
#     issue_date = Column(String)
#     title = Column(String)
#     pdf_url = Column(String, unique=True)
#     body_text = Column(Text)

# Base.metadata.create_all(engine)

# # ---------------- CONSTANTS -----------------

# BASE = "https://rbi.org.in/Scripts/"
# NOTIFY_INDEX = BASE + "NotificationUser.aspx"

# HEADERS = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
#                   " AppleWebKit/537.36 (KHTML, like Gecko)"
#                   " Chrome/120.0.0.0 Safari/537.36",
#     "Accept": "*/*",
# }

# PDF_HEADERS = {
#     "User-Agent": HEADERS["User-Agent"],
#     "Referer": "https://rbidocs.rbi.org.in/",
#     "Accept": "application/pdf",
# }

# PDF_DIR = "data_pdfs"
# os.makedirs(PDF_DIR, exist_ok=True)


# # ---------------- FETCH RBI NOTIFICATIONS ----------------

# def fetch_notifications():
#     print("📡 Fetching RBI notification list…")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifications = []
#     for row in soup.select("table.tablebg tr"):
#         a = row.find("a", class_="link2")
#         if not a:
#             continue

#         href = a.get("href", "")
#         if "Id=" not in href:
#             continue

#         params = urllib.parse.parse_qs(href.split("?")[1])
#         circ_id = params.get("Id", [""])[0]
#         mode = params.get("Mode", [""])[0]
#         title = a.text.strip()

#         notifications.append({
#             "title": title,
#             "id": circ_id,
#             "mode": mode
#         })

#     print(f"✔ Found {len(notifications)} notifications")
#     return notifications


# # ---------------- PDF URL EXTRACTION ----------------

# def extract_pdf_link(item):
#     page_url = f"{BASE}NotificationUser.aspx?Id={item['id']}&Mode={item['mode']}"
#     time.sleep(0.2)

#     r = requests.get(page_url, headers=HEADERS)
#     soup = BeautifulSoup(r.text, "html.parser")

#     pdf_tag = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
#     if pdf_tag:
#         pdf_url = pdf_tag["href"]
#         if not pdf_url.startswith("http"):
#             pdf_url = urllib.parse.urljoin(BASE, pdf_url)
#         return pdf_url

#     return None


# # ---------------- PDF DOWNLOAD ----------------

# def download_pdf(pdf_url):
#     fname = os.path.join(PDF_DIR, os.path.basename(pdf_url))
#     if os.path.exists(fname):
#         return fname

#     print("📥 Downloading", os.path.basename(pdf_url))
#     r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
#     if r.status_code == 200 and b"%PDF" in r.content[:5]:
#         with open(fname, "wb") as f:
#             f.write(r.content)
#         return fname
#     else:
#         print("⚠️ Could not download PDF (blocked or invalid).")
#         return None


# # ---------------- BETTER TEXT EXTRACTION ----------------

# def extract_text_pdf(pdf_path):
#     """
#     Extract text from PDF with more coverage:
#     - Use pdfplumber blocks + sort
#     - Fallback to PyMuPDF
#     """

#     text = ""

#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             all_pages = []

#             for page in pdf.pages:
#                 # get text in blocks to preserve position
#                 blocks = page.extract_words(use_text_flow=True)

#                 # sort blocks by top->bottom then left->right
#                 blocks.sort(key=lambda b: (round(b["top"], 1), round(b["x0"], 1)))

#                 page_text = "\n".join([b["text"] for b in blocks])
#                 all_pages.append(page_text.strip())

#             text = "\n\n".join(all_pages)

#     except Exception as e:
#         print("⚠️ pdfplumber extraction issue:", e)

#     # fallback if empty
#     if not text.strip():
#         try:
#             doc = fitz.open(pdf_path)
#             for p in doc:
#                 text += p.get_text("text") + "\n"
#         except Exception as e:
#             print("⚠️ PyMuPDF fallback issue:", e)

#     return text.strip()


# # ---------------- PARSE METADATA ----------------

# def parse_pdf_text(text):
#     """
#     Extract structured metadata:
#     - ref_no
#     - issue_date
#     - title
#     - body_text
#     """

#     lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

#     ref_no = ""
#     issue_date = ""
#     title = ""
#     body_lines = []

#     # Patterns seen in RBI PDFs
#     ref_pattern = r"[A-Z]+\.\w+(\.\w+)*\.[0-9/]+"   # e.g., FIDD.CO.PSD.BC.No.11/…
#     date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

#     stage = "find_ref"

#     for ln in lines:

#         if stage == "find_ref":
#             m = re.search(ref_pattern, ln)
#             if m:
#                 ref_no = m.group(0).strip()
#                 stage = "find_date"
#             continue

#         if stage == "find_date":
#             m = re.search(date_pattern, ln)
#             if m:
#                 issue_date = m.group(0).strip()
#                 stage = "title_or_sal"
#             continue

#         if stage == "title_or_sal":
#             # Detect typical salutations
#             salutations = ["Dear Sir", "Madam / Dear Sir", "Dear Sir / Madam", "Sir / Madam"]
#             if any(s in ln for s in salutations):
#                 stage = "title_after_sal"
#                 continue
#             else:
#                 # no salutation → this is title
#                 title = ln
#                 stage = "collect_body"
#                 continue

#         if stage == "title_after_sal":
#             title = ln
#             stage = "collect_body"
#             continue

#         if stage == "collect_body":
#             body_lines.append(ln)

#     body_text = "\n".join(body_lines)
#     return ref_no, issue_date, title, body_text


# # ---------------- MAIN EXECUTION ----------------

# if __name__ == "__main__":

#     notifications = fetch_notifications()
#     session = Session()

#     for idx, item in enumerate(notifications, start=1):

#         print(f"\n===== [{idx}] {item['title']} =====")

#         pdf_url = extract_pdf_link(item)
#         if not pdf_url:
#             print("⚠️ No PDF link — skip")
#             continue

#         pdf_file = download_pdf(pdf_url)
#         if not pdf_file:
#             print("⚠️ Download failed — skip")
#             continue

#         extracted_text = extract_text_pdf(pdf_file)
#         if not extracted_text:
#             print("⚠️ No text extracted — skip")
#             continue

#         ref_no, issue_date, title, body_text = parse_pdf_text(extracted_text)

#         if not title:
#             # fallback: use notification list title
#             title = item["title"]

#         # avoid duplicate
#         exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
#         if exists:
#             print("🔁 Already in DB — skip")
#         else:
#             circ = Circular(
#                 ref_no=ref_no,
#                 issue_date=issue_date,
#                 title=title,
#                 pdf_url=pdf_url,
#                 body_text=body_text
#             )
#             session.add(circ)
#             session.commit()
#             print("✔ Stored:", title)

#         time.sleep(0.3)

#     session.close()
#     print("\n🎉 Extraction & Storage Complete!")



#   ref_pattern = r"RBI/\d{4}-\d{2}/\d+"
#     date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

#     stage = "find_ref"

#     for i, ln in enumerate(lines):

#         # → FIND CIRCULAR REF
#         if stage == "find_ref":
#             m = re.search(ref_pattern, ln)
#             if m:
#                 ref_no = m.group(0)
#                 stage = "find_date"
#             continue

#         # → FIND ISSUE DATE
#         if stage == "find_date":
#             m = re.search(date_pattern, ln)
#             if m:
#                 issue_date = m.group(0)
#                 stage = "find_salutation"
#             continue

#         # → LOOK FOR SALUTATION
#         if stage == "find_salutation":
#            salutations = [
#             "Madam / Dear Sir",  "Madam/Dear Sir",  "Madam /Dear Sir",  "Madam/ Dear Sir",   "Madam / Dear Sir,",  "Madam/Dear Sir,",  "Madam /Dear Sir,", "Madam/ Dear Sir,",
#             "Dear Sir / Madam",  "Dear Sir/Madam",  "Dear Sir /Madam",  "Dear Sir/ Madam",  "Dear Sir / Madam,",  "Dear Sir/Madam,", "Dear Sir /Madam,", "Dear Sir/ Madam,",
#             "Madam / Sir",  "Madam/Sir",  "Madam /Sir",  "Madam/ Sir",  "Madam / Sir,",  "Madam/Sir,",  "Madam /Sir,",   "Madam/ Sir,", 
#             "Sir / Madam",  "Sir/Madam",  "Sir /Madam",  "Sir/ Madam",  "Sir / Madam,",  "Sir/Madam,",  "Sir /Madam,",  "Sir/ Madam,",
#             "Dear Madam / Sir",  "Dear Madam/Sir", "Dear Madam /Sir", "Dear Madam/ Sir",  "Dear Madam / Sir,", "Dear Madam/Sir,", "Dear Madam /Sir,", "Dear Madam/ Sir,",  "Dear Sir / Madam",
#             "Dear Sir/Madam",  "Dear Sir / Madam,",  "Dear Sir/Madam,"]



#missed few values in the database 

# import os
# import time
# import re
# import urllib.parse
# import requests
# from bs4 import BeautifulSoup
# import pdfplumber
# import fitz  # PyMuPDF

# from sqlalchemy import create_engine, Column, Integer, String, Text
# from sqlalchemy.orm import sessionmaker, declarative_base

# engine = create_engine("sqlite:///data.db", echo=False)
# Session = sessionmaker(bind=engine)
# Base = declarative_base()

# class Circular(Base):
#     __tablename__ = "circulars"
#     id = Column(Integer, primary_key=True)
#     ref_no = Column(String)
#     issue_date = Column(String)
#     title = Column(String)
#     pdf_url = Column(String, unique=True)
#     body_text = Column(Text)

# Base.metadata.create_all(engine)

# BASE = "https://rbi.org.in/Scripts/"
# NOTIFY_INDEX = BASE + "NotificationUser.aspx"

# HEADERS = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
#                   " AppleWebKit/537.36 (KHTML, like Gecko)"
#                   " Chrome/120.0.0.0 Safari/537.36",
#     "Accept": "*/*",
# }

# PDF_HEADERS = {
#     "User-Agent": HEADERS["User-Agent"],
#     "Referer": "https://rbidocs.rbi.org.in/",
#     "Accept": "application/pdf",
# }

# PDF_DIR = "data_pdfs"
# os.makedirs(PDF_DIR, exist_ok=True)

# def fetch_notifications():
#     print("📡 Fetching RBI notification list…")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifications = []
#     for row in soup.select("table.tablebg tr"):
#         a = row.find("a", class_="link2")
#         if not a:
#             continue

#         href = a.get("href", "")
#         if "Id=" not in href:
#             continue

#         params = urllib.parse.parse_qs(href.split("?")[1])
#         circ_id = params.get("Id", [""])[0]
#         mode = params.get("Mode", [""])[0]
#         title = a.text.strip()

#         notifications.append({
#             "title": title,
#             "id": circ_id,
#             "mode": mode
#         })

#     print(f"✔ Found {len(notifications)} notifications")
#     return notifications

# def extract_pdf_link(item):
#     page_url = f"{BASE}NotificationUser.aspx?Id={item['id']}&Mode={item['mode']}"
#     time.sleep(0.2)

#     r = requests.get(page_url, headers=HEADERS)
#     soup = BeautifulSoup(r.text, "html.parser")

#     pdf_tag = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
#     if pdf_tag:
#         pdf_url = pdf_tag["href"]
#         if not pdf_url.startswith("http"):
#             pdf_url = urllib.parse.urljoin(BASE, pdf_url)
#         return pdf_url

#     return None

# def download_pdf(pdf_url):
#     fname = os.path.join(PDF_DIR, os.path.basename(pdf_url))
#     if os.path.exists(fname):
#         return fname

#     print("📥 Downloading", os.path.basename(pdf_url))
#     r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
#     if r.status_code == 200 and b"%PDF" in r.content[:5]:
#         with open(fname, "wb") as f:
#             f.write(r.content)
#         return fname
#     else:
#         print("⚠️ Could not download PDF (blocked or invalid).")
#         return None

# def extract_text_pdf(pdf_path):
#     """
#     Extract text from PDF with more coverage:
#     - Use pdfplumber blocks + sort
#     - Fallback to PyMuPDF
#     """

#     text = ""

#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             all_pages = []

#             for page in pdf.pages:
#                 # get text in blocks to preserve position
#                 blocks = page.extract_words(use_text_flow=True)

#                 # sort blocks by top->bottom then left->right
#                 blocks.sort(key=lambda b: (round(b["top"], 1), round(b["x0"], 1)))

#                 page_text = "\n".join([b["text"] for b in blocks])
#                 all_pages.append(page_text.strip())

#             text = "\n\n".join(all_pages)

#     except Exception as e:
#         print("⚠️ pdfplumber extraction issue:", e)

#     # fallback if empty
#     if not text.strip():
#         try:
#             doc = fitz.open(pdf_path)
#             for p in doc:
#                 text += p.get_text("text") + "\n"
#         except Exception as e:
#             print("⚠️ PyMuPDF fallback issue:", e)

#     return text.strip()

# def parse_pdf_text(text):
#     """
#     Extract structured metadata:
#     - ref_no
#     - issue_date
#     - title
#     - body_text
#     """

#     lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

#     ref_no = ""
#     issue_date = ""
#     title = ""
#     body_lines = []

#     # Patterns seen in RBI PDFs
#     ref_pattern = r"[A-Z]+\.\w+(\.\w+)*\.[0-9/]+"   # e.g., FIDD.CO.PSD.BC.No.11/…
#     date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

#     stage = "find_ref"

#     for ln in lines:

#         if stage == "find_ref":
#             m = re.search(ref_pattern, ln)
#             if m:
#                 ref_no = m.group(0).strip()
#                 stage = "find_date"
#             continue

#         if stage == "find_date":
#             m = re.search(date_pattern, ln)
#             if m:
#                 issue_date = m.group(0).strip()
#                 stage = "title_or_sal"
#             continue

#         if stage == "title_or_sal":
#             # Detect typical salutations
#             salutations = ["Dear Sir", "Madam / Dear Sir", "Dear Sir / Madam", "Sir / Madam"]
#             if any(s in ln for s in salutations):
#                 stage = "title_after_sal"
#                 continue
#             else:
#                 # no salutation → this is title
#                 title = ln
#                 stage = "collect_body"
#                 continue

#         if stage == "title_after_sal":
#             title = ln
#             stage = "collect_body"
#             continue

#         if stage == "collect_body":
#             body_lines.append(ln)

#     body_text = "\n".join(body_lines)
#     return ref_no, issue_date, title, body_text

# if __name__ == "__main__":

#     notifications = fetch_notifications()
#     session = Session()

#     for idx, item in enumerate(notifications, start=1):

#         print(f"\n===== [{idx}] {item['title']} =====")

#         pdf_url = extract_pdf_link(item)
#         if not pdf_url:
#             print("⚠️ No PDF link — skip")
#             continue

#         pdf_file = download_pdf(pdf_url)
#         if not pdf_file:
#             print("⚠️ Download failed — skip")
#             continue

#         extracted_text = extract_text_pdf(pdf_file)
#         if not extracted_text:
#             print("⚠️ No text extracted — skip")
#             continue

#         ref_no, issue_date, title, body_text = parse_pdf_text(extracted_text)

#         if not title:
#             # fallback: use notification list title
#             title = item["title"]

#         # avoid duplicate
#         exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
#         if exists:
#             print("🔁 Already in DB — skip")
#         else:
#             circ = Circular(
#                 ref_no=ref_no,
#                 issue_date=issue_date,
#                 title=title,
#                 pdf_url=pdf_url,
#                 body_text=body_text
#             )
#             session.add(circ)
#             session.commit()
#             print("✔ Stored:", title)

#         time.sleep(0.3)

#     session.close()
#     print("\n🎉 Extraction & Storage Complete!")




import os
import time
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup

import pdfplumber
import fitz

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------- DATABASE SETUP -----------------

engine = create_engine("sqlite:///data_.db", echo=False)
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                  " AppleWebKit/537.36 (KHTML, like Gecko)"
                  " Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

PDF_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Referer": "https://rbidocs.rbi.org.in/",
    "Accept": "application/pdf",
}

PDF_DIR = "data_"
os.makedirs(PDF_DIR, exist_ok=True)


# ---------------- FETCH NOTIFICATIONS ----------------

def fetch_notifications():
    print("📡 Fetching RBI notification list…")
    res = requests.get(NOTIFY_INDEX, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    notifications = []
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
        title = a.text.strip()

        notifications.append({
            "title": title,
            "id": circ_id,
            "mode": mode
        })

    print(f"✔ Found {len(notifications)} notifications")
    return notifications


# ---------------- PDF LINK EXTRACTION ----------------

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


# ---------------- PDF DOWNLOAD ----------------

def download_pdf(pdf_url):
    fname = os.path.join(PDF_DIR, os.path.basename(pdf_url))
    if os.path.exists(fname):
        return fname

    r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
    if r.status_code == 200 and b"%PDF" in r.content[:4]:
        with open(fname, "wb") as f:
            f.write(r.content)
        return fname
    return None


# ---------------- TEXT EXTRACTION ----------------

def extract_text_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for p in pdf.pages:
                page_words = p.extract_words(use_text_flow=True)
                page_words.sort(key=lambda w: (round(w["top"],1), round(w["x0"],1)))
                text += " ".join([w["text"] for w in page_words]) + "\n"
    except Exception:
        pass

    if not text.strip():
        try:
            doc = fitz.open(pdf_path)
            for p in doc:
                text += p.get_text("text") + "\n"
        except Exception:
            pass

    return text.strip()


# ---------------- UPDATED PARSING ----------------

def parse_circular_text(text):
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    ref_no = ""
    issue_date = ""
    title = ""
    body_lines = []

    # Patterns
    date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

    i = 0

    # 1. Read reference (could be one or two lines)
    if i < len(lines):
        first = lines[i]
        if "/" in first and any(char.isdigit() for char in first):
            ref_no = first
            i += 1
            # next line can be part of ref_no too
            if i < len(lines) and "/" in lines[i] and any(char.isdigit() for char in lines[i]):
                ref_no = ref_no + " " + lines[i]
                i += 1

    # 2. Find date
    while i < len(lines):
        m = re.search(date_pattern, lines[i])
        if m:
            issue_date = m.group(0)
            i += 1
            break
        i += 1

    # 3. Detect title
    saluts = ["Dear Sir", "Madam / Dear Sir", "Dear Sir / Madam", "Sir / Madam"]
    if i < len(lines) and any(s in lines[i] for s in saluts):
        # skip salutation
        i += 1

    # Title may span multiple lines — gather until we hit body start
    title_lines = []
    while i < len(lines):
        if re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}", lines[i]):
            # another date means likely new section
            break
        if lines[i].endswith(":"):
            # Probably start of body
            break
        # Stop if this looks like body start
        if lines[i].lower().startswith("please") or lines[i].lower().startswith("in terms"):
            break

        title_lines.append(lines[i])
        i += 1
        # Limit title length to 3 lines
        if len(title_lines) >= 3:
            break

    title = " ".join(title_lines).strip()

    # 4. Body (remaining lines)
    while i < len(lines):
        body_lines.append(lines[i])
        i += 1

    body_text = "\n".join(body_lines)

    return ref_no, issue_date, title, body_text

if __name__ == "__main__":

    notifications = fetch_notifications()
    session = Session()

    for idx, item in enumerate(notifications, start=1):

        print(f"\n===== [{idx}] {item['title']} =====")

        pdf_url = extract_pdf_link(item)
        if not pdf_url:
            print("⚠️ No PDF found — skip")
            continue

        pdf_file = download_pdf(pdf_url)
        if not pdf_file:
            print("⚠️ PDF download failed — skip")
            continue

        text = extract_text_pdf(pdf_file)
        if not text.strip():
            print("⚠️ No text extracted — skip")
            continue

        ref_no, issue_date, title, body_text = parse_circular_text(text)

        if not title.strip():
            title = item["title"]

        exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
        if exists:
            print("🔁 Already stored — skip")
        else:
            circ = Circular(
                ref_no=ref_no,
                issue_date=issue_date,
                title=title,
                pdf_url=pdf_url,
                body_text=body_text
            )
            session.add(circ)
            session.commit()
            print("✔ Stored:", title)

        time.sleep(0.3)

    session.close()
    print("\n🎉 Extraction and storage complete!")
