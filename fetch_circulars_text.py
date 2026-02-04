#old circulars last one was of 2021

import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import time

# --- Database Setup ---
engine = create_engine("sqlite:///database_circulars_text.db")
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Circular(Base):
    __tablename__ = "circulars"
    id = Column(Integer, primary_key=True)
    ref_no = Column(String)
    date = Column(String)
    department = Column(String)
    title = Column(String)
    url = Column(String, unique=True)
    full_text = Column(Text)

Base.metadata.create_all(engine)

# === Source URLs ===
INDEX_URL = "https://www.rbi.org.in/commonman/English/scripts/notification.aspx"
BASE_DOMAIN = "https://www.rbi.org.in"

# === Fetch Index Page ===
def fetch_index_html():
    print("Fetching RBI notification index page…")
    response = requests.get(INDEX_URL)
    response.raise_for_status()
    return response.text

# === Parse Index and Save Metadata ===
def parse_index(html, limit=70):
    soup = BeautifulSoup(html, "html.parser")
    session = Session()

    table = soup.find("table")
    if not table:
        print("No table found on index page!")
        return

    rows = table.find_all("tr")
    count = 0
    
    for row in rows[1:]:
        if count >= limit:
            break

        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        date = cols[0].text.strip()
        title_tag = cols[2].find("a")
        if not title_tag:
            continue

        title = title_tag.text.strip()
        href = title_tag.get("href").strip()

        # fix URL logic
        if href.startswith("http"):
            detail_url = href
        else:
            detail_url = BASE_DOMAIN + href

        # derive ref_no from URL or title
        ref_no = detail_url.split("/")[-1]

        exists = session.query(Circular).filter_by(url=detail_url).first()
        if exists:
            continue

        circ = Circular(
            ref_no=ref_no,
            date=date,
            department="",
            title=title,
            url=detail_url,
            full_text=""
        )
        session.add(circ)
        session.commit()

        print(f"[{count+1}] Saved metadata: {ref_no} - {title[:50]}")
        count += 1

    session.close()
    print(f"\nIndexed {count} circulars.")

# === Fetch Detail Page and Extract Text ===
def fetch_detail_text():
    session = Session()
    circulars = session.query(Circular).all()

    for circ in circulars:
        if circ.full_text:
            continue  # skip already scraped

        print(f"Fetching detail for: {circ.ref_no}")
        try:
            r = requests.get(circ.url)
            r.raise_for_status()
        except Exception as e:
            print("  ❌ Error fetching detail:", e)
            continue

        detail_soup = BeautifulSoup(r.text, "html.parser")

        # extract plain text
        full_text = detail_soup.get_text(separator="\n", strip=True)
        circ.full_text = full_text

        # simple department extraction (best effort)
        lines = full_text.split("\n")
        dept = ""
        for ln in lines[:10]:
            if ":" in ln and ln.isupper():
                dept = ln
                break
        circ.department = dept

        session.commit()
        time.sleep(0.3)  # avoid too many requests

    session.close()

if __name__ == "__main__":
    try:
        index_html = fetch_index_html()
        parse_index(index_html, limit=70)
        fetch_detail_text()
        print("\nDone — database populated.")
    except Exception as err:
        print("Error:", err)
