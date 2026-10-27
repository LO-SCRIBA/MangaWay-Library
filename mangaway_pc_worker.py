import os
import re
import requests
from internetarchive import get_item

# ==========================================
# CONFIGURAZIONE COORDINATE CLOUD & LOCALI
# ==========================================
IA_ARCHIVE_ID = "MANGAWAYIA"
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

IA_CONFIG = {
    "s3": {
        "access": IA_ACCESS_KEY,
        "secret": IA_SECRET_KEY
    }
}

LISTA_MANGA_FILE = "lista_manga.txt"
OUTPUT_DIR = "mangaway_downloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# SINCRO CONTROL: EVITIAMO DI RISCARICARE
# ==========================================
def get_remote_existing_files():
    """Interroga Internet Archive e scarica la lista dei file già presenti."""
    print(f"[*] Controllo file esistenti in remoto su {IA_ARCHIVE_ID}...")
    try:
        item = get_item(IA_ARCHIVE_ID)
        cbz_files = {f["name"] for f in item.files if f["name"].endswith(".cbz")}
        print(f"[+] Trovati {len(cbz_files)} file .cbz già archiviati.")
        return cbz_files
    except Exception as e:
        print(f"[!] Accesso a Internet Archive fallito ({e}). Procedo a coda vuota.")
        return set()

# ==========================================
# UTILITY FILENAME
# ==========================================
def clean_name(name):
    """Rende il nome riconoscibile e pulito per il file system."""
    name = name.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9__\-]", "", name)

# ==========================================
# FEED SCRAPER (Fix Parentesi Quadre)
# ==========================================
def get_chapters_feed(manga_id):
    """Scarica il feed dei capitoli inviando le tuple native senza alterare le parentesi."""
    url = f"https://mangadex.org{manga_id}/feed"
    params = [
        ("limit", "20"),
        ("translatedLanguage[]", "en"),
        ("order[chapter]", "asc"),
        ("includeExternalUrl", "0")
    ]
    headers = {"User-Agent": "MangaWay3DSWorker/1.0"}
    
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
    except Exception as e:
        print(f"    [!] Errore connessione feed: {e}")
        return []

# ==========================================
# DOWNLOAD BINARIO PURO (Nessuna Modifica)
# ==========================================
def download_pure_cbz(chapter_id, final_path):
    """
    Scarica il file CBZ originale senza toccarlo.
    Se MangaDex non espone direttamente il pacchetto compilato, 
    preleva lo stream binario grezzo delle tavole sequenziali dal server at-home.
    """
    # Nota: MangaDex non distribuisce direttamente file .cbz pronti dalle API pubbliche, 
    # ma espone l'endpoint "at-home" per aggregare i flussi immagine originali (senza compressione).
    # Questo modulo li unisce in un archivio raw binario non alterato.
    import zipfile
    url = f"https://mangadex.org{chapter_id}"
    try:
        res = requests.get(url)
        if res.status_code != 200: return False
        
        data = res.json()
        base_url = data.get("baseUrl")
        chapter_data = data.get("chapter", {})
        hash_code = chapter_data.get("hash")
        pages = chapter_data.get("data")
        
        if not base_url or not hash_code or not pages: return False

        # Creazione del contenitore puro (STORED = Nessun re-encoding, nessuna alterazione byte)
        with zipfile.ZipFile(final_path, "w", zipfile.ZIP_STORED) as cbz:
            for i, page in enumerate(pages):
                page_url = f"{base_url}/data/{hash_code}/{page}"
                img_res = requests.get(page_url, stream=True)
                if img_res.status_code == 200:
                    ext = page.split(".")[-1]
                    cbz.writestr(f"{i+1:03d}.{ext}", img_res.content)
        return True
    except Exception as e:
        print(f"        [!] Errore download binario: {e}")
        return False

# ==========================================
# CLOUD UPLOAD VIA S3 TOKENS
# ==========================================
def upload_to_ia(file_path, file_name):
    """Carica il file intonso direttamente su Internet Archive."""
    print(f"    [*] Uploading {file_name} in corso...")
    try:
        item = get_item(IA_ARCHIVE_ID)
        r = item.upload({file_name: file_path}, config=IA_CONFIG, verbose=False)
        return r.status_code == 200
    except Exception as e:
        print(f"    [!] Errore upload: {e}")
        return False

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    if not os.path.exists(LISTA_MANGA_FILE):
        print(f"[!] Errore: Manca il file {LISTA_MANGA_FILE}")
        return

    remote_files = get_remote_existing_files()

    with open(LISTA_MANGA_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        if not line.strip() or "|" not in line: continue
        
        manga_name, manga_id = map(str.strip, line.split("|"))
        manga_slug = clean_name(manga_name)
        
        print(f"\n[*] Controllo serie: {manga_name}")
        chapters = get_chapters_feed(manga_id)
        
        for ch in chapters:
            attrs = ch.get("attributes", {})
            vol = f"vol{attrs.get('volume')}" if attrs.get('volume') else "vol0"
            cap = f"ch{attrs.get('chapter')}" if attrs.get('chapter') else "ch0"
            
            # Formato nome super riconoscibile: nome_manga_vol0_ch1.cbz
            cbz_name = f"{manga_slug}_{vol}_{cap}.cbz"
            local_path = os.path.join(OUTPUT_DIR, cbz_name)

            if cbz_name in remote_files:
                print(f"    [-] Saltato: {cbz_name} già presente.")
                continue

            print(f"    [+] Nuovo capitolo trovato! Scarico in: {cbz_name}")
            if download_pure_cbz(ch.get("id"), local_path):
                if upload_to_ia(local_path, cbz_name):
                    print(f"    [+] Sincronizzato con successo: {cbz_name}")
                    remote_files.add(cbz_name)
                else:
                    print(f"    [!] Errore nel caricamento cloud di {cbz_name}")
            else:
                print(f"    [!] Errore nel download di {cbz_name}")
                if os.path.exists(local_path): os.remove(local_path)

if __name__ == "__main__":
    main()
