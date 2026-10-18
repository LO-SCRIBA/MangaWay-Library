import os
import json
import zipfile
import requests
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

# 🌐 CLOUDFLARE BYPASS LAYER: High-speed proxy that intercepts blocks on GitHub servers
BASE_API_URL = "https://corsproxy.io"

session = requests.Session()
# Setup pristine headers mimicking a clean developer fetch instance
session.headers.update({"User-Agent": "MangaWayCloudUploader/6.0 (Nintendo 3DS Portal)"})

def main():
    print("[*] Starting Unblocked Cloud Pipeline...")
    if not os.path.exists("manga_sources.json"):
        with open("manga_sources.json", "w") as f:
            json.dump(["Naruto", "Chainsaw Man", "Berserk"], f)

    with open("manga_sources.json", "r") as f:
        manga_queue = json.load(f)

    for title in manga_queue:
        print(f"\n[🔍] Scanning Mirror Feed: {title}")
        try:
            # Route requests through the open proxy to drop the line 1 column 1 crash
            manga_url = f"{BASE_API_URL}/manga?title={urllib.parse.quote(title)}&limit=1"
            res = session.get(manga_url, verify=False, timeout=20).json()
            results = res.get("data", [])
            if not results:
                print(f"[-] No hits found for {title}")
                continue
                
            manga_id = results[0]["id"]
            official_title = results[0]["attributes"]["title"].get("en", title)
            print(f"[✔] Locked ID: {manga_id} ({official_title})")
            
            # Fetch English chapters using proxy streams
            feed_url = f"{BASE_API_URL}/manga/{manga_id}/feed?translatedLanguage[]=en&order[chapter]=asc&limit=15"
            ch_res = session.get(feed_url, verify=False, timeout=20).json()
            chapters = ch_res.get("data", [])
            
            for ch in chapters:
                ch_id = ch["id"]
                attr = ch["attributes"]
                vol = attr.get("volume") or "0"
                ch_num = attr.get("chapter") or "0"
                
                clean_title = "".join([c if c.isalnum() else "_" for c in official_title.lower()]).strip("_")
                cbz_filename = f"{clean_title}_vol{vol}_ch{ch_num}.cbz"
                
                print(f"[*] Downloading & Compressing chapter {ch_num}...")
                server_url = f"{BASE_API_URL}/at-home/server/{ch_id}"
                server_res = session.get(server_url, verify=False, timeout=20).json()
                
                base_url = server_res["baseUrl"]
                ch_hash = server_res["chapter"]["hash"]
                page_files = server_res["chapter"]["data"]
                
                cbz_buffer = BytesIO()
                with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for i, page in enumerate(page_files):
                        # Image download via unblocked pipeline
                        page_url = f"https://corsproxy.io{base_url}/data/{ch_hash}/{page}"
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
                            zip_file.writestr(f"{i:03d}.jpg", p_buf.getvalue())
                
                with open(cbz_filename, "wb") as f:
                    f.write(cbz_buffer.getvalue())
                
                # Upload packet straight to your personal archive bucket
                upload(IA_ARCHIVE_ID, files=[cbz_filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                print(f"[🎉] Successfully uploaded: {cbz_filename}")
                os.remove(cbz_filename)
        except Exception as e:
            print(f"[-] Error processing {title}: {e}")

if __name__ == "__main__":
    main()
