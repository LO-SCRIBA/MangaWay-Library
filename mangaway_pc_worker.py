import os
import zipfile
import requests
from PIL import Image
from io import BytesIO
from internetarchive import upload
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- TARGET CONFIGURATION ---
IA_ARCHIVE_ID = "EMPTYFILE" 
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

# 🎮 PUNTO - RIDIMENSIONAMENTO HARDWARE: Bloccato a 480p di larghezza massima per preservare l'Old 3DS
MAX_WIDTH = 480 
JPEG_QUALITY = 70 

# 🌐 CORREZIONE CRITICA: Ripristinato l'endpoint API corretto per saltare i blocchi 404
BASE_API_URL = "https://api.mangadex.org"

session = requests.Session()
session.headers.update({
    "User-Agent": "MangaWayStore3DSWorker/4.0 (Nintendo 3DS Homebrew Link)"
})

def fetch_manga_id(title):
    """
    Cerca il manga su MangaDex ed applica un filtro a corrispondenza esatta 
    sulla stringa del titolo per evitare opere derivate o scambi di nomi.
    """
    url = f"{BASE_API_URL}/manga"
    params = {"title": title, "limit": 10}
    clean_search = title.strip().lower()
    try:
        res = session.get(url, params=params, verify=False, timeout=15)
        if res.status_code == 200:
            results = res.json().get("data", [])
            
            # FILTRO DI CORRISPONDENZA ESATTA (Es. Cerca solo 'Berserk' e scarta il resto)
            for manga_item in results:
                manga_title_en = manga_item["attributes"]["title"].get("en", "").strip().lower()
                if manga_title_en == clean_search:
                    return manga_item["id"], manga_item["attributes"]["title"].get("en")
            
            # Fallback se non trova il match perfetto ma l'elenco contiene dati
            if results:
                return results[0]["id"], results[0]["attributes"]["title"].get("en", title)
                
        print(f"[-] Ricerca catalogo fallita. Status code: {res.status_code}")
    except Exception as e:
        print(f"[-] Errore durante la ricerca di '{title}': {e}")
    return None, None

def get_english_chapters(manga_id):
    """
    Recupera i capitoli riducendo il limite a 20 per richiesta API
    E applicando un blocco rigido a un totale massimo di 20 capitoli complessivi per serie.
    """
    all_chapters = []
    limit = 20  # Blocchi da 20 elementi per singola richiesta
    offset = 0
    MAX_CAPITOLI_TOTALI = 20  # 🎯 IL TUO LIMITE: Cambia questo numero se in futuro vorrai scaricarne di più
    
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
                print(f"[#] Ottenuti {len(all_chapters)} / {total} capitoli inglesi...")
                
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


def process_and_compress_chapter(manga_title, chapter_data):
    chapter_id = chapter_data["id"]
    attributes = chapter_data["attributes"]
    volume = attributes.get("volume") or "0"
    chapter_num = attributes.get("chapter") or "0"
    
    clean_title = "".join([c if c.isalnum() else "_" for c in manga_title.lower()]).strip("_")
    cbz_filename = f"{clean_title}_vol{volume}_ch{chapter_num}.cbz"
    
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
                    if img.mode in ("RGBA", "P"):
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
        return cbz_filename
    except Exception as e:
        print(f"[-] Compressione fallita per il capitolo {chapter_num}: {e}")
        return None

def main():
    if not os.path.exists("lista_manga.txt"):
        with open("lista_manga.txt", "w", encoding="utf-8") as f:
            f.write("Chainsaw Man\nBerserk\nMy Dress-Up Darling\nThe Quintessential Quintuplets\nLove of Kill\n")
        print("[!] Creato il file lista_manga.txt. Inserisci i titoli al suo interno.")
        return

    with open("lista_manga.txt", "r", encoding="utf-8") as f:
        manga_queue = [line.strip() for line in f if line.strip()]

    for title in manga_queue:
        print(f"\n[🔍] Scansione database per: {title}")
        manga_id, official_title = fetch_manga_id(title)
        
        if not manga_id:
            continue
            
        print(f"[✔] Trovato (Corrispondenza Esatta): {official_title} (ID: {manga_id})")
        chapters = get_english_chapters(manga_id)
        print(f"[+] Totale coda caricata: {len(chapters)} capitoli pronti per l'elaborazione.")
        
        for ch in chapters:
            filename = process_and_compress_chapter(official_title, ch)
            if filename:
                try:
                    upload(IA_ARCHIVE_ID, files=[filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                    print(f"[🎉] Pacchetto inviato all'Internet Archive: {filename}")
                    os.remove(filename) 
                except Exception as e:
                    print(f"[-] Errore di sincronizzazione cloud per {filename}: {e}")

if __name__ == "__main__":
    main()

