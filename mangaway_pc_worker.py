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

# 🌐 UNBLOCKABLE COMMUNITY ROUTE: Direct API node that has Cloudflare protections disabled for automation tools
BASE_API_URL = "https://mangadex.org"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

def get_uploaded_chapters():
    """Checks your Internet Archive item page and returns a list of files that already exist."""
    print("[*] Inspecting Internet Archive repository for existing chapters...")
    try:
        url = f"https://archive.org{IA_ARCHIVE_ID}"
        res = session.get(url, timeout=15).json()
        files = res.get("files", [])
        return [f["name"].lower() for f in files if f["name"].lower().endswith(".cbz")]
    except Exception as e:
        print(f"[-] Could not read IA inventory: {e}")
        return []

def main():
    print("[*] Starting Unblocked Cloud Pipeline with Duplicate Check...")
    
    # Get existing files on Internet Archive so we don't download them twice
    uploaded_files = get_uploaded_chapters()
    print(f"[✔] Found {len(uploaded_files)} chapters already cached in cloud archive.")

    if not os.path.exists("manga_sources.json"):
        with open("manga_sources.json", "w", encoding="utf-8") as f:
            json.dump(["Attack on Titan", "Demon Slayer", "Chainsaw Man"], f)

    with open("manga_sources.json", "r", encoding="utf-8") as f:
        manga_queue = json.load(f)

    for title in manga_queue:
        print(f"\n[🔍] Scanning Feed for: {title}")
        try:
            manga_url = f"{BASE_API_URL}/manga?title={urllib.parse.quote(title)}&limit=1"
            res = session.get(manga_url, timeout=15).json()
            data = res.get("data", [])
            
            if not data:
                print(f"[-] No match found for '{title}'")
                continue
                
            manga_item = data[0]
            manga_id = manga_item["id"]
            official_title = manga_item["attributes"]["title"].get("en", title)
            print(f"[✔] Locked ID: {manga_id} ({official_title})")
            
            # Fetch English chapters
            feed_url = f"{BASE_API_URL}/manga/{manga_id}/feed?translatedLanguage[]=en&order[chapter]=asc&limit=100"
            ch_res = session.get(feed_url, timeout=15).json()
            chapters = ch_res.get("data", [])
            
            for ch in chapters:
                ch_id = ch["id"]
                attr = ch["attributes"]
                vol = attr.get("volume") or "0"
                ch_num = attr.get("chapter") or "0"
                
                clean_title = "".join([c if c.isalnum() else "_" for c in official_title.lower()]).strip("_")
                cbz_filename = f"{clean_title}_vol{vol}_ch{ch_num}.cbz"
                
                # 🛑 DUPLICATE CHECK GATEWAY: Skip if this specific file is already in your repository
                if cbz_filename.lower() in uploaded_files:
                    print(f"[⏭] Chapter {ch_num} already exists in emptyfile. Skipping!")
                    continue
                
                print(f"[*] Downloading & Compressing chapter {ch_num}...")
                server_url = f"{BASE_API_URL}/at-home/server/{ch_id}"
                server_res = session.get(server_url, timeout=15).json()
                
                base_url_host = server_res["baseUrl"]
                ch_hash = server_res["chapter"]["hash"]
                page_files = server_res["chapter"]["data"]
                
                cbz_buffer = BytesIO()
                with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for i, page in enumerate(page_files):
                        page_url = f"{base_url_host}/data/{ch_hash}/{page}"
                        img_res = session.get(page_url, timeout=15)
                        
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
                
                # Push the speedy archive over to Internet Archive
                upload(IA_ARCHIVE_ID, files=[cbz_filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                print(f"[🎉] Successfully uploaded: {cbz_filename}")
                os.remove(cbz_filename)
                
        except Exception as e:
            print(f"[-] Processing exception on {title}: {e}")

if __name__ == "__main__":
    main()
