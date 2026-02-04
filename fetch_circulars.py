import os
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Database (SQLite) Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Circular(Base):
    __tablename__ = "circulars"
    id = Column(Integer, primary_key=True)
    date = Column(String)
    title = Column(String)
    url = Column(String, unique=True)
    local_file = Column(String)

Base.metadata.create_all(bind=engine)

# --- URL to Fetch RBI Circulars ---
RBI_URL = "https://www.rbi.org.in/commonman/English/scripts/notification.aspx"

def fetch_page():
    """
    Fetches the RBI notification page.
    """
    resp = requests.get(RBI_URL)
    if resp.status_code == 200:
        return resp.text
    print("Error fetching RBI page:", resp.status_code)
    return ""

def parse_and_save(html, limit=70):
    """
    Parses the RBI page for circulars and saves to DB.
    """
    soup = BeautifulSoup(html, "html.parser")
    session = SessionLocal()
    count = 0

    # The list of notifications are in <table> rows
    table = soup.find("table")
    if not table:
        print("No table found on the page.")
        return

    rows = table.find_all("tr")
    for row in rows[1:]:
        if count >= limit:
            break

        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        date = cols[0].text.strip()
        link_tag = cols[2].find("a")
        if not link_tag:
            continue

        title = link_tag.text.strip()
        href = link_tag.get("href")
        url = href if href.startswith("http") else ("https://www.rbi.org.in" + href)

        # Avoid duplicates
        exists = session.query(Circular).filter_by(url=url).first()
        if exists:
            continue

        circular = Circular(date=date, title=title, url=url)
        session.add(circular)
        session.commit()
        count += 1
        print(f"[{count}] Saved: {title[:60]}")

    session.close()
    print(f"\nTotal saved: {count}")

def download_files():
    """
    Downloads linked files for each saved circular.
    """
    session = SessionLocal()
    os.makedirs("pdfs", exist_ok=True)

    circulars = session.query(Circular).all()
    for circ in circulars:
        filename = os.path.join("pdfs", circ.url.split("/")[-1].split("?")[0])
        if not os.path.exists(filename):
            try:
                r = requests.get(circ.url)
                with open(filename, "wb") as f:
                    f.write(r.content)
                circ.local_file = filename
                session.commit()
                print("Downloaded:", filename)
            except Exception as e:
                print("Error downloading:", circ.url, e)
    session.close()

if __name__ == "__main__":
    html = fetch_page()
    if html:
        parse_and_save(html, limit=70)
        download_files()
        print("\nCompleted scraping and storing 70 circulars.")
    else:
        print("No HTML retrieved.")
