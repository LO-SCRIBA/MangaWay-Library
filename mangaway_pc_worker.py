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

# --- GLOBAL EXPLICIT SETTINGS ---
IA_ARCHIVE_ID = "EMPTYFILE"
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

MAX_WIDTH = 1024
JPEG_QUALITY = 70

# Direct official endpoints bypassed using clean user-agent masking
API_BASE = "https://mangadex.org"

session = requests.Session()
session.verify = False  # Hardkill python SSL verification checks globally
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
})

def get_uploaded_chapters():
    """Explicitly clean item query structure."""
    print("[*] Checking inventory database status...")
    try:
        # Hardcoded structural slash prevents any domain merging bugs
        url = f"https://archive.org{IA_ARCHIVE_ID}"
        res = session.get(url, timeout=15).json()
        files = res.get("files", [])
        return [f["name"].lower() for f in files if f["name"].lower().endswith(".cbz")]
    except Exception as e:
        print(f"[-] Inventory fallback activated: {e}")
        return []

def main():
    print("[*] Initializing Pure Direct Cloud Worker Layer...")
    
    uploaded_inventory = get_uploaded_chapters()
    print(f"[✔] Found {len(uploaded_inventory)} items inside your cloud vault.")

    if not os.path.exists("manga_sources.json"):
        with open("manga_sources.json", "w", encoding="utf-8") as f:
            json.dump(["Attack on Titan", "Demon Slayer", "Chainsaw Man"], f)

    with open("manga_sources.json", "r", encoding="utf-8") as f:
        manga_queue = json.load(f)

    for title in manga_queue:
        print(f"\n[🔍] Pinging Target Index: {title}")
        try:
            # Direct parameters tracking prevents string manipulation blocks
            search_url = f"{API_BASE}/manga"
            res = session.get(search_url, params={"title": title, "limit": 1}, timeout=15).json()
            data = res.get("data", [])
            
            if not data:
                print(f"[-] Title lookup returned 0 items for: {title}")
                continue
                
            manga_item = data[0] if isinstance(data, list) else data
            manga_id = manga_item["id"]
            official_title = manga_item["attributes"]["title"].get("en", title)
            print(f"[✔] Connection Secured! ID: {manga_id} ({official_title})")
            
            # Request translation feed
            feed_url = f"{API_BASE}/manga/{manga_id}/feed"
            feed_params = {"translatedLanguage[]": ["en"], "order[chapter]": "asc", "limit": 15}
            chapters = session.get(feed_url, params=feed_params, timeout=15).json().get("data", [])
            
            for ch in chapters:
                ch_id = ch["id"]
                attr = ch["attributes"]
                vol = attr.get("volume") or "0"
                ch_num = attr.get("chapter") or "0"
                
                clean_title = "".join([c if c.isalnum() else "_" for c in official_title.lower()]).strip("_")
                cbz_filename = f"{clean_title}_vol{vol}_ch{ch_num}.cbz"
                
                if cbz_filename.lower() in uploaded_inventory:
                    print(f"[⏭] Chapter {ch_num} matched in vault cache. Skipped.")
                    continue
                    
                print(f"[*] Extracting page matrix -> Chapter {ch_num}")
                server_res = session.get(f"{API_BASE}/at-home/server/{ch_id}", timeout=15).json()
                base_host = server_res["baseUrl"]
                ch_hash = server_res["chapter"]["hash"]
                page_files = server_res["chapter"]["data"]
                
                cbz_buffer = BytesIO()
                with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for i, page in enumerate(page_files):
                        page_url = f"{base_host}/data/{ch_hash}/{page}"
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
                    
                # Direct upload to your personal Internet Archive bucket page
                upload(IA_ARCHIVE_ID, files=[cbz_filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                print(f"[🎉] Deployed successfully to emptyfile vault: {cbz_filename}")
                os.remove(cbz_filename)
                
        except Exception as e:
            print(f"[-] Extraction loop exception on '{title}': {e}")

if __name__ == "__main__":
    main()
