from bs4 import BeautifulSoup
import pdfplumber
import os
import requests
 
BASE = "https://www.rbi.org.in/scripts/"
INDEX_URL = BASE + "BS_CircularIndexDisplay.aspx"
 
headers = {
    "User-Agent": "Mozilla/5.0"
}
 
# STEP 1 — Get index page
res = requests.get(INDEX_URL, headers=headers)
soup = BeautifulSoup(res.text, "html.parser")
 
circular_links = []
 
# find circular links
for a in soup.find_all("a", class_="link2"):
    link = BASE + a["href"]
    circular_links.append(link)
 
print("Found circular pages:", len(circular_links))
 
# STEP 2 — Visit circular page → find PDF
def extract_pdf_url(page_url):
    r = requests.get(page_url, headers=headers)
    s = BeautifulSoup(r.text, "html.parser")
 
    pdf_link = s.find("a", href=lambda x: x and ".pdf" in x.lower())
 
    if pdf_link:
        return pdf_link["href"]
 
    return None
  
# STEP 3 — Download + extract PDF text
def extract_pdf_text(pdf_url):
 
    session = requests.Session()
 
    headers = {

        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.rbi.org.in/",
        "Accept": "application/pdf"
    }
 
    r = session.get(pdf_url, headers=headers)
 
    # Check if RBI blocked us

    if b"<html" in r.content[:100]:

        print("❌ CAPTCHA page received — RBI blocked download")

        return None
 
    filename = "circular.pdf"
 
    with open(filename, "wb") as f:

        f.write(r.content)
 
    import pdfplumber
 
    text = ""

    with pdfplumber.open(filename) as pdf:

        for page in pdf.pages:

            text += page.extract_text() or ""
 
    return text 
# Pipeline
for circular_page in circular_links[:10]:  # test first 3
    print("\nVisiting:", circular_page)
 
    pdf_url = extract_pdf_url(circular_page)
 
    if pdf_url:
        print("PDF:", pdf_url)
 
        # text = extract_pdf_text(pdf_url)
 
        # print("Extracted text preview:")
        # print(text[:500])
    else:
        print("No PDF found")
 
 
 
 
 
 
 
 
 
 
 
#  >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>



# import requests
# from bs4 import BeautifulSoup
# import time
# import pdfplumber
# import os

# # ---------------- CONFIG ----------------
# BASE = "https://www.rbi.org.in/scripts/"
# INDEX_URL = BASE + "BS_CircularIndexDisplay.aspx"

# HEADERS = {
#     "User-Agent": "Mozilla/5.0"
# }

# PDF_HEADERS = {
#     "User-Agent": "Mozilla/5.0",
#     "Referer": "https://www.rbi.org.in/",
#     "Accept": "application/pdf"
# }

# YEAR = 2024        # 🔴 CHANGE YEAR HERE
# DELAY = 1          # polite delay (seconds)
# DOWNLOAD_PDF = False  # True if you want text extraction

# session = requests.Session()

# # ---------------- STEP 1: Get circular pages for a year ----------------
# def get_circular_pages_for_year(year):
#     circular_pages = []

#     for month in range(1, 13):
#         payload = {
#             "hdnYear": year,
#             "hdnMonth": month
#         }

#         print(f"\nFetching {year}-{month:02d}")
#         r = session.post(INDEX_URL, headers=HEADERS, data=payload, timeout=30)

#         soup = BeautifulSoup(r.text, "html.parser")
#         rows = soup.find_all("a", class_="link2")

#         if not rows:
#             print("  No circulars")
#             continue

#         for row in rows:
#             circular_pages.append(BASE + row["href"])

#         time.sleep(DELAY)

#     return circular_pages


# # ---------------- STEP 2: Extract PDF link ----------------
# def extract_pdf_url(circular_page):
#     r = session.get(circular_page, headers=HEADERS, timeout=30)
#     soup = BeautifulSoup(r.text, "html.parser")

#     pdf = soup.find("a", href=lambda x: x and x.lower().endswith(".pdf"))
#     return pdf["href"] if pdf else None


# # ---------------- STEP 3: Extract PDF text (safe) ----------------
# def extract_pdf_text(pdf_url):
#     r = session.get(pdf_url, headers=PDF_HEADERS, timeout=30)

#     # RBI sometimes sends HTML instead of PDF
#     if b"<html" in r.content[:100]:
#         print("  ⚠️ Not a real PDF (blocked or redirected)")
#         return None

#     filename = "temp.pdf"
#     with open(filename, "wb") as f:
#         f.write(r.content)

#     text = ""
#     try:
#         with pdfplumber.open(filename) as pdf:
#             for page in pdf.pages:
#                 text += page.extract_text() or ""
#     except Exception as e:
#         print("  ⚠️ PDF read error:", e)
#         text = None
#     finally:
#         os.remove(filename)

#     return text


# # ---------------- PIPELINE ----------------
# def main():
#     print(f"\n🔎 Fetching RBI circulars for YEAR = {YEAR}")

#     circular_pages = get_circular_pages_for_year(YEAR)
#     print(f"\n✅ Total circulars found: {len(circular_pages)}")

#     for idx, circular_page in enumerate(circular_pages, 1):
#         print(f"\n[{idx}] Circular Page:")
#         print(circular_page)

#         pdf_url = extract_pdf_url(circular_page)
#         if not pdf_url:
#             print("  No PDF found")
#             continue

#         print("  PDF:", pdf_url)

#         if DOWNLOAD_PDF:
#             text = extract_pdf_text(pdf_url)
#             if text:
#                 print("  Text preview:")
#                 print(text[:300])

#         time.sleep(DELAY)


# # ---------------- RUN ----------------
# if __name__ == "__main__":
#     main()










# import requests

# from bs4 import BeautifulSoup

# import time
 
# url = "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx"
 
# session = requests.Session()

# headers = {"User-Agent": "Mozilla/5.0"}
 
# years = [2026, 2025, 2024]  # add more if needed
 
# for year in years:

#     for month in range(1, 13):
 
#         print(f"\nFetching Year {year} Month {month}")
 
#         payload = {

#             "hdnYear": year,

#             "hdnMonth": month

#         }
 
#         r = session.post(url, headers=headers, data=payload)
 
#         soup = BeautifulSoup(r.text, "html.parser")
 
#         rows = soup.find_all("a", class_="link2")
 
#         if not rows:

#             print("No data")

#             continue
 
#         for row in rows:

#             circular_link = "https://www.rbi.org.in/scripts/" + row["href"]

#             print("Circular:", circular_link)
 
#         time.sleep(1)  # polite delay

 