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

# 🌐 CLEAN REVERSE PROXY COUPLING: Separates the gate endpoint from the nested query formatting
PROXY_GATE = "https://allorigins.win"
MANGADEX_API = "https://mangadex.org"

session = requests.Session()
session.headers.update({"User-Agent": "MangaWayCloudUploader/8.0 (Nintendo 3DS Homebrew Ecosystem)"})

def main():
    print("[*] Starting Proxy-Isolated Cloud Pipeline...")
    if not os.path.exists("manga_sources.json"):
        with open("manga_sources.json", "w") as f:
            json.dump(["Naruto", "Chainsaw Man", "Berserk"], f)

    with open("manga_sources.json", "r") as f:
        manga_queue = json.load(f)

    for title in manga_queue:
        print(f"\n[🔍] Tunneling request for: {title}")
        try:
            # 🎯 FIXED: Build clean decoupled URL parameters
            raw_url = f"{MANGADEX_API}/manga?title={urllib.parse.quote(title)}&limit=1"
            proxied_url = f"{PROXY_GATE}{urllib.parse.quote(raw_url)}"
            
            res = session.get(proxied_url, verify=False, timeout=25)
            if res.status_code == 200:
                data = res.json().get("data", [])
                if data and len(data) > 0:
                    # 🎯 FIXED: Safely fetch the first item element in the data index list
                    manga_item = data[0]
                    manga_id = manga_item["id"]
                    official_title = manga_item["attributes"]["title"].get("en", title)
                else:
                    print(f"[-] No match found for '{title}' over proxy.")
                    continue
            else:
                print(f"[-] Proxy returned error code: {res.status_code}")
                continue
                
            print(f"[✔] Tunnel Locked ID: {manga_id} ({official_title})")
            
            # Fetch English chapters via proxy tunnels
            raw_feed_url = f"{MANGADEX_API}/manga/{manga_id}/feed?translatedLanguage[]=en&order[chapter]=asc&limit=15"
            proxied_feed_url = f"{PROXY_GATE}{urllib.parse.quote(raw_feed_url)}"
            
            ch_res = session.get(proxied_feed_url, verify=False, timeout=25).json()
            chapters = ch_res.get("data", [])
            
            for ch in chapters:
                ch_id = ch["id"]
                attr = ch["attributes"]
                vol = attr.get("volume") or "0"
                ch_num = attr.get("chapter") or "0"
                
                clean_title = "".join([c if c.isalnum() else "_" for c in official_title.lower()]).strip("_")
                cbz_filename = f"{clean_title}_vol{vol}_ch{ch_num}.cbz"
                
                print(f"[*] Downloading & Compressing chapter {ch_num}...")
                
                raw_server_url = f"{MANGADEX_API}/at-home/server/{ch_id}"
                proxied_server_url = f"{PROXY_GATE}{urllib.parse.quote(raw_server_url)}"
                server_res = session.get(proxied_server_url, verify=False, timeout=25).json()
                
                base_url_host = server_res["baseUrl"]
                ch_hash = server_res["chapter"]["hash"]
                page_files = server_res["chapter"]["data"]
                
                cbz_buffer = BytesIO()
                with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for i, page in enumerate(page_files):
                        page_url = f"{base_url_host}/data/{ch_hash}/{page}"
                        img_res = session.get(page_url, verify=False, timeout=20)
                        
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
                
                upload(IA_ARCHIVE_ID, files=[cbz_filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                print(f"[🎉] Successfully uploaded to Internet Archive: {cbz_filename}")
                os.remove(cbz_filename)
        except Exception as e:
            print(f"[-] Processing exception on {title}: {e}")

if __name__ == "__main__":
    main()
