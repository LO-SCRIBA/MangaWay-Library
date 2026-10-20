import os
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

# 🎮 RIDIMENSIONAMENTO HARDWARE CRITICO PER OLD 3DS
MAX_WIDTH = 480 
JPEG_QUALITY = 70 

BASE_API_URL = "https://mangadex.org"

session = requests.Session()
session.headers.update({
    "User-Agent": "MangaWayStore3DSWorker/5.5 (Nintendo 3DS Pure CBZ Engine)"
})

def get_uploaded_archive_files():
    print("[*] Recupero elenco file esistenti da Internet Archive...")
    try:
        item = get_item(IA_ARCHIVE_ID)
        return {f['name'] for f in item.files}
    except Exception as e:
        print(f"[⚠️] Impossibile mappare l'archivio remoto ({e}). Procedo senza controllo storici.")
        return set()

def get_english_chapters(manga_id):
    """Recupera i capitoli in ordine cronologico reale forzando l'ordinamento ascendente"""
    all_chapters = []
    limit = 20  
    offset = 0
    MAX_CAPITOLI_TOTALI = 20  # Forza il tetto massimo di 20 capitoli inediti al giorno
    
    while True:
        # Costruzione cruda della query per aggirare i WAF ed evitare payload vuoti
        query_string = (
            f"translatedLanguage[]=en"
            f"&limit={limit}"
            f"&offset={offset}"
            f"&order[chapter]=asc"  # 📈 ORDINE CRONOLOGICO CORRETTO (Dal capitolo 1 in poi)
            f"&contentRating[]=safe"
            f"&contentRating[]=suggestive"
            f"&contentRating[]=erotica"
            f"&contentRating[]=pornographic"
        )
        
        raw_url = f"{BASE_API_URL}/manga/{manga_id}/feed?{query_string}"
        
        try:
            res = session.get(raw_url, verify=False, timeout=15)
            if res.status_code == 200:
                res_json = res.json()
                data = res_json.get("data", [])
                total = res_json.get("total", 0)
                
                if not data:
                    break  
                
                all_chapters.extend(data)
                offset += limit
                print(f"[#] Estratti {len(all_chapters)} / {total} capitoli da MangaDex...")
                
                if len(all_chapters) >= MAX_CAPITOLI_TOTALI:
                    all_chapters = all_chapters[:MAX_CAPITOLI_TOTALI]
                    break
                    
                if len(all_chapters) >= total:
                    break
            else:
                print(f"[-] Errore server MangaDex: {res.status_code}")
                break
        except Exception as e:
            print(f"[-] Eccezione nel caricamento feed: {e}")
            break
            
    return all_chapters

def generate_cbz_filename(manga_title, chapter_data):
    attributes = chapter_data["attributes"]
    volume = attributes.get("volume") or "0"
    chapter_num = attributes.get("chapter") or "0"
    # Pulisce i caratteri speciali preservando la struttura del nome
    clean_title = "".join([c if c.isalnum() else "_" for c in manga_title.lower()]).strip("_")
    # Formato standardizzato tracciabile
    return f"{clean_title}_vol{volume}_ch{chapter_num}.cbz"

def process_and_compress_chapter(cbz_filename, chapter_data):
    """Scarica, ridimensiona e impacchetta in modalità STORED leggibile da 3dslibris"""
    chapter_id = chapter_data["id"]
    print(f"[*] Elaborazione e stritolamento hardware -> {cbz_filename}")
    
    try:
        server_res = session.get(f"{BASE_API_URL}/at-home/server/{chapter_id}", verify=False, timeout=15).json()
        base_url = server_res["baseUrl"]
        chapter_hash = server_res["chapter"]["hash"]
        page_files = server_res["chapter"]["data"]
        
        cbz_buffer = BytesIO()
        # 🎮 FIX CRITICO 3DSLIBRIS: Impostato a ZIP_STORED (Nessuna compressione complessa, solo archiviazione)
        with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_STORED) as zip_file:
            for i, page in enumerate(page_files):
                page_url = f"{base_url}/data/{chapter_hash}/{page}"
                img_res = session.get(page_url, verify=False, timeout=15)
                
                if img_res.status_code == 200:
                    img = Image.open(BytesIO(img_res.content))
                    
                    # Converte i canali alpha corrotti per evitare crash in Pillow
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    
                    # Ridimensionamento nativo a 480p di larghezza
                    if img.width > MAX_WIDTH:
                        ratio = MAX_WIDTH / float(img.width)
                        img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.Resampling.LANCZOS)
                    
                    page_buffer = BytesIO()
                    img.save(page_buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                    
                    # 🎮 FIX CRITICO ALFABETICO: Forzato il nome a 3 cifre (001.jpg, 002.jpg) per preservare l'ordine su 3DS
                    zip_file.writestr(f"{i+1:03d}.jpg", page_buffer.getvalue())
                    
        cbz_buffer.seek(0)
        with open(cbz_filename, "wb") as f:
            f.write(cbz_buffer.getvalue())
        return True
    except Exception as e:
        print(f"[-] Fallimento elaborazione capitolo per {cbz_filename}: {e}")
        return False

def main():
    if not os.path.exists("lista_manga.txt"):
        print("[-] File lista_manga.txt mancante. Genero file di esempio.")
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
        print("[-] Coda vuota. Inserisci i manga nel formato 'Nome | ID' in lista_manga.txt")
        return

    existing_files = get_uploaded_archive_files()

    for official_title, manga_id in manga_queue:
        print(f"\n[🔍] Sincronizzazione serie: {official_title} ({manga_id})")
        
        chapters = get_english_chapters(manga_id)
        print(f"[+] Ricevuti {len(chapters)} capitoli validi. Filtro storici in corso...")
        
        for ch in chapters:
            filename = generate_cbz_filename(official_title, ch)
            
            if filename in existing_files:
                print(f"[⏭] Già presente su Internet Archive. SALTO: {filename}")
                continue
                
            success = process_and_compress_chapter(filename, ch)
            if success:
                try:
                    upload(IA_ARCHIVE_ID, files=[filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                    print(f"[🎉] Inviato all'archivio MANGAWAY: {filename}")
                    os.remove(filename) 
                    existing_files.add(filename)
                except Exception as e:
                    print(f"[-] Errore di upload cloud per {filename}: {e}")

if __name__ == "__main__":
    main()

