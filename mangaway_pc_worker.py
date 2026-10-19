import os
import zipfile
import requests
from PIL import Image
from io import BytesIO
from internetarchive import upload, get_item
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- TARGET CONFIGURATION ---
IA_ARCHIVE_ID = "EMPTYFILE" 
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

# 🎮 PUNTO - RIDIMENSIONAMENTO HARDWARE: Bloccato a 480p di larghezza massima per preservare l'Old 3DS
MAX_WIDTH = 480 
JPEG_QUALITY = 70 

# 🌐 ENDPOINT API MANGADEX
BASE_API_URL = "https://api.mangadex.org"

session = requests.Session()
session.headers.update({
    "User-Agent": "MangaWayStore3DSWorker/5.0 (Nintendo 3DS Homebrew Link)"
})

def get_uploaded_archive_files():
    """
    Recupera l'elenco dei file attualmente presenti su Internet Archive
    per consentire il controllo dei duplicati in tempo reale.
    """
    print("[*] Recupero elenco file esistenti da Internet Archive...")
    try:
        item = get_item(IA_ARCHIVE_ID)
        return {f['name'] for f in item.files}
    except Exception as e:
        print(f"[⚠️] Impossibile mappare l'archivio remoto ({e}). Procedo senza controllo storici.")
        return set()

def get_english_chapters(manga_id):
    """
    Recupera i capitoli tramite UUID statico riducendo il limite a 20 per richiesta API
    E applicando un blocco rigido a un totale massimo di 20 capitoli complessivi per serie.
    """
    all_chapters = []
    limit = 20  # Blocchi da 20 elementi per singola richiesta
    offset = 0
    MAX_CAPITOLI_TOTALI = 20  # 🎯 IL TUO LIMITE GIORNALIERO DI DOWNLOAD
    
    while True:
        # Costruiamo la stringa interamente a mano mantenendo le parentesi [] intatte e cruda
        query_string = (
            f"translatedLanguage[]=en"
            f"&limit={limit}"
            f"&offset={offset}"
            f"&order[chapter]=asc"
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
                    break  # Fine dei dati disponibili sul server
                
                all_chapters.extend(data)
                offset += limit
                print(f"[#] Trovati {len(all_chapters)} / {total} capitoli totali su MangaDex...")
                
                # --- BLOCCO DI SICUREZZA RIGIDO ---
                if len(all_chapters) >= MAX_CAPITOLI_TOTALI:
                    print(f"[⚠️] Raggiunto il limite massimo impostato di {MAX_CAPITOLI_TOTALI} capitoli. Taglio la coda.")
                    all_chapters = all_chapters[:MAX_CAPITOLI_TOTALI]  # Forza il taglio esatto a 20 elementi
                    break
                    
                if len(all_chapters) >= total:
                    break
            else:
                print(f"[-] Errore feed server (Status {res.status_code}).")
                break
        except Exception as e:
            print(f"[-] Eccezione durante l'estrazione: {e}")
            break
            
    return all_chapters

def generate_cbz_filename(manga_title, chapter_data):
    """
    Genera il nome standardizzato del file CBZ a partire dai metadati del capitolo.
    """
    attributes = chapter_data["attributes"]
    volume = attributes.get("volume") or "0"
    chapter_num = attributes.get("chapter") or "0"
    clean_title = "".join([c if c.isalnum() else "_" for c in manga_title.lower()]).strip("_")
    return f"{clean_title}_vol{volume}_ch{chapter_num}.cbz"

def process_and_compress_chapter(cbz_filename, chapter_data):
    """
    Scarica le pagine del capitolo, rimuove i canali alfa/trasparenza difettosi,
    ridimensiona a 480p e compila il file .cbz ottimizzato.
    """
    chapter_id = chapter_data["id"]
    print(f"[*] Ottimizzazione ed elaborazione pagine -> {cbz_filename}...")
    
    try:
        server_res = session.get(f"{BASE_API_URL}/at-home/server/{chapter_id}", verify=False, timeout=15).json()
        base_url = server_res["baseUrl"]
        chapter_hash = server_res["chapter"]["hash"]
        page_files = server_res["chapter"]["data"]
        
        cbz_buffer = BytesIO()
        with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, page in enumerate(page_files):
                page_url = f"{base_url}/data/{chapter_hash}/{page}"
                img_res = session.get(page_url, verify=False, timeout=15)
                
                if img_res.status_code == 200:
                    img = Image.open(BytesIO(img_res.content))
                    
                    # 🧼 RISOLUZIONE BUG IMAGEMODE (Scala di grigi, Trasparenze e canali Alpha corrotti)
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    
                    # 🎮 RIDIMENSIONAMENTO RIGIDO: Sotto i 480px di larghezza per la RAM del 3DS
                    if img.width > MAX_WIDTH:
                        ratio = MAX_WIDTH / float(img.width)
                        img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.Resampling.LANCZOS)
                    
                    page_buffer = BytesIO()
                    img.save(page_buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                    zip_file.writestr(f"{i:03d}.jpg", page_buffer.getvalue())
                    
        cbz_buffer.seek(0)
        with open(cbz_filename, "wb") as f:
            f.write(cbz_buffer.getvalue())
        return True
    except Exception as e:
        print(f"[-] Compressione fallita per il file {cbz_filename}: {e}")
        return False

def main():
    if not os.path.exists("lista_manga.txt"):
        with open("lista_manga.txt", "w", encoding="utf-8") as f:
            f.write("# Inserisci i manga nel formato: Nome Manga | ID-MangaDex\n")
            f.write("Berserk | e83c523e-51c8-4227-a9f1-a169b1bfb90e\n")
            f.write("Chainsaw Man | a77742b1-c6a6-4dc0-83ae-d369b50bc6e9\n")
            f.write("The Quintessential Quintuplets | b5b6631a-02f5-4cc1-94ef-d4cc56d4ba4e\n")
        print("[!] Creato il nuovo file lista_manga.txt basato su ID univoci. Configuralo prima di avviare.")
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
            else:
                print(f"[⚠️] Riga ignorata (Formato non valido, manca il carattere '|'): {line}")

    if not manga_queue:
        print("[-] Nessun manga valido inserito nella coda di download.")
        return

    # Mappa i file già esistenti su Internet Archive prima di iniziare la sessione
    existing_files = get_uploaded_archive_files()

    for official_title, manga_id in manga_queue:
        print(f"\n[🔍] Inizio elaborazione serie tramite ID: {official_title} ({manga_id})")
        
        chapters = get_english_chapters(manga_id)
        print(f"[+] Trovati {len(chapters)} capitoli pronti per il filtraggio storici.")
        
        for ch in chapters:
            filename = generate_cbz_filename(official_title, ch)
            
            # 🛑 CONTROLLO DUPLICATI: Se il file .cbz esiste già su IA, viene completamente saltato
            if filename in existing_files:
                print(f"[⏭] Capitolo già sincronizzato su Internet Archive. SALTO: {filename}")
                continue
                
            success = process_and_compress_chapter(filename, ch)
            if success:
                try:
                    upload(IA_ARCHIVE_ID, files=[filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                    print(f"[🎉] Pacchetto inviato con successo all'Internet Archive: {filename}")
                    os.remove(filename) 
                    existing_files.add(filename) # Aggiorna la cache locale per i cicli successivi
                except Exception as e:
                    print(f"[-] Errore di sincronizzazione cloud per {filename}: {e}")

if __name__ == "__main__":
    main()
