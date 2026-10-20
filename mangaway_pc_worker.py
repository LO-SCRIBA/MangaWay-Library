import os
import zipfile
import requests
from PIL import Image
from io import BytesIO
from internetarchive import upload, get_item
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- TARGET CONFIGURATION ---
IA_ARCHIVE_ID = "MANGAWAYIA"  # 🎯 Aggiornato con il tuo nuovo identificativo cloud
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

# 🎮 OTTIMIZZAZIONE HARDWARE PER 3DSLIBRIS E OLD 3DS
MAX_WIDTH = 480 
JPEG_QUALITY = 70 

BASE_API_URL = "https://mangadex.org"

session = requests.Session()
session.headers.update({
    "User-Agent": "MangaWayStore3DSWorker/5.9 (Nintendo 3DS Pure CBZ Engine)"
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
    """Recupera i capitoli in ordine cronologico nativo usando la formattazione dei parametri ufficiale"""
    all_chapters = []
    limit = 20  
    offset = 0
    MAX_CAPITOLI_TOTALI = 20  # Scarica al massimo 20 capitoli inediti al giorno per serie
    
    feed_url = f"{BASE_API_URL}/manga/{manga_id}/feed"
    
    while True:
        payload_params = {
            "translatedLanguage[]": "en",
            "limit": limit,
            "offset": offset,
            "order[chapter]": "asc", # Ordine crescente dal capitolo 1 in poi
            "contentRating[]": ["safe", "suggestive", "erotica", "pornographic"]
        }
        
        try:
            res = session.get(feed_url, params=payload_params, verify=False, timeout=15)
            
            if res.status_code == 200:
                res_json = res.json()
                data = res_json.get("data", [])
                total = res_json.get("total", 0)
                
                if not data:
                    break  
                
                all_chapters.extend(data)
                offset += limit
                print(f"[#] Estratti {len(all_chapters)} / {total} capitoli totali...")
                
                if len(all_chapters) >= MAX_CAPITOLI_TOTALI:
                    all_chapters = all_chapters[:MAX_CAPITOLI_TOTALI]
                    break
                    
                if len(all_chapters) >= total:
                    break
            else:
                print(f"[-] Errore risposta feed server MangaDex (HTTP {res.status_code}). Interrompo.")
                break
        except Exception as e:
            print(f"[-] Eccezione o blocco nel parsing JSON: {e}")
            break
            
    return all_chapters

def generate_cbz_filename(manga_title, chapter_data):
    attributes = chapter_data["attributes"]
    volume = attributes.get("volume") or "0"
    chapter_num = attributes.get("chapter") or "0"
    clean_title = "".join([c if c.isalnum() else "_" for c in manga_title.lower()]).strip("_")
    return f"{clean_title}_vol{volume}_ch{chapter_num}.cbz"

def process_and_compress_chapter(cbz_filename, chapter_data):
    """Scarica e costruisce l'archivio privo di compressione apribile da 3dslibris"""
    chapter_id = chapter_data["id"]
    print(f"[*] Elaborazione e ridimensionamento immagini -> {cbz_filename}")
    
    try:
        server_res = session.get(f"{BASE_API_URL}/at-home/server/{chapter_id}", verify=False, timeout=15).json()
        base_url = server_res["baseUrl"]
        chapter_hash = server_res["chapter"]["hash"]
        page_files = server_res["chapter"]["data"]
        
        cbz_buffer = BytesIO()
        # 🎮 FORMATO STORED: Nessun algoritmo complesso, puro contenitore leggibile al volo dal processore del 3DS
        with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_STORED) as zip_file:
            for i, page in enumerate(page_files):
                page_url = f"{base_url}/data/{chapter_hash}/{page}"
                img_res = session.get(page_url, verify=False, timeout=15)
                
                if img_res.status_code == 200:
                    img = Image.open(BytesIO(img_res.content))
                    
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    
                    # Ridimensionamento nativo rigido a 480p di larghezza massima
                    if img.width > MAX_WIDTH:
                        ratio = MAX_WIDTH / float(img.width)
                        img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.Resampling.LANCZOS)
                    
                    page_buffer = BytesIO()
                    img.save(page_buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                    
                    # 🎮 INDEXING ADATTIVO: Nome forzato a 3 cifre (001.jpg, 002.jpg) per preservare la cronologia delle pagine
                    zip_file.writestr(f"{i+1:03d}.jpg", page_buffer.getvalue())
                    
        cbz_buffer.seek(0)
        with open(cbz_filename, "wb") as f:
            f.write(cbz_buffer.getvalue())
        return True
    except Exception as e:
        print(f"[-] Compressione hardware fallita per {cbz_filename}: {e}")
        return False

def main():
    if not os.path.exists("lista_manga.txt"):
        print("[-] Errore: manca il file lista_manga.txt.")
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
        print("[-] Nessun manga configurato. Verifica il formato 'Nome | ID' in lista_manga.txt")
        return

    existing_files = get_uploaded_archive_files()

    for official_title, manga_id in manga_queue:
        print(f"\n[🔍] Controllo flussi serie: {official_title} ({manga_id})")
        
        chapters = get_english_chapters(manga_id)
        print(f"[+] Trovati {len(chapters)} capitoli cronologici pronti per il filtraggio duplicati.")
        
        for ch in chapters:
            filename = generate_cbz_filename(official_title, ch)
            
            if filename in existing_files:
                print(f"[⏭] File già presente su Internet Archive. SALTO COMPLETO: {filename}")
                continue
                
            success = process_and_compress_chapter(filename, ch)
            if success:
                try:
                    upload(IA_ARCHIVE_ID, files=[filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                    print(f"[🎉] Upload completato con successo su archivio {IA_ARCHIVE_ID}: {filename}")
                    os.remove(filename) 
                    existing_files.add(filename)
                except Exception as e:
                    print(f"[-] Errore di sincronizzazione cloud per {filename}: {e}")

if __name__ == "__main__":
    main()
