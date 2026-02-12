# import os
# import re
# import time
# import urllib.parse
# import requests
# from bs4 import BeautifulSoup

# import pdfplumber
# import fitz  # PyMuPDF

# from sqlalchemy import create_engine, Column, Integer, String, Text
# from sqlalchemy.orm import sessionmaker, declarative_base

# # ---------------- SQLITE DB SETUP -----------------

# engine = create_engine("sqlite:///fetch.db", echo=False)
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

# PDF_DIR = "fetch"
# os.makedirs(PDF_DIR, exist_ok=True)

# def fetch_notifications():
#     print("📡 Fetching RBI notifications…")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifs = []
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

#         notifs.append({"title": title, "id": circ_id, "mode": mode})

#     print(f"✔ Found {len(notifs)} notifications")
#     return notifs

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


# # ---------------- DOWNLOAD PDF ----------------

# def download_pdf(pdf_url):
#     fname = os.path.join(PDF_DIR, os.path.basename(pdf_url))
#     if os.path.exists(fname):
#         return fname

#     print("📥 Downloading:", os.path.basename(pdf_url))
#     r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
#     if r.status_code == 200 and b"%PDF" in r.content[:4]:
#         with open(fname, "wb") as f:
#             f.write(r.content)
#         return fname
#     return None

# def extract_text_pdf(pdf_path):
#     """
#     Extract text using pdfplumber with positional sorting
#     fallback to PyMuPDF if needed.
#     """
#     text = ""
#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             lines = []
#             for page in pdf.pages:
#                 words = page.extract_words(use_text_flow=True)
#                 # sort by y then x
#                 words.sort(key=lambda w: (round(w["top"], 1), round(w["x0"], 1)))
#                 current_line = []
#                 last_top = None

#                 # group by approximate top
#                 for w in words:
#                     if last_top is None or abs(w["top"] - last_top) < 3:
#                         current_line.append(w["text"])
#                     else:
#                         lines.append(" ".join(current_line))
#                         current_line = [w["text"]]
#                     last_top = w["top"]

#                 if current_line:
#                     lines.append(" ".join(current_line))

#             text = "\n".join(lines).strip()

#     except Exception as e:
#         print("⚠️ pdfplumber issue:", e)

#     if not text.strip():
#         try:
#             doc = fitz.open(pdf_path)
#             for p in doc:
#                 text += p.get_text("text") + "\n"
#         except Exception as e:
#             print("⚠️ PyMuPDF fallback issue:", e)

#     return text.strip()

# def parse_circular_text(text):
#     """
#     Extract:
#      - ref_no
#      - issue_date
#      - title (with or without salutation)
#      - body_text
#     """
#     lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

#     ref_no = ""
#     issue_date = ""
#     title = ""
#     body_lines = []

#     # Patterns
#     date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

#     i = 0

#     # 1) Circular ref can be one or two lines
#     if i < len(lines) and "/" in lines[i]:
#         ref_no = lines[i]
#         i += 1
#         # sometimes second line is part of ref
#         if i < len(lines) and "/" in lines[i] and any(c.isdigit() for c in lines[i]):
#             ref_no = ref_no + " " + lines[i]
#             i += 1

#     # 2) Find issue date next
#     while i < len(lines):
#         m = re.search(date_pattern, lines[i])
#         if m:
#             issue_date = m.group(0)
#             i += 1
#             break
#         i += 1

#     # 3) Detect salutation
#     salutations = [
#         "Dear Sir", "Madam / Dear Sir", "Dear Sir / Madam",
#         "Sir / Madam", "Dear Sir/Madam", "Madam/Sir"
#     ]
#     if i < len(lines) and any(s in lines[i] for s in salutations):
#         i += 1

#     # 4) Title (can be multi-line)
#     title_lines = []
#     while i < len(lines):
#         ln = lines[i]
#         if re.search(date_pattern, ln):
#             break
#         if ln.lower().startswith("please") or ln.lower().startswith("in terms"):
#             break
#         title_lines.append(ln)
#         i += 1
#         if len(title_lines) >= 3:
#             break

#     title = " ".join(title_lines).strip()

#     # 5) Everything else is body
#     while i < len(lines):
#         body_lines.append(lines[i])
#         i += 1

#     body_text = "\n".join(body_lines)

#     return ref_no, issue_date, title, body_text

# if __name__ == "__main__":

#     notifications = fetch_notifications()
#     session = Session()

#     for idx, item in enumerate(notifications, start=1):

#         print(f"\n===== [{idx}] {item['title']} =====")

