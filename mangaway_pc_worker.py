import os
import json
import zipfile
import requests
import urllib.parse
from PIL import Image
from io import BytesIO
from internetarchive import upload
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION HUB ---
IA_ARCHIVE_ID = "EMPTYFILE" 
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

MAX_WIDTH = 1024 
JPEG_QUALITY = 70 

# 🌐 OFFICIAL EMBEDDED MIRROR ROUTE: Bypasses the main web routing filter gates
BASE_API_URL = "https://mangadex.network"

session = requests.Session()
session.headers.update({"User-Agent": "MangaWayCloudUploader/7.0 (Nintendo 3DS Portal Platform)"})

def main():
    print("[*] Starting Hardware-Isolated Cloud Pipeline...")
    if not os.path.exists("manga_sources.json"):
        with open("manga_sources.json", "w") as f:
            json.dump(["Naruto", "Chainsaw Man", "Berserk"], f)

    with open("manga_sources.json", "r") as f:
        manga_queue = json.load(f)

    # Fallback to direct routing if mirror responds with empty streams
    endpoints = [BASE_API_URL, "https://mangadex.org"]

    for title in manga_queue:
        print(f"\n[🔍] Scanning Cloud Feed for: {title}")
        results = None
        official_title = title
        manga_id = None
        
        # Try routing through available API layers cleanly
        for base_url in endpoints:
            try:
                manga_url = f"{base_url}/manga?title={urllib.parse.quote(title)}&limit=1"
                res = session.get(manga_url, verify=False, timeout=15)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    if data:
                        manga_item = data[0] if isinstance(data, list) else data
                        manga_id = manga_item["id"]
                        official_title = manga_item["attributes"]["title"].get("en", title)
                        break
            except:
                continue
                
        if not manga_id:
            print(f"[-] Fetch failed for '{title}'. Gateway connection dropped.")
            continue
            
        print(f"[✔] Locked ID: {manga_id} ({official_title})")
        
        # Pull chapter lists safely
        chapters = []
        for base_url in endpoints:
            try:
                feed_url = f"{base_url}/manga/{manga_id}/feed?translatedLanguage[]=en&order[chapter]=asc&limit=15"
                res = session.get(feed_url, verify=False, timeout=15)
                if res.status_code == 200:
                    chapters = res.json().get("data", [])
                    if chapters:
                        break
            except:
                continue

        for ch in chapters:
            ch_id = ch["id"]
            attr = ch["attributes"]
            vol = attr.get("volume") or "0"
            ch_num = attr.get("chapter") or "0"
            
            clean_title = "".join([c if c.isalnum() else "_" for c in official_title.lower()]).strip("_")
            cbz_filename = f"{clean_title}_vol{vol}_ch{ch_num}.cbz"
            
            print(f"[*] Downloading & Compressing chapter {ch_num}...")
            
            try:
                # Get the page home storage parameters safely
                server_res = None
                for base_url in endpoints:
                    try:
                        server_url = f"{base_url}/at-home/server/{ch_id}"
                        res = session.get(server_url, verify=False, timeout=15)
                        if res.status_code == 200:
                            server_res = res.json()
                            break
                    except:
                        continue
                        
                if not server_res:
                    print(f"[-] Asset server unreachable for chapter {ch_num}")
                    continue

                base_url_host = server_res["baseUrl"]
                ch_hash = server_res["chapter"]["hash"]
                page_files = server_res["chapter"]["data"]
                
                cbz_buffer = BytesIO()
                with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for i, page in enumerate(page_files):
                        page_url = f"{base_url_host}/data/{ch_hash}/{page}"
                        img_res = session.get(page_url, verify=False, timeout=15)
                        
                        if img_res.status_code == 200:
                            img = Image.open(BytesIO(img_res.content))
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            if img.width > MAX_WIDTH:
                                ratio = MAX_WIDTH / float(img.width)
                                img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.Resampling.LANCZOS)
                            
                            p_buf = BytesIO()
                            img.save(p_buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                            zip_file.writestr(f"{i:03d}.jpg", page_buffer := p_buf.getvalue())
                
                with open(cbz_filename, "wb") as f:
                    f.write(cbz_buffer.getvalue())
                
                upload(IA_ARCHIVE_ID, files=[cbz_filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                print(f"[🎉] Successfully uploaded: {cbz_filename}")
                os.remove(cbz_filename)
            except Exception as e:
                print(f"[-] Processing exception on chapter {ch_num}: {e}")

if __name__ == "__main__":
    main()
