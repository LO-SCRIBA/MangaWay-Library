import os
import json
import struct
import zipfile
import urllib.parse
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

GITHUB_USER = "LO-SCRIBA"
GITHUB_REPO = "MangaWay-Library"

CATALOG_FILE = "catalog.json"
COVERS_DIR = "covers"
COVER_SIZE = (128, 256) # 3DS native GPU dimensions
MAX_WIDTH = 1024        # 3DS RAM safe width
JPEG_QUALITY = 70       # Speedy download size

BASE_API_URL = "https://mangadex.org"

session = requests.Session()
session.headers.update({"User-Agent": "MangaWayCloudBot/5.0"})

def setup_environment():
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)

def save_as_t3x(img_path, t3x_path):
    try:
        with Image.open(img_path) as img:
            img = img.convert('RGBA').resize(COVER_SIZE, Image.Resampling.LANCZOS)
            width, height = img.size
            header = struct.pack('<4sHHHH', b'T3X1', width, height, 3, 1)
            pixel_data = bytearray()
            for y in range(height):
                for x in range(width):
                    r, g, b, a = img.getpixel((x, y))
                    pixel_data.extend([a, b, g, r])
            with open(t3x_path, 'wb') as f:
                f.write(header)
                f.write(pixel_data)
            return True
    except:
        return False

def fetch_manga_id(title):
    url = f"{BASE_API_URL}/manga"
    params = {"title": title, "limit": 1}
    try:
        res = session.get(url, params=params, verify=False, timeout=15).json()
        results = res.get("data", [])
        if results and len(results) > 0:
            return results[0]["id"], results[0]["attributes"]["title"].get("en", title)
    except:
        pass
    return None, None

def get_english_chapters(manga_id):
    url = f"{BASE_API_URL}/manga/{manga_id}/feed"
    params = {
        "translatedLanguage[]": ["en"],
        "order[chapter]": "asc",
        "limit": 15 # Set your cap here
    }
    try:
        res = session.get(url, params=params, verify=False, timeout=15).json()
        return res.get("data", [])
    except:
        return []

def main():
    print("[*] Launching 100% Serverless Cloud Pipeline...")
    setup_environment()
    
    if not os.path.exists("manga_sources.json"):
        # Uses your existing configuration layout to hold target names
        with open("manga_sources.json", "w") as f:
            json.dump(["Naruto", "Chainsaw Man", "Berserk"], f)

    with open("manga_sources.json", "r") as f:
        manga_queue = json.load(f)

    catalogo_finale = []

    for title in manga_queue:
        print(f"\n[🔍] Cloud Scanning for: {title}")
        manga_id, official_title = fetch_manga_id(title)
        
        if not manga_id:
            print(f"[-] '{title}' skipped.")
            continue
            
        print(f"[✔] Linked ID: {manga_id}")
        chapters = get_english_chapters(manga_id)
        
        for ch in chapters:
            chapter_id = ch["id"]
            attr = ch["attributes"]
            vol = attr.get("volume") or "0"
            ch_num = attr.get("chapter") or "0"
            
            clean_title = "".join([c if c.isalnum() else "_" for c in official_title.lower()]).strip("_")
            cbz_filename = f"{clean_title}_vol{vol}_ch{ch_num}.cbz"
            manga_id_str = f"{clean_title}_ch{ch_num}"
            
            print(f"[*] Compressing -> {cbz_filename}")
            
            try:
                server_res = session.get(f"{BASE_API_URL}/at-home/server/{chapter_id}", verify=False, timeout=15).json()
                base_url = server_res["baseUrl"]
                ch_hash = server_res["chapter"]["hash"]
                page_files = server_res["chapter"]["data"]
                
                # Build optimized CBZ in the cloud memory
                cbz_buffer = BytesIO()
                cover_saved = False
                local_cover_jpg = os.path.join(COVERS_DIR, f"{manga_id_str}.jpg")
                local_cover_t3x = os.path.join(COVERS_DIR, f"{manga_id_str}.t3x")

                with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for i, page in enumerate(page_files):
                        page_url = f"{base_url}/data/{ch_hash}/{page}"
                        img_res = session.get(page_url, verify=False, timeout=15)
                        
                        if img_res.status_code == 200:
                            img = Image.open(BytesIO(img_res.content))
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            
                            # Cache the first page to use as the menu thumbnail cover
                            if i == 0 and not cover_saved:
                                img.save(local_cover_jpg, "JPEG", quality=85)
                                save_as_t3x(local_cover_jpg, local_cover_t3x)
                                os.remove(local_cover_jpg) # Clean raw file
                                cover_saved = True

                            if img.width > MAX_WIDTH:
                                ratio = MAX_WIDTH / float(img.width)
                                img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.Resampling.LANCZOS)
                            
                            p_buf = BytesIO()
                            img.save(p_buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                            zip_file.writestr(f"{i:03d}.jpg", p_buf.getvalue())
                
                # Save out the package to pass to Internet Archive
                with open(cbz_filename, "wb") as f:
                    f.write(cbz_buffer.getvalue())
                
                # Push the speedy CBZ packet over to your archive
                upload(IA_ARCHIVE_ID, files=[cbz_filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                os.remove(cbz_filename) # Drop server file trace
                
                url_manga_grezzo = f"https://archive.org{IA_ARCHIVE_ID}/{cbz_filename}"
                url_manga_sicuro = urllib.parse.quote(url_manga_grezzo, safe=':/')
                url_cover_3ds = f"https://githubusercontent.com{GITHUB_USER}/{GITHUB_REPO}/main/covers/{manga_id_str}.t3x"

                catalogo_finale.append({
                    "titolo": f"{official_title} - Ch.{ch_num}",
                    "url_cbz": url_manga_sicuro,
                    "filename": cbz_filename,
                    "cover_url": url_cover_3ds
                })
                print(f"[🎉] Fully Synced to Cloud: {cbz_filename}")

            except Exception as e:
                print(f"[-] Skip chapter entry due to processing error: {e}")

    with open(CATALOG_FILE, "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print(f"\n[✔] Core Catalog updated. Process complete.")

if __name__ == "__main__":
    main()
