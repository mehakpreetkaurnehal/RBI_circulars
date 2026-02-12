import os
import time
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
import json

import pdfplumber
import fitz  # PyMuPDF

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------- DATABASE SETUP -----------------

engine = create_engine("sqlite:///shared.db", echo=False)
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
POST_URL = "https://rbi.org.in/Scripts/NotificationUser.aspx"  # URL for POST requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

PDF_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Referer": "https://rbidocs.rbi.org.in/",
    "Accept": "application/pdf",
}

PDF_DIR = "Shared"
os.makedirs(PDF_DIR, exist_ok=True)

def get_available_years():
    """Parse the year tree from the main page to get all available years"""
    print("📡 Fetching available years from RBI notifications page…")
    res = requests.get(NOTIFY_INDEX, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")
    
    years = []
    # Find all year buttons in the date tree
    year_elements = soup.select('h2 a[id^="btn"]')
    
    for year_elem in year_elements:
        year_id = year_elem.get('id', '')
        if year_id.startswith('btn'):
            year = year_id[3:]  # Remove 'btn' prefix
            years.append(year)
    
    print(f"✔ Found {len(years)} years: {years}")
    return years

def get_notifications_for_year_month(year, month=0):
    """
    Fetch notifications for a specific year and month
    month=0 means all months in that year
    """
    print(f"  📋 Fetching notifications for {year} - Month: {month if month != 0 else 'All'}")
    
    # This simulates the GetYearMonth JavaScript function
    payload = {
        'year': year,
        'month': str(month),
        'mode': '0'  # Mode for regular notifications
    }
    
    try:
        # The actual endpoint that handles the AJAX request
        response = requests.post(
            POST_URL + "/GetYearMonth",  # Adjust this endpoint if needed
            data=payload,
            headers=HEADERS,
            timeout=30
        )
        
        if response.status_code == 200:
            # Parse the HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            notifications = parse_notifications_from_html(soup)
            print(f"    ✔ Found {len(notifications)} notifications")
            return notifications
        else:
            print(f"    ⚠️ Failed to fetch: {response.status_code}")
            
    except Exception as e:
        print(f"    ⚠️ Error: {e}")
    
    return []

def parse_notifications_from_html(soup):
    """Parse notifications from HTML content"""
    notifs = []
    
    # Find all notification entries
    for row in soup.select("table.tablebg tr"):
        a = row.find("a", class_="link2")
        if not a:
            continue
        
        href = a.get("href", "")
        if "Id=" not in href:
            continue
        
        # Extract the date from the tableheader
        date_header = row.find_previous("td", class_="tableheader")
        issue_date = ""
        if date_header:
            date_text = date_header.get_text(strip=True)
            # Extract date from format like "Feb 11, 2026"
            date_match = re.search(r'[A-Za-z]{3} \d{1,2}, \d{4}', date_text)
            if date_match:
                issue_date = date_match.group(0)
        
        params = urllib.parse.parse_qs(href.split("?")[1])
        circ_id = params.get("Id", [""])[0]
        mode = params.get("Mode", [""])[0]
        title = a.text.strip()
        
        # Find PDF link
        pdf_cell = row.find("td", colspan="3")
        if pdf_cell:
            pdf_link = pdf_cell.find("a", href=lambda x: x and ".pdf" in x.lower())
            if pdf_link:
                pdf_url = pdf_link["href"]
                if not pdf_url.startswith("http"):
                    pdf_url = urllib.parse.urljoin(BASE, pdf_url)
                
                notifs.append({
                    "title": title,
                    "id": circ_id,
                    "mode": mode,
                    "issue_date": issue_date,
                    "pdf_url": pdf_url
                })
    
    return notifs

def fetch_notifications_alternative():
    """
    Alternative method: Directly parse the page and follow the JavaScript links
    by constructing the appropriate POST requests
    """
    print("📡 Fetching RBI notifications using direct POST requests…")
    
    # First, get the main page to extract viewstate if needed
    session = requests.Session()
    res = session.get(NOTIFY_INDEX, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # Extract any hidden fields that might be required
    viewstate = soup.find('input', {'name': '__VIEWSTATE'})
    eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})
    viewstategen = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
    
    all_notifications = []
    # years = ['2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019', 
    #          '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011', 
    #          '2010', '2009', '2008', '2007', '2006', '2005', '2004', '2003', 
    #          '2002', '2001', '2000', '1999', '1998', '1997', '1996', '1995', 
    #          '1994', '1993', '1992', '1991']
    years = [ '2026', '2025', '2024']
    for year in years:
        print(f"\n📅 Processing year: {year}")
        
        # Try to get all months for this year first
        payload = {
            '__VIEWSTATE': viewstate.get('value') if viewstate else '',
            '__EVENTVALIDATION': eventvalidation.get('value') if eventvalidation else '',
            '__VIEWSTATEGENERATOR': viewstategen.get('value') if viewstategen else '',
            'year': year,
            'month': '0',  # 0 = all months
            'mode': '0'
        }
        
        try:
            # This might be the actual endpoint used by the GetYearMonth function
            response = session.post(
                "https://rbi.org.in/Scripts/NotificationUser.aspx/GetYearMonth",
                json={"year": year, "month": "0", "mode": "0"},
                headers={**HEADERS, "Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                # Try to parse JSON response
                try:
                    data = response.json()
                    if 'd' in data:
                        html_content = data['d']
                        soup = BeautifulSoup(html_content, 'html.parser')
                        notifications = parse_notifications_from_html(soup)
                        all_notifications.extend(notifications)
                        print(f"  ✔ Found {len(notifications)} notifications for {year}")
                except:
                    # If not JSON, try to parse as HTML
                    soup = BeautifulSoup(response.text, 'html.parser')
                    notifications = parse_notifications_from_html(soup)
                    all_notifications.extend(notifications)
                    print(f"  ✔ Found {len(notifications)} notifications for {year}")
            else:
                print(f"  ⚠️ Failed to fetch {year}: {response.status_code}")
                
        except Exception as e:
            print(f"  ⚠️ Error for year {year}: {e}")
        
        # Be respectful - add delay between requests
        time.sleep(1)
    
    print(f"\n✔ Total notifications found across all years: {len(all_notifications)}")
    return all_notifications

def extract_pdf_link(item):
    """Extract PDF link from notification detail page if not already available"""
    if item.get('pdf_url'):
        return item['pdf_url']
    
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
    
    print("    📥 Downloading:", os.path.basename(pdf_url))
    try:
        r = requests.get(pdf_url, headers=PDF_HEADERS, timeout=30)
        if r.status_code == 200 and b"%PDF" in r.content[:4]:
            with open(fname, "wb") as f:
                f.write(r.content)
            return fname
    except Exception as e:
        print(f"    ⚠️ Download failed: {e}")
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
    """Extract reference number, issue date, and body text from PDF content"""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    
    ref_no = ""
    issue_date = ""
    body_lines = []
    
    date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}"
    
    # Try to find date
    date_found = False
    for i, line in enumerate(lines):
        m = re.search(date_pattern, line)
        if m:
            issue_date = m.group(0)
            date_found = True
            # Look for reference number before date
            for j in range(max(0, i-3), i):
                if "/" in lines[j] and len(lines[j]) > 5:
                    ref_no = lines[j]
                    break
            # Body text after date
            body_lines = lines[i+1:]
            break
    
    # If no date found in text, try to find it from the item data
    if not date_found:
        # Look for RBI reference pattern
        for line in lines[:10]:
            if re.search(r'[A-Z]+\.?No\.?\s*[A-Z0-9/.-]+', line) or "/" in line:
                ref_no = line
                break
    
    body_text = " ".join(body_lines).strip() if body_lines else ""
    
    return ref_no, issue_date, body_text.strip()

if __name__ == "__main__":
    
    print("=" * 60)
    print("RBI CIRCULARS SCRAPER - ALL YEARS")
    print("=" * 60)
    
    # Get all notifications from all years
    all_notifications = fetch_notifications_alternative()
    
    if not all_notifications:
        print("⚠️ No notifications found. Trying alternative approach...")
        
        # Alternative: Parse the main page and follow the archive links
        years = ['2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019', 
                 '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011', 
                 '2010', '2009', '2008', '2007', '2006', '2005', '2004', '2003', 
                 '2002', '2001', '2000', '1999', '1998', '1997', '1996', '1995', 
                 '1994', '1993', '1992', '1991']
        
        all_notifications = []
        for year in years:
            print(f"\n📅 Fetching {year}...")
            
            # Construct URL with year parameter
            url = f"{BASE}NotificationUser.aspx?year={year}"
            try:
                res = requests.get(url, headers=HEADERS, timeout=30)
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Parse notifications from this page
                notifs = parse_notifications_from_html(soup)
                all_notifications.extend(notifs)
                print(f"  ✔ Found {len(notifs)} notifications for {year}")
                
                time.sleep(1)  # Be respectful
            except Exception as e:
                print(f"  ⚠️ Error fetching {year}: {e}")
    
    print(f"\n🎯 Total unique notifications to process: {len(all_notifications)}")
    
    session = Session()
    processed = 0
    skipped = 0
    failed = 0
    
    for idx, item in enumerate(all_notifications, start=1):
        print(f"\n===== [{idx}/{len(all_notifications)}] {item.get('title', 'No title')[:80]}... =====")
        
        # Get PDF URL
        pdf_url = extract_pdf_link(item)
        if not pdf_url:
            print("    ⚠️ No PDF link — skip")
            failed += 1
            continue
        
        # Check if already in database
        if session.query(Circular).filter_by(pdf_url=pdf_url).first():
            print("    🔁 Already in DB — skip")
            skipped += 1
            continue
        
        # Download PDF
        pdf_file = download_pdf(pdf_url)
        if not pdf_file:
            print("    ⚠️ Download failed — skip")
            failed += 1
            continue
        
        # Extract text
        raw_text = extract_text_pdf(pdf_file)
        if not raw_text:
            print("    ⚠️ Text extraction failed — skip")
            failed += 1
            continue
        
        # Parse content
        ref_no, issue_date, body_text = parse_circular_text(raw_text)
        
        # Use issue_date from PDF or from listing
        if not issue_date and item.get('issue_date'):
            issue_date = item['issue_date']
        
        title = item.get('title', '')
        
        # Save to database
        try:
            circ = Circular(
                ref_no=ref_no,
                issue_date=issue_date,
                title=title,
                pdf_url=pdf_url,
                body_text=body_text[:50000]  # Limit text length if needed
            )
            session.add(circ)
            session.commit()
            processed += 1
            
            print("    ✔ Stored:")
            if ref_no:
                print(f"      ref_no: {ref_no}")
            if issue_date:
                print(f"      issue_date: {issue_date}")
        except Exception as e:
            print(f"    ⚠️ Database error: {e}")
            session.rollback()
            failed += 1
        
        time.sleep(0.3)  # Rate limiting
    
    session.close()
    
    print("\n" + "=" * 60)
    print("🎉 SCRAPING COMPLETE!")
    print("=" * 60)
    print(f"✅ Successfully processed: {processed}")
    print(f"⏭️  Skipped (already in DB): {skipped}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total attempted: {len(all_notifications)}")
    print("=" * 60)