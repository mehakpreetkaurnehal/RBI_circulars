# import requests
# from bs4 import BeautifulSoup

# # URL to scrape
# # url = "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx?Id=13290"
# url = "https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx"
# # Send HTTP GET request
# response = requests.get(url)
# response.raise_for_status()  # will raise an error if bad response

# # Parse HTML
# soup = BeautifulSoup(response.text, "html.parser")

# # Extract the textual content
# text_content = soup.get_text(separator="\n")

# # Clean up whitespace
# lines = [line.strip() for line in text_content.splitlines() if line.strip()]
# clean_text = "\n".join(lines)

# # Save to .txt file
# with open("rbi_circular.txt", "w", encoding="utf-8") as f:
#     f.write(clean_text)

# print("Saved RBI Circular text to rbi_circular_13290.txt")




# import requests
# from bs4 import BeautifulSoup
# from urllib.parse import urljoin

# # The RBI index page with the table you want
# url = "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx"

# # GET request
# response = requests.get(url)
# response.raise_for_status()

# # Parse HTML
# soup = BeautifulSoup(response.text, "html.parser")

# # Select the specific table
# table = soup.find("table", {"class": "tablebg"})

# rows_data = []

# # Read table headers
# headers = [th.get_text(strip=True) for th in table.find_all("th")]
# rows_data.append("\t".join(headers))

# # Extract all rows
# for tr in table.find_all("tr")[1:]:
#     cols = tr.find_all(["td"])
#     if not cols:
#         continue
    
#     # For the first column (which contains a link), get full link and text
#     link_tag = cols[0].find("a")
#     if link_tag:
#         href = urljoin(url, link_tag.get("href"))
#         text = link_tag.get_text(" ", strip=True)
#         cols[0] = f"{text} ({href})"
#     else:
#         cols[0] = cols[0].get_text(strip=True)

#     # Extract text for remaining cells
#     row_text = [cols[i].get_text(strip=True) if i!=0 else cols[0] for i in range(len(cols))]
#     rows_data.append("\t".join(row_text))

# # Save to file
# with open("rbi_circulars_feb_2026.txt", "w", encoding="utf-8") as f:
#     for line in rows_data:
#         f.write(line + "\n")

# print("Table saved to rbi_circulars_feb_2026.txt")



# # Saves the metadata of the circulars need to add code for the ext. text
# issue is duplicate circulars

# import requests
# from bs4 import BeautifulSoup
# from urllib.parse import urljoin

# BASE_URL = "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx"

# HEADERS = {
#     "User-Agent": "Mozilla/5.0",
#     "Content-Type": "application/x-www-form-urlencoded"
# }

# START_YEAR = 2026
# END_YEAR = 2020
# MAX_CIRCULARS = 50 # can change the number of circulars 

# results = []

# def fetch_circulars(year, month):
#     payload = {
#         "hdnYear": str(year),
#         "hdnMonth": str(month)
#     }

#     response = requests.post(BASE_URL, data=payload, headers=HEADERS)
#     response.raise_for_status()

#     soup = BeautifulSoup(response.text, "html.parser")
#     table = soup.find("table", class_="tablebg")

#     if not table:
#         return []

#     rows = table.find_all("tr")[2:]  # skip title + header row
#     data = []

#     for row in rows:
#         cols = row.find_all("td")
#         if len(cols) < 4:
#             continue

#         link_tag = cols[0].find("a")
#         if not link_tag:
#             continue

#         circular_url = urljoin(BASE_URL, link_tag.get("href"))
#         reference_number = link_tag.get_text(" ", strip=True)
#         date = cols[1].get_text(strip=True)
#         department = cols[2].get_text(strip=True)
#         subject = cols[3].get_text(strip=True)

#         data.append({
#             "year": year,
#             "month": month,
#             "reference_number": reference_number,
#             "date": date,
#             "department": department,
#             "title": subject,
#             "url": circular_url
#         })

#     return data


# # -------- MAIN LOOP --------
# for year in range(START_YEAR, END_YEAR - 1, -1):
#     for month in range(12, 0, -1):
#         if len(results) >= MAX_CIRCULARS:
#             break

#         print(f"Fetching {year}-{month:02d}")
#         records = fetch_circulars(year, month)

#         for r in records:
#             results.append(r)
#             if len(results) >= MAX_CIRCULARS:
#                 break

#     if len(results) >= MAX_CIRCULARS:
#         break


# # -------- SAVE TO TXT --------
# with open("circular_links.txt", "w", encoding="utf-8") as f:
#     for i, r in enumerate(results, 1):
#         f.write(f"Circular {i}\n")
#         f.write(f"Year           : {r['year']}\n")
#         f.write(f"Month          : {r['month']}\n")
#         f.write(f"Reference No   : {r['reference_number']}\n")
#         f.write(f"Date           : {r['date']}\n")
#         f.write(f"Department     : {r['department']}\n")
#         f.write(f"Title          : {r['title']}\n")
#         f.write(f"URL            : {r['url']}\n")
#         f.write("-" * 80 + "\n")

# print(f"\nSaved {len(results)} circulars to circular_links.txt")



import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx"
HEADERS = {"User-Agent": "Mozilla/5.0"}

START_YEAR = 2026
END_YEAR = 2020
MAX_CIRCULARS = 50

seen = set()
results = []

for year in range(START_YEAR, END_YEAR - 1, -1):
    # Fetch year without month
    payload = {"hdnYear": str(year), "hdnMonth": "0"}
    res = requests.post(BASE_URL, data=payload, headers=HEADERS)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    table = soup.find("table", class_="tablebg")
    if table is None:
        continue

    for tr in table.find_all("tr")[2:]:
        cols = tr.find_all("td")
        if len(cols) < 4:
            continue

        link = cols[0].find("a")
        if not link:
            continue

        url = urljoin(BASE_URL, link["href"])
        ref = link.get_text(" ", strip=True)
        if url in seen:
            continue  # skip duplicates
        seen.add(url)

        results.append({
            "year": year,
            "reference_number": ref,
            "date": cols[1].get_text(strip=True),
            "department": cols[2].get_text(strip=True),
            "title": cols[3].get_text(strip=True),
            "url": url
        })
        if len(results) >= MAX_CIRCULARS:
            break

    if len(results) >= MAX_CIRCULARS:
        break

# Save to file
with open("unique_circulars.txt", "w", encoding="utf-8") as f:
    for i, r in enumerate(results, 1):
        f.write(f"Circular {i}\n")
        f.write(f"Year           : {r['year']}\n")
        f.write(f"Reference No   : {r['reference_number']}\n")
        f.write(f"Date           : {r['date']}\n")
        f.write(f"Department     : {r['department']}\n")
        f.write(f"Title          : {r['title']}\n")
        f.write(f"URL            : {r['url']}\n")
        f.write("-" * 80 + "\n")

print(f"Fetched {len(results)} unique circulars.")