#         pdf_url = extract_pdf_link(item)
#         if not pdf_url:
#             print("⚠️ No PDF — skip")
#             continue

#         pdf_file = download_pdf(pdf_url)
#         if not pdf_file:
#             print("⚠️ Download failed — skip")
#             continue

#         text = extract_text_pdf(pdf_file)
#         if not text:
#             print("⚠️ Text extraction empty — skip")
#             continue

#         ref_no, issue_date, title, body_text = parse_circular_text(text)

#         if not title:
#             title = item["title"]

#         # insert into DB only if new
#         exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
#         if exists:
#             print("🔁 Already in DB — skip")
#             continue

#         circ = Circular(
#             ref_no=ref_no,
#             issue_date=issue_date,
#             title=title,
#             pdf_url=pdf_url,
#             body_text=body_text
#         )
#         session.add(circ)
#         session.commit()
#         print("✔ Stored:", title)

#         time.sleep(0.3)

#     session.close()
#     print("\n🎉 Extraction + DB storage complete!")


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

# engine = create_engine("sqlite:///f.db", echo=False)
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

# PDF_DIR = "f"
# os.makedirs(PDF_DIR, exist_ok=True)

# # ---------------- FETCH RBI NOTIFICATIONS ----------------

# def fetch_notifications():
#     print("📡 Fetching RBI notification list…")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifs = []
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

#         notifs.append({"title": title, "id": circ_id, "mode": mode})

#     print(f"✔ Found {len(notifs)} notifications")
#     return notifs

# # ---------------- EXTRACT PDF LINK ----------------

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

# # ---------------- DOWNLOAD PDF ----------------

# def download_pdf(pdf_url):
#     fname = os.path.join(PDF_DIR, os.path.basename(pdf_url))
#     if os.path.exists(fname):
#         return fname

#     print("📥 Downloading:", os.path.basename(pdf_url))
#     r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
#     if r.status_code == 200 and b"%PDF" in r.content[:4]:
#         with open(fname, "wb") as f:
#             f.write(r.content)
#         return fname
#     return None

# # ---------------- EXTRACT TEXT ----------------

# def extract_text_pdf(pdf_path):
#     text = ""
#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             lines = []
#             for page in pdf.pages:
#                 words = page.extract_words(use_text_flow=True)
#                 words.sort(key=lambda w: (round(w["top"],1), round(w["x0"],1)))

#                 current = []
#                 last_top = None
#                 for w in words:
#                     if last_top is None or abs(w["top"] - last_top) < 3:
#                         current.append(w["text"])
#                     else:
#                         lines.append(" ".join(current))
#                         current = [w["text"]]
#                     last_top = w["top"]
#                 if current:
#                     lines.append(" ".join(current))
#             text = "\n".join(lines).strip()
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

# # ---------------- PARSE LOGIC ----------------

# def parse_circular_text(text):
#     """
#     NEW improved parsing to:
#     1) capture text after date up to salutation
#     2) handle cases with/without salutation
#     3) assign title correctly
#     """
#     lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

#     ref_no = ""
#     issue_date = ""
#     addressed_to = ""
#     title = ""
#     body_lines = []

#     date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

#     i = 0

#     # 1️⃣ Circular reference could be 1 or 2 lines
#     if i < len(lines) and "/" in lines[i]:
#         ref_no = lines[i]
#         i += 1
#         if i < len(lines) and "/" in lines[i] and any(c.isdigit() for c in lines[i]):
#             ref_no += " " + lines[i]
#             i += 1

#     # 2️⃣ Issue date
#     while i < len(lines):
#         m = re.search(date_pattern, lines[i])
#         if m:
#             issue_date = m.group(0)
#             i += 1
#             break
#         i += 1

#     # 3️⃣ Collect "addressed to" if present (lines until salutation or next skip)
#     addressed = []
#     salutations = [
#             "Madam / Dear Sir",  "Madam/Dear Sir",  "Madam /Dear Sir",  "Madam/ Dear Sir",   "Madam / Dear Sir,",  "Madam/Dear Sir,",  "Madam /Dear Sir,", "Madam/ Dear Sir,",
#             "Dear Sir / Madam",  "Dear Sir/Madam",  "Dear Sir /Madam",  "Dear Sir/ Madam",  "Dear Sir / Madam,",  "Dear Sir/Madam,", "Dear Sir /Madam,", "Dear Sir/ Madam,",
#             "Madam / Sir",  "Madam/Sir",  "Madam /Sir",  "Madam/ Sir",  "Madam / Sir,",  "Madam/Sir,",  "Madam /Sir,",   "Madam/ Sir,", 
#             "Sir / Madam",  "Sir/Madam",  "Sir /Madam",  "Sir/ Madam",  "Sir / Madam,",  "Sir/Madam,",  "Sir /Madam,",  "Sir/ Madam,",
#             "Dear Madam / Sir",  "Dear Madam/Sir", "Dear Madam /Sir", "Dear Madam/ Sir",  "Dear Madam / Sir,", "Dear Madam/Sir,", "Dear Madam /Sir,", "Dear Madam/ Sir,",  "Dear Sir / Madam",
#             "Dear Sir/Madam",  "Dear Sir / Madam,",  "Dear Sir/Madam,"]
    
