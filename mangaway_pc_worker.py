import os
import time
import zipfile
import requests
from PIL import Image
from io import BytesIO
from internetarchive import upload, get_item
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- TARGET CONFIGURATION ---
IA_ARCHIVE_ID = "MANGAWAYIA"  
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

# 🎮 HARDWARE COMPATIBILITY SCALING FOR 3DSLIBRIS
MAX_WIDTH = 480 
JPEG_QUALITY = 70 

# Direct endpoint and official backup proxy
PRIMARY_API = "https://mangadex.org"
PROXY_API = "https://mangadex.network" # Fallback proxy layer

session = requests.Session()

def get_uploaded_archive_files():
    print(f"[*] Recupero elenco file esistenti da Internet Archive ({IA_ARCHIVE_ID})...")
    try:
        item = get_item(IA_ARCHIVE_ID)
        return {f['name'] for f in item.files}
    except Exception as e:
        print(f"[⚠️] Impossibile mappare l'archivio remoto ({e}). Procedo senza controllo storici.")
        return set()

def get_english_chapters(manga_id):
    """Fetches chapters by cycling between official endpoints and proxy servers if GitHub is blocked"""
    all_chapters = []
    limit = 20  
    offset = 0
    MAX_CAPITOLI_TOTALI = 20  
    
    # Clean real browser headers to look less like an automated python runner
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://mangadex.org",
        "Referer": "https://mangadex.org"
    }

    while True:
        raw_query = (
            f"translatedLanguage[]=en"
            f"&limit={limit}"
            f"&offset={offset}"
            f"&order[volume]=asc"
            f"&order[chapter]=asc"
            f"&contentRating[]=safe"
            f"&contentRating[]=suggestive"
            f"&contentRating[]=erotica"
            f"&contentRating[]=pornographic"
        )
        
        # Test primary server, switch to proxy mirror dynamically if blocked
        endpoints = [PRIMARY_API, PROXY_API]
        success = False
        
        for base_url in endpoints:
            feed_url = f"{base_url}/manga/{manga_id}/feed?{raw_query}"
            retries = 2
            
            while retries > 0 and not success:
                try:
                    time.sleep(2.0) # Polite delay
                    res = session.get(feed_url, headers=browser_headers, verify=False, timeout=15)
                    
                    if res.status_code == 200:
                        res_json = res.json()
                        data = res_json.get("data", [])
                        total = res_json.get("total", 0)
                        
                        all_chapters.extend(data)
                        offset += limit
                        print(f"[#] Estratti {len(all_chapters)} / {total} capitoli totali...")
                        success = True
                        
                        if not data or len(all_chapters) >= MAX_CAPITOLI_TOTALI or len(all_chapters) >= total:
                            return all_chapters[:MAX_CAPITOLI_TOTALI]
                            
                    elif res.status_code == 429:
                        time.sleep(5.0)
                        retries -= 1
                    else:
                        retries -= 1
                except Exception:
                    retries -= 1
                    
            if success:
                break # Succeeded on this endpoint layer, move to next batch offset
                
        if not success:
            print("[-] Both primary database and proxy network endpoints are actively blocking this node instance.")
            break
            
    return all_chapters

def generate_cbz_filename(manga_title, chapter_data):
    attributes = chapter_data["attributes"]
    volume = attributes.get("volume") or "0"
    chapter_num = attributes.get("chapter") or "0"
    clean_title = "".join([c if c.isalnum() else "_" for c in manga_title.lower()]).strip("_")
    return f"{clean_title}_vol{volume}_ch{chapter_num}.cbz"

def process_and_compress_chapter(cbz_filename, chapter_data):
    chapter_id = chapter_data["id"]
    print(f"[*] Ottimizzazione fisica su disco -> {cbz_filename}")
    
    # Emulate real image reader browser request
    img_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://mangadex.org"
    }
    
    try:
        time.sleep(1.5)
        # Try primary endpoint for image mapping server lookup
        try:
            server_res = session.get(f"{PRIMARY_API}/at-home/server/{chapter_id}", headers=img_headers, verify=False, timeout=15).json()
        except:
            # Proxy lookup fallback
            server_res = session.get(f"{PROXY_API}/at-home/server/{chapter_id}", headers=img_headers, verify=False, timeout=15).json()
            
        base_url = server_res["baseUrl"]
        chapter_hash = server_res["chapter"]["hash"]
        page_files = server_res["chapter"]["data"]
        
        with zipfile.ZipFile(cbz_filename, 'w', zipfile.ZIP_STORED) as zip_file:
            for i, page in enumerate(page_files):
                page_url = f"{base_url}/data/{chapter_hash}/{page}"
                
                time.sleep(0.4)
                img_res = session.get(page_url, headers=img_headers, verify=False, timeout=15)
                
                if img_res.status_code == 200:
                    img = Image.open(BytesIO(img_res.content))
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    
                    if img.width > MAX_WIDTH:
                        ratio = MAX_WIDTH / float(img.width)
                        img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.Resampling.LANCZOS)
                    
                    page_buffer = BytesIO()
                    img.save(page_buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                    zip_file.writestr(f"{i+1:03d}.jpg", page_buffer.getvalue())
                    
        if os.path.exists(cbz_filename) and os.path.getsize(cbz_filename) > 0:
            return True
        return False
    except Exception as e:
        print(f"[-] Compressione hardware fallita per {cbz_filename}: {e}")
        if os.path.exists(cbz_filename):
            os.remove(cbz_filename)
        return False

def main():
    if not os.path.exists("lista_manga.txt"):
        print("[-] Errore: file lista_manga.txt non trovato.")
        return

    manga_queue = []
    with open("lista_manga.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                parts = line.split("|")
                manga_queue.append((parts[0].strip(), parts[1].strip()))

    if not manga_queue:
        print("[-] Nessun manga configurato in lista_manga.txt.")
        return

    existing_files = get_uploaded_archive_files()

    for official_title, manga_id in manga_queue:
        print(f"\n[🔍] Sincronizzazione flussi serie: {official_title} ({manga_id})")
        
        chapters = get_english_chapters(manga_id)
        print(f"[+] Trovati {len(chapters)} capitoli cronologici pronti per l'elaborazione.")
        
        for ch in chapters:
            filename = generate_cbz_filename(official_title, ch)
            
            if filename in existing_files:
                print(f"[⏭] File già presente nel cloud. SALTO: {filename}")
                continue
                
            success = process_and_compress_chapter(filename, ch)
            if success:
                try:
                    upload(IA_ARCHIVE_ID, files=[filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                    print(f"[🎉] Sincronizzato su archivio {IA_ARCHIVE_ID}: {filename}")
                    os.remove(filename) 
                    existing_files.add(filename)
                except Exception as e:
                    print(f"[-] Errore di sincronizzazione cloud per {filename}: {e}")

if __name__ == "__main__":
    main()
