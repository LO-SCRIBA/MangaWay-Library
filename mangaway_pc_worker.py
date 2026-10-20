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
IA_ARCHIVE_ID = "MANGAWAYIA"  # 🎯 Il tuo archivio cloud aggiornato
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

# 🎮 OTTIZZAZIONE HARDWARE PER 3DSLIBRIS E OLD 3DS
MAX_WIDTH = 480 
JPEG_QUALITY = 70 

BASE_API_URL = "https://api.mangadex.org"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Nintendo 3DS; U; ; en) Version/1.0.0.Homebrew",
    "Accept": "application/json"
})

def get_uploaded_archive_files():
    print(f"[*] Recupero elenco file esistenti da Internet Archive ({IA_ARCHIVE_ID})...")
    try:
        item = get_item(IA_ARCHIVE_ID)
        return {f['name'] for f in item.files}
    except Exception as e:
        print(f"[⚠️] Impossibile mappare l'archivio remoto ({e}). Procedo senza controllo storici.")
        return set()

def get_english_chapters(manga_id):
    """Recupera i capitoli gestendo i blocchi del WAF di MangaDex e i Rate Limit"""
    all_chapters = []
    limit = 20  
    offset = 0
    MAX_CAPITOLI_TOTALI = 20  # Quota giornaliera rigida per serie
    
    # 🌐 STRUTTURA PARAMETRI PULITA: Passaggio tramite tuple per evitare duplicazioni o encoding anomali delle parentesi []
    payload_params = [
        ("translatedLanguage[]", "en"),
        ("limit", str(limit)),
        ("order[chapter]", "asc"),
        ("contentRating[]", "safe"),
        ("contentRating[]", "suggestive"),
        ("contentRating[]", "erotica"),
        ("contentRating[]", "pornographic")
    ]
    
    feed_url = f"{BASE_API_URL}/manga/{manga_id}/feed"
    
    while True:
        # Aggiorna dinamicamente l'offset mantenendo i parametri puliti
        current_params = payload_params + [("offset", str(offset))]
        
        success = False
        retries = 3
        
        while retries > 0 and not success:
            try:
                # Ritardo di sicurezza preventivo anti-ban prima di toccare MangaDex
                time.sleep(1.2)
                res = session.get(feed_url, params=current_params, verify=False, timeout=15)
                
                if res.status_code == 200:
                    res_json = res.json()
                    data = res_json.get("data", [])
                    total = res_json.get("total", 0)
                    
                    if not data:
                        return all_chapters  # Fine dei capitoli disponibili
                        
                    all_chapters.extend(data)
                    offset += limit
                    print(f"[#] Estratti {len(all_chapters)} / {total} capitoli totali...")
                    success = True
                    
                    if len(all_chapters) >= MAX_CAPITOLI_TOTALI:
                        return all_chapters[:MAX_CAPITOLI_TOTALI]
                    if len(all_chapters) >= total:
                        return all_chapters
                        
                elif res.status_code == 429:
                    print("[⏳] Rate Limit di MangaDex raggiunto (429). Attesa forzata di 5 secondi...")
                    time.sleep(5.0)
                    retries -= 1
                else:
                    print(f"[-] Risposta anomala del server MangaDex (HTTP {res.status_code}). Riprovo...")
                    time.sleep(2.0)
                    retries -= 1
            except Exception as e:
                print(f"[⚠️] Connessione instabile o errore di parsing ({e}). Tentativi rimasti: {retries-1}")
                time.sleep(3.0)
                retries -= 1
                
        if not success:
            print("[-] Impossibile bypassare le restrizioni del server. Taglio la coda della serie attuale.")
            break
            
    return all_chapters

def generate_cbz_filename(manga_title, chapter_data):
    attributes = chapter_data["attributes"]
    volume = attributes.get("volume") or "0"
    chapter_num = attributes.get("chapter") or "0"
    clean_title = "".join([c if c.isalnum() else "_" for c in manga_title.lower()]).strip("_")
    return f"{clean_title}_vol{volume}_ch{chapter_num}.cbz"

def process_and_compress_chapter(cbz_filename, chapter_data):
    """Costruisce il file CBZ in modalità STORED (nessuna compressione) leggibile da 3dslibris"""
    chapter_id = chapter_data["id"]
    print(f"[*] Elaborazione e ridimensionamento immagini -> {cbz_filename}")
    
    try:
        # Richiesta dell'endpoint di hosting delle immagini
        time.sleep(1.0)
        server_res = session.get(f"{BASE_API_URL}/at-home/server/{chapter_id}", verify=False, timeout=15).json()
        base_url = server_res["baseUrl"]
        chapter_hash = server_res["chapter"]["hash"]
        page_files = server_res["chapter"]["data"]
        
        cbz_buffer = BytesIO()
        # 🎮 HARDWARE LOCK: ZIP_STORED per azzerare lo sforzo di decompressione della CPU del 3DS
        with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_STORED) as zip_file:
            for i, page in enumerate(page_files):
                page_url = f"{base_url}/data/{chapter_hash}/{page}"
                
                # Download della singola pagina con piccolo delay anti-ban
                time.sleep(0.3)
                img_res = session.get(page_url, verify=False, timeout=15)
                
                if img_res.status_code == 200:
                    img = Image.open(BytesIO(img_res.content))
                    
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    
                    # Ridimensionamento nativo rigido a 480p di larghezza massima per la VRAM
                    if img.width > MAX_WIDTH:
                        ratio = MAX_WIDTH / float(img.width)
                        img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.Resampling.LANCZOS)
                    
                    page_buffer = BytesIO()
                    img.save(page_buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                    
                    # 🎮 ALPHABETIC PADDING: Struttura a 3 cifre (001.jpg, 002.jpg) per bloccare i bug di lettura del 3DS
                    zip_file.writestr(f"{i+1:03d}.jpg", page_buffer.getvalue())
                    
        cbz_buffer.seek(0)
        with open(cbz_filename, "wb") as f:
            f.write(cbz_buffer.getvalue())
        return True
    except Exception as e:
        print(f"[-] Elaborazione hardware fallita per {cbz_filename}: {e}")
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
        print("[-] Lista vuota. Verifica la formattazione 'Nome | ID' in lista_manga.txt")
        return

    existing_files = get_uploaded_archive_files()

    for official_title, manga_id in manga_queue:
        print(f"\n[🔍] Sincronizzazione flussi serie: {official_title} ({manga_id})")
        
        chapters = get_english_chapters(manga_id)
        print(f"[+] Trovati {len(chapters)} capitoli cronologici pronti per l'elaborazione.")
        
        for ch in chapters:
            filename = generate_cbz_filename(official_title, ch)
            
            if filename in existing_files:
                print(f"[⏭] File già presente su Internet Archive. SALTO: {filename}")
                continue
                
            success = process_and_compress_chapter(filename, ch)
            if success:
                try:
                    upload(IA_ARCHIVE_ID, files=[filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                    print(f"[🎉] Sincronizzato con successo su archivio {IA_ARCHIVE_ID}: {filename}")
                    os.remove(filename) 
                    existing_files.add(filename)
                except Exception as e:
                    print(f"[-] Errore di sincronizzazione cloud per {filename}: {e}")

if __name__ == "__main__":
    main()
