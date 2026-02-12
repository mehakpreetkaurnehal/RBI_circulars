# import os
# import re
# import time
# import requests
# import fitz  # PyMuPDF4LLM
# from bs4 import BeautifulSoup
# from urllib.parse import urljoin

# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager

# from sqlalchemy import create_engine, Column, Integer, String, Text
# from sqlalchemy.orm import sessionmaker, declarative_base

# # ---------------- DATABASE ----------------
# engine = create_engine("sqlite:///test_check.db", echo=False)
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

# # ---------------- CONSTANTS ----------------
# START_URL = "https://rbi.org.in/Scripts/NotificationUser.aspx"
# BASE_URL = "https://rbi.org.in"

# PDF_DIR = "test_check"
# os.makedirs(PDF_DIR, exist_ok=True)

# # ---------------- PDF HELPERS ----------------
# def download_pdf(pdf_url):
#     filename = os.path.join(PDF_DIR, pdf_url.split("/")[-1])
#     if not os.path.exists(filename):
#         r = requests.get(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
#         r.raise_for_status()
#         with open(filename, "wb") as f:
#             f.write(r.content)
#     return filename

# def extract_text_from_pdf(pdf_path):
#     doc = fitz.open(pdf_path)
#     text = ""
#     for page in doc:
#         text += page.get_text()
#     return text

# # ---------------- FIXED PARSER ----------------
# def parse_pdf_text(text):
#     lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

#     ref_no = ""
#     issue_date = ""
#     title_lines = []
#     body_lines = []

#     ref_pattern = r"RBI/\d{4}-\d{2}/\d+"
#     date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"

#     salutations = [
#         "Madam / Dear Sir", "Madam/Dear Sir", "Dear Sir / Madam",
#         "Dear Sir/Madam", "Sir / Madam", "Sir/Madam"
#     ]

#     stage = "find_ref"

#     for ln in lines:
#         if stage == "find_ref":
#             if re.search(ref_pattern, ln):
#                 ref_no = re.search(ref_pattern, ln).group(0)
#                 stage = "find_date"
#             continue

#         if stage == "find_date":
#             if re.search(date_pattern, ln):
#                 issue_date = re.search(date_pattern, ln).group(0)
#                 stage = "find_salutation"
#             continue

#         if stage == "find_salutation":
#             if any(s in ln for s in salutations):
#                 stage = "collect_title"
#             continue

#         # ✅ COLLECT MULTI-LINE TITLE
#         if stage == "collect_title":
#             if ln.endswith(".") or ln.lower().startswith(
#                 ("please refer", "in exercise", "it has been decided")
#             ):
#                 stage = "collect_body"
#                 body_lines.append(ln)
#             else:
#                 title_lines.append(ln)
#             continue

#         if stage == "collect_body":
#             body_lines.append(ln)

#     title = " ".join(title_lines).strip()
#     body_text = "\n".join(body_lines)

#     return ref_no, issue_date, title, body_text

# # ---------------- INDEX (SELENIUM) ----------------
# def fetch_latest_notification_pdfs():
#     options = webdriver.ChromeOptions()
#     options.add_argument("--headless")
#     driver = webdriver.Chrome(
#         service=Service(ChromeDriverManager().install()),
#         options=options
#     )

#     driver.get(START_URL)
#     time.sleep(5)

#     soup = BeautifulSoup(driver.page_source, "html.parser")
#     driver.quit()

#     pdf_urls = []

#     for a in soup.find_all("a", href=True):
#         if "Notification/PDFs" in a["href"]:
#             pdf_urls.append(urljoin(BASE_URL, a["href"]))

#     print(f"📄 Found {len(pdf_urls)} PDFs from latest notifications")
#     return list(set(pdf_urls))

# # ---------------- PIPELINE ----------------
# def process_pdfs(pdf_urls):
#     session = Session()

#     for pdf_url in pdf_urls:
#         if session.query(Circular).filter_by(pdf_url=pdf_url).first():
#             continue

#         try:
#             pdf_path = download_pdf(pdf_url)
#             raw_text = extract_text_from_pdf(pdf_path)
#             ref_no, issue_date, title, body_text = parse_pdf_text(raw_text)
#         except Exception as e:
#             print("❌ Failed:", pdf_url, e)
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

#         print(f"✔ Stored | {issue_date} | {title[:90]}")
#         time.sleep(0.2)

#     session.close()

# # ---------------- MAIN ----------------
# if __name__ == "__main__":
#     pdfs = fetch_latest_notification_pdfs()
#     process_pdfs(pdfs)
#     print("🎉 Latest RBI notifications extracted successfully!")





# import time
# import os
# import requests
# import pdfplumber
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager
# from bs4 import BeautifulSoup
# from urllib.parse import urljoin

# START_URL = "https://rbi.org.in/Scripts/NotificationUser.aspx"
# BASE_URL = "https://rbi.org.in"

# PDF_HEADERS = {
#     "User-Agent": "Mozilla/5.0",
#     "Referer": START_URL,
#     "Accept": "application/pdf"
# }

# # ---------------- SETUP SELENIUM ----------------
# options = webdriver.ChromeOptions()
# options.add_argument("--start-maximized")
# options.add_argument("--disable-blink-features=AutomationControlled")

# driver = webdriver.Chrome(
#     service=Service(ChromeDriverManager().install()),
#     options=options
# )

# # ---------------- PDF TEXT EXTRACTION ----------------
# def extract_pdf_text(pdf_url):
#     r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)

#     if b"<html" in r.content[:200]:
#         print("⚠️ Blocked PDF")
#         return None

#     filename = "temp.pdf"
#     with open(filename, "wb") as f:
#         f.write(r.content)

#     text = ""
#     try:
#         with pdfplumber.open(filename) as pdf:
#             for page in pdf.pages:
#                 text += page.extract_text() or ""
#     finally:
#         os.remove(filename)

#     return text


# # ---------------- MAIN PIPELINE ----------------
# def main():
#     print("🚀 Opening RBI Notification page")
#     driver.get(START_URL)
#     time.sleep(5)  # allow JS to load

#     # Right-side year links
#     year_links = driver.find_elements(By.XPATH, "//a[text()[number()]]")

#     print("📅 Years found:", [y.text for y in year_links])

#     for year_link in year_links:
#         year = year_link.text
#         print(f"\n➡ Clicking year {year}")
#         year_link.click()
#         time.sleep(4)

#         soup = BeautifulSoup(driver.page_source, "html.parser")

#         notifications = []

#         for a in soup.find_all("a", href=True):
#             if "Notification/PDFs" not in a["href"]:
#                 continue

#             title = a.get_text(strip=True)
#             pdf_url = urljoin(BASE_URL, a["href"])

#             block = a.parent.get_text(" ", strip=True)
#             date = block.replace(title, "").strip()

#             notifications.append({
#                 "date": date,
#                 "title": title,
#                 "pdf_url": pdf_url
#             })

#         print(f"✅ Notifications found: {len(notifications)}")

#         for i, n in enumerate(notifications, 1):
#             print(f"\n[{i}] {n['date']}")
#             print(n["title"])
#             print("PDF:", n["pdf_url"])

#             text = extract_pdf_text(n["pdf_url"])
#             if text:
#                 print("Text preview:")
#                 print(text[:300])

#         time.sleep(2)

#     driver.quit()


# if __name__ == "__main__":
#     main()