#     while i < len(lines) and not any(s in lines[i] for s in salutations):
#         # stop if this line looks like a title (capitalized and long)
#         if len(lines[i]) > 40 and lines[i][0].isupper() and NOT_TO_STOP(lines[i]):
#             break

#         addressed.append(lines[i])
#         i += 1

#     addressed_to = " ".join(addressed).strip()

#     # 4️⃣ Skip salutation
#     if i < len(lines) and any(s in lines[i] for s in salutations):
#         i += 1

#     # 5️⃣ Title detection
#     title_lines = []
#     while i < len(lines):
#         ln = lines[i]
#         # stop title when likely body start
#         if ln.lower().startswith("please") or ln.lower().startswith("in terms"):
#             break
#         # often body text paragraphs begin without capitalization
#         if ln and ln[0].islower():
#             break

#         title_lines.append(ln)
#         i += 1
#         if len(title_lines) >= 3:
#             break

#     title = " ".join(title_lines).strip()

#     # 6️⃣ Body text
#     while i < len(lines):
#         body_lines.append(lines[i])
#         i += 1

#     # include addressed_to into body if it exists
#     if addressed_to:
#         body_text = addressed_to + "\n" + "\n".join(body_lines)
#     else:
#         body_text = "\n".join(body_lines)

#     return ref_no, issue_date, title, body_text

# # ---------------- HELPER for title break ----------------

# def NOT_TO_STOP(line):
#     """
#     Very simple check:
#     If line contains a comma or dash inside, more likely a title continuation.
#     Allows longer title segments.
#     """
#     return "," in line or "-" in line

# # ---------------- MAIN ----------------

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

#         text = extract_text_pdf(pdf_file)
#         if not text:
#             print("⚠️ No text extracted — skip")
#             continue

#         ref_no, issue_date, title, body_text = parse_circular_text(text)

#         if not title:
#             title = item["title"]

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
#     print("\n🎉 Extraction & DB storage complete!")




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

# engine = create_engine("sqlite:///fetch_.db", echo=False)
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
#     "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                  "AppleWebKit/537.36 (KHTML, like Gecko) "
#                  "Chrome/120.0.0.0 Safari/537.36",
#     "Accept":"*/*",
# }

# PDF_HEADERS = {
#     "User-Agent":HEADERS["User-Agent"],
#     "Referer":"https://rbidocs.rbi.org.in/",
#     "Accept":"application/pdf",
# }

# PDF_DIR = "fetch_"
# os.makedirs(PDF_DIR, exist_ok=True)

# def fetch_notifications():
#     print("📡 Fetching RBI notification list…")
#     res = requests.get(NOTIFY_INDEX, headers=HEADERS)
#     soup = BeautifulSoup(res.text, "html.parser")

#     notifs = []
#     for row in soup.select("table.tablebg tr"):
#         a = row.find("a", class_="link2")
#         if not a: continue

#         href = a.get("href", "")
#         if "Id=" not in href: continue

#         params = urllib.parse.parse_qs(href.split("?")[1])
#         circ_id = params.get("Id", [""])[0]
#         mode = params.get("Mode", [""])[0]
#         title = a.text.strip()

#         notifs.append({"title":title, "id":circ_id, "mode":mode})

#     print(f"✔ Found {len(notifs)} notifications")
#     return notifs


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
#     if os.path.exists(fname): return fname

#     print("📥 Downloading:", os.path.basename(pdf_url))
#     r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
#     if r.status_code == 200 and b"%PDF" in r.content[:4]:
#         with open(fname,"wb") as f: f.write(r.content)
#         return fname
#     return None

# def extract_text_pdf(pdf_path):
#     text=""
#     try:
#         with pdfplumber.open(pdf_path) as pdf:
#             lines=[]
#             for page in pdf.pages:
#                 words = page.extract_words(use_text_flow=True)
#                 words.sort(key=lambda w:(round(w["top"],1), round(w["x0"],1)))
#                 current=[]
#                 last_top=None
#                 for w in words:
#                     if last_top is None or abs(w["top"]-last_top)<3:
#                         current.append(w["text"])
#                     else:
#                         lines.append(" ".join(current))
#                         current=[w["text"]]
#                     last_top=w["top"]
#                 if current: lines.append(" ".join(current))
#             text="\n".join(lines).strip()
#     except Exception:
#         pass

#     if not text.strip():
#         try:
#             doc=fitz.open(pdf_path)
#             for p in doc: text+=p.get_text("text")+"\n"
#         except Exception:
#             pass

#     return text.strip()

# def parse_circular_text(text):
#     lines=[ln.strip() for ln in text.split("\n") if ln.strip()]

#     ref_no=""
#     issue_date=""
#     title=""
#     body_lines=[]

#     date_pattern=r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

#     i=0

#     # 1️⃣ Ref No (maybe 1 or 2 lines)
#     if i<len(lines) and "/" in lines[i]:
#         ref_no=lines[i]; i+=1
#         if i<len(lines) and "/" in lines[i] and any(ch.isdigit() for ch in lines[i]):
#             # second line part of ref
#             ref_no+= " " + lines[i]
#             i+=1

#     # 2️⃣ Issue date
#     while i<len(lines):
#         m=re.search(date_pattern, lines[i])
#         if m:
#             issue_date=m.group(0)
#             i+=1
#             break
#         i+=1

#     # 3️⃣ Now check “To whom it’s written”
#     recipients=[]
#     salutations= [
#             "Madam / Dear Sir",  "Madam/Dear Sir",  "Madam /Dear Sir",  "Madam/ Dear Sir",   "Madam / Dear Sir,",  "Madam/Dear Sir,",  "Madam /Dear Sir,", "Madam/ Dear Sir,",
#             "Dear Sir / Madam",  "Dear Sir/Madam",  "Dear Sir /Madam",  "Dear Sir/ Madam",  "Dear Sir / Madam,",  "Dear Sir/Madam,", "Dear Sir /Madam,", "Dear Sir/ Madam,",
#             "Madam / Sir",  "Madam/Sir",  "Madam /Sir",  "Madam/ Sir",  "Madam / Sir,",  "Madam/Sir,",  "Madam /Sir,",   "Madam/ Sir,", 
#             "Sir / Madam",  "Sir/Madam",  "Sir /Madam",  "Sir/ Madam",  "Sir / Madam,",  "Sir/Madam,",  "Sir /Madam,",  "Sir/ Madam,",
#             "Dear Madam / Sir",  "Dear Madam/Sir", "Dear Madam /Sir", "Dear Madam/ Sir",  "Dear Madam / Sir,", "Dear Madam/Sir,", "Dear Madam /Sir,", "Dear Madam/ Sir,",  "Dear Sir / Madam",
#             "Dear Sir/Madam",  "Dear Sir / Madam,",  "Dear Sir/Madam,"]

#     while i<len(lines) and not any(s in lines[i] for s in salutations):
#         # stop collecting if looks like title start
#         if len(lines[i])>40 and lines[i][0].isupper():
#             # it's likely title
#             break
#         recipients.append(lines[i]); i+=1

#     # 4️⃣ Skip salutation
#     if i<len(lines) and any(s in lines[i] for s in salutations):
#         i+=1

#     # 5️⃣ Collect title (multi-line)
#     title_lines=[]
#     while i<len(lines):
#         ln=lines[i]
#         # detect body start:
#         if ln.lower().startswith("please") or ln.lower().startswith("in terms"):
#             break
#         # if line starts lower → likely body
#         if ln and ln[0].islower():
#             break
#         title_lines.append(ln)
#         i+=1
#         if len(title_lines)>=3:
#             break

#     title=" ".join(title_lines).strip()

#     # 6️⃣ Body
#     while i<len(lines):
#         body_lines.append(lines[i]); i+=1

#     body_text=" ".join(recipients + body_lines)

#     return ref_no, issue_date, title, body_text

# if __name__=="__main__":

#     notifications=fetch_notifications()
#     session=Session()

#     for idx,item in enumerate(notifications,start=1):
#         print(f"\n===== [{idx}] {item['title']} =====")

#         pdf_url=extract_pdf_link(item)
#         if not pdf_url:
#             print("⚠️ No PDF — skip"); continue

#         pdf_file=download_pdf(pdf_url)
#         if not pdf_file:
#             print("⚠️ Download failed — skip"); continue

#         text=extract_text_pdf(pdf_file)
#         if not text:
#             print("⚠️ No text — skip"); continue

#         ref_no, issue_date, title, body_text=parse_circular_text(text)

#         if not title:
#             title=item["title"]

#         exists=session.query(Circular).filter_by(pdf_url=pdf_url).first()
#         if exists:
#             print("🔁 Already in DB — skip"); continue

#         circ=Circular(
#             ref_no=ref_no,
#             issue_date=issue_date,
#             title=title,
#             pdf_url=pdf_url,
#             body_text=body_text
#         )

#         session.add(circ)
#         session.commit()
#         print("✔ Stored:", title)

#         time.sleep(0.3)

#     session.close()
#     print("\n🎉 Done!")



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

engine = create_engine("sqlite:///f_ext.db", echo=False)
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

PDF_DIR = "f_ext"
os.makedirs(PDF_DIR, exist_ok=True)


# ---------------- FETCH RBI NOTIFICATIONS ----------------

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
        title = a.text.strip()

        notifs.append({"title": title, "id": circ_id, "mode": mode})

    print(f"✔ Found {len(notifs)} notifications")
    return notifs


# ---------------- EXTRACT PDF LINK ----------------

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


# ---------------- DOWNLOAD PDF ----------------

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


# ---------------- TEXT EXTRACTION ----------------

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
    """
    Extracts:
      - ref_no (if exists)
      - issue_date
      - title (multi-line)
      - body_text (including any 'to …' lines)
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    ref_no = ""
    issue_date = ""
    title = ""
    body_lines = []

    date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

    i = 0

    # 1️⃣ Try to extract reference if it exists
    if i < len(lines) and re.search(r"(RBI/|DOR\.|FIDD\.)", lines[i]):
        ref_no = lines[i]
        i += 1
        # Sometimes ref splits onto two lines
        if i < len(lines) and "/" in lines[i] and any(c.isdigit() for c in lines[i]):
            ref_no += " " + lines[i]
            i += 1

    # 2️⃣ Find issue date
    while i < len(lines):
        match = re.search(date_pattern, lines[i])
        if match:
            issue_date = match.group(0)
            i += 1
            break
        i += 1

    # 3️⃣ Collect recipient (“To …”) lines if present
    addressed = []
    while i < len(lines) and lines[i].lower().startswith("to"):
        addressed.append(lines[i])
        i += 1

    # 4️⃣ Skip salutation if present
    salutations = ["Madam / Sir", "Madam/Sir", "Dear Sir / Madam", "Sir / Madam"]
    if i < len(lines) and any(s in lines[i] for s in salutations):
        i += 1

    # 5️⃣ Next non-blank is title (multi-line allowed)
    title_lines = []
    while i < len(lines):
        ln = lines[i]
        # Stop accumulating title if looks like body start
        if ln.lower().startswith("please") or ln.lower().startswith("in terms") or ln.lower().startswith("in exercise"):
            break
        # lowercase line often indicates body
        if ln and ln[0].islower():
            break
        title_lines.append(ln)
        i += 1
        # limit to 3 lines max
        if len(title_lines) >= 3:
            break

    title = " ".join(title_lines).strip()

    # 6️⃣ The rest is body
    while i < len(lines):
        body_lines.append(lines[i])
        i += 1

    # include addressed lines at top of body
    if addressed:
        body_text = " ".join(addressed + body_lines)
    else:
        body_text = " ".join(body_lines)

    return ref_no.strip(), issue_date.strip(), title.strip(), body_text.strip()


# ---------------- MAIN ----------------

if __name__ == "__main__":

    notifications = fetch_notifications()
    session = Session()

    for idx, item in enumerate(notifications[:10], start=1): # for 10 circulars
        print(f"\n===== [{idx}] {item['title']} =====")

        pdf_url = extract_pdf_link(item)
        if not pdf_url:
            print("⚠️ No PDF link found — skip")
            continue

        pdf_file = download_pdf(pdf_url)
        if not pdf_file:
            print("⚠️ Download failed — skip")
            continue

        raw_text = extract_text_pdf(pdf_file)
        if not raw_text:
            print("⚠️ Text extraction failed — skip")
            continue

        ref_no, issue_date, title, body_text = parse_circular_text(raw_text)

        # fallback if title still empty
        if not title:
            title = item["title"]

        # avoid duplicates
        exists = session.query(Circular).filter_by(pdf_url=pdf_url).first()
        if exists:
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

        print("✔ Stored:", ref_no, issue_date, title)

        # a tiny pause to avoid spammy loops
        time.sleep(0.3)

    session.close()
    print("\n🎉 Extraction & Storage Complete!")
