"""
RBI Latest Circulars Scraper (2021+)
Hybrid approach: Scrape index + Extract PDFs
Source: https://rbi.org.in/scripts/BS_CircularIndexDisplay.aspx

#1: This code is only extracting text of one circular.
"""

import os
import re
import sqlite3
import time
import requests
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

# NEW RBI URLs (2021+)
INDEX_URL = "https://rbi.org.in/scripts/BS_CircularIndexDisplay.aspx"
DETAIL_URL_BASE = "https://rbi.org.in/scripts/BS_CircularIndexDisplay.aspx?Id="
PDF_BASE = "https://rbidocs.rbi.org.in/rdocs/Notification/PDFs/"

# Storage
DB_PATH = "latest_rbi_circulars.db"
PDF_DIR = "latest_rbi_circulars"
os.makedirs(PDF_DIR, exist_ok=True)

def init_database():
    """Initialize database."""
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
    print("✓ Database initialized")

def scrape_index_table(year: int = 2026, limit: int = 100) -> List[Dict]:
    """
    Scrape the index table to get circular metadata.
    Returns list of circular info dicts.
    """
    circulars = []
    
    try:
        # The index page shows current year by default
        # You can filter by year using the sidebar
        response = requests.get(INDEX_URL, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the main table
        table = soup.find('table', {'class': 'tablebg'})
        if not table:
            print("❌ Table not found")
            return []
        
        # Get all rows (skip header)
        rows = table.find_all('tr')[1:]
        
        for row in rows[:limit]:
            cols = row.find_all('td')
            if len(cols) < 4:
                continue
            
            # Extract data from columns
            circular_number = cols[0].get_text(strip=True)
            date_of_issue = cols[1].get_text(strip=True)
            department = cols[2].get_text(strip=True)
            subject = cols[3].get_text(strip=True)
            meant_for = cols[4].get_text(strip=True) if len(cols) > 4 else ""
            
            # Get detail page link
            link = cols[0].find('a')
            detail_url = None
            circular_id = None
            
            if link and 'href' in link.attrs:
                href = link['href']
                # Extract ID from href like "?Id=13288"
                match = re.search(r'Id=(\d+)', href)
                if match:
                    circular_id = match.group(1)
                    detail_url = DETAIL_URL_BASE + circular_id
            
            circulars.append({
                'circular_number': circular_number,
                'date_of_issue': date_of_issue,
                'department': department,
                'subject': subject,
                'meant_for': meant_for,
                'detail_url': detail_url,
                'circular_id': circular_id
            })
        
        print(f"✓ Scraped {len(circulars)} circulars from index")
        return circulars
    
    except Exception as e:
        print(f"❌ Error scraping index: {e}")
        return []

def get_pdf_url_from_detail(detail_url: str) -> Optional[str]:
    """
    Visit detail page to get PDF URL.
    The PDF link is in the page HTML.
    """
    try:
        response = requests.get(detail_url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for PDF link - it's usually in an anchor with .PDF extension
        pdf_link = None
        
        # Method 1: Find direct PDF link
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '.PDF' in href.upper() or '.pdf' in href:
                if href.startswith('http'):
                    pdf_link = href
                else:
                    # Construct full URL
                    if href.startswith('/'):
                        pdf_link = 'https://rbidocs.rbi.org.in' + href
                    else:
                        pdf_link = PDF_BASE + href.split('/')[-1]
                break
        
        # Method 2: Look in page source for PDF filename
        if not pdf_link:
            # The PDF filename is in the HTML (as shown in Image 2 - yellow highlight)
            page_text = response.text
            match = re.search(r'([A-Z0-9]+\.PDF)', page_text, re.IGNORECASE)
            if match:
                pdf_filename = match.group(1)
                pdf_link = PDF_BASE + pdf_filename
        
        return pdf_link
    
    except Exception as e:
        print(f"  ⚠️ Error getting PDF URL: {e}")
        return None

def download_pdf(pdf_url: str) -> Optional[str]:
    """Download PDF and return local path."""
    try:
        filename = os.path.join(PDF_DIR, pdf_url.split('/')[-1])
        
        if os.path.exists(filename):
            return filename
        
        response = requests.get(pdf_url, timeout=60)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        return filename
    
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return None

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF with table preservation."""
    try:
        doc = fitz.open(pdf_path)
        full_text = []
        
        for page in doc:
            blocks = page.get_text("blocks")
            sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
            
            page_text = []
            for block in sorted_blocks:
                text = block[4].strip()
                if text:
                    # Detect tables
                    if re.search(r'\s{3,}|\t', text):
                        page_text.append(f"[TABLE]\n{text}\n[/TABLE]")
                    else:
                        page_text.append(text)
            
            full_text.append("\n".join(page_text))
        
        doc.close()
        return "\n\n".join(full_text)
    
    except Exception as e:
        print(f"  ❌ PDF extraction failed: {e}")
        return ""

def extract_text_from_web(detail_url: str) -> str:
    """
    Extract text directly from detail page HTML.
    Use as backup if PDF fails.
    """
    try:
        response = requests.get(detail_url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Main content is usually in a specific div
        # Adjust selector based on actual page structure
        content_div = soup.find('div', {'id': 'pnlDetails'})
        
        if not content_div:
            # Try other common containers
            content_div = soup.find('div', {'class': 'container_12'})
        
        if content_div:
            # Get text, preserving some structure
            text = content_div.get_text(separator='\n', strip=True)
            return text
        
        return ""
    
    except Exception as e:
        print(f"  ⚠️ Web extraction failed: {e}")
        return ""

def parse_circular_content(text: str) -> Dict:
    """
    Parse circular text to extract DOR number and structure.
    """
    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
    
    # Extract DOR number
    dor_number = ""
    for line in lines[:10]:  # Usually in first few lines
        if 'DOR' in line or 'DoR' in line:
            match = re.search(r'(DOR[^\s]+|DoR[^\s]+)', line, re.IGNORECASE)
            if match:
                dor_number = match.group(1)
                break
    
    return {
        'dor_number': dor_number,
        'full_text': text
    }

def process_circulars(limit: int = 50):
    """
    Complete pipeline:
    1. Scrape index table
    2. Get PDF URLs
    3. Extract text (PDF preferred, web backup)
    4. Store in database
    """
    
    print(f"\n{'='*70}")
    print(f"  RBI LATEST CIRCULARS SCRAPER")
    print(f"{'='*70}\n")
    
    # Initialize
    init_database()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Scrape index
    circulars = scrape_index_table(limit=limit)
    
    if not circulars:
        print("❌ No circulars found")
        return
    
    print(f"\n📊 Processing {len(circulars)} circulars...\n")
    
    stats = {'new': 0, 'skipped': 0, 'failed': 0}
    
    for idx, circ in enumerate(circulars, 1):
        print(f"[{idx}/{len(circulars)}] {circ['circular_number']}")
        
        # Check if exists
        cur.execute("SELECT id FROM circulars WHERE circular_number = ?", 
                   (circ['circular_number'],))
        if cur.fetchone():
            print(f"  ⏭️  Already exists")
            stats['skipped'] += 1
            continue
        
        # Get PDF URL from detail page
        pdf_url = None
        if circ['detail_url']:
            print(f"  🔍 Getting PDF URL...")
            pdf_url = get_pdf_url_from_detail(circ['detail_url'])
        
        body_text = ""
        extraction_method = "none"
        pdf_filename = ""
        
        # Method 1: Extract from PDF (preferred)
        if pdf_url:
            print(f"  📥 Downloading PDF...")
            pdf_path = download_pdf(pdf_url)
            
            if pdf_path:
                print(f"  📄 Extracting from PDF...")
                body_text = extract_text_from_pdf(pdf_path)
                extraction_method = "pdf"
                pdf_filename = os.path.basename(pdf_path)
        
        # Method 2: Extract from web (backup)
        if not body_text and circ['detail_url']:
            print(f"  🌐 Extracting from web...")
            body_text = extract_text_from_web(circ['detail_url'])
            extraction_method = "web"
        
        if not body_text:
            print(f"  ❌ Extraction failed")
            stats['failed'] += 1
            continue
        
        # Parse content
        parsed = parse_circular_content(body_text)
        
        # Save to database
        try:
            cur.execute("""
                INSERT INTO circulars 
                (circular_number, dor_number, date_of_issue, department, 
                 subject, meant_for, pdf_url, pdf_filename, body_text, 
                 extraction_method)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                circ['circular_number'],
                parsed['dor_number'],
                circ['date_of_issue'],
                circ['department'],
                circ['subject'],
                circ['meant_for'],
                pdf_url or "",
                pdf_filename,
                parsed['full_text'],
                extraction_method
            ))
            
            conn.commit()
            print(f"  ✓ Saved ({extraction_method}) - {len(body_text)} chars")
            stats['new'] += 1
        
        except Exception as e:
            print(f"  ❌ Database error: {e}")
            stats['failed'] += 1
        
        time.sleep(0.5)  # Rate limiting
    
    conn.close()
    
    # Summary
    print(f"\n{'='*70}")
    print(f"  SCRAPING COMPLETE")
    print(f"{'='*70}")
    print(f"New:     {stats['new']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Failed:  {stats['failed']}")
    print(f"Database: {DB_PATH}")
    print(f"{'='*70}\n")

def verify_data(limit: int = 5):
    """Display sample data to verify extraction quality."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT circular_number, date_of_issue, subject, 
               extraction_method, LENGTH(body_text) as text_len
        FROM circulars
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    
    print(f"\n{'='*70}")
    print(f"  SAMPLE DATA")
    print(f"{'='*70}\n")
    
    for row in cur.fetchall():
        print(f"Number: {row[0]}")
        print(f"Date: {row[1]}")
        print(f"Subject: {row[2][:60]}...")
        print(f"Method: {row[3]} | Text length: {row[4]} chars")
        print()
    
    # Statistics
    cur.execute("SELECT COUNT(*), extraction_method FROM circulars GROUP BY extraction_method")
    print("Extraction methods:")
    for count, method in cur.fetchall():
        print(f"  {method}: {count}")
    
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_data()
    else:
        # Process circulars
        process_circulars(limit=30)  # Start with 30 for testing
        
        # Show results
        verify_data()