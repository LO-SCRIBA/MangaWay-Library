import os
import re
import zipfile
import requests
from internetarchive import get_item

# ==========================================
# CONFIGURAZIONE COORDINATE CLOUD & LOCALI
# ==========================================
# Il tuo server personale di destinazione per l'homebrew
MY_TARGET_ARCHIVE = "MANGAWAYIA" 
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

IA_CONFIG = {
    "s3": {
        "access": IA_ACCESS_KEY,
        "secret": IA_SECRET_KEY
    }
}

# La sorgente pubblica colossale dell'Internet Archive da saccheggiare
MEGA_SOURCE_ARCHIVE = "manga-2022-digital"

LISTA_MANGA_FILE = "lista_manga.txt"
OUTPUT_DIR = "mangaway_downloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# MAPPARE I FILE PRESENTI SUI VARI CLOUD
# ==========================================
def get_archive_files(archive_id):
    """Ritorna l'elenco dei file .cbz presenti in un qualsiasi item di Internet Archive."""
    print(f"[*] Scansione archivio {archive_id} su Internet Archive...")
    try:
        item = get_item(archive_id)
        cbz_files = {f["name"] for f in item.files if f["name"].endswith(".cbz")}
        print(f"[+] Trovati {len(cbz_files)} file .cbz pronti in {archive_id}.")
        return cbz_files
    except Exception as e:
        print(f"[!] Errore scansione archivio {archive_id}: {e}")
        return set()

def clean_name(name):
    """Rende il nome riconoscibile e pulito per il file system."""
    name = name.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9__\-]", "", name)

# ==========================================
# STRATEGIA 1: DOWNLOAD DIRETTO DA MEGA-SOURCE (IA)
# ==========================================
def download_from_mega_source(filename, final_path):
    """Scarica direttamente il file CBZ originale intonso dal mega-archivio di IA."""
    url = f"https://archive.org/download/{MEGA_SOURCE_ARCHIVE}/{filename}"
    try:
        res = requests.get(url, stream=True)
        if res.status_code == 200:
            with open(final_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        return False
    except Exception as e:
        print(f"        [!] Errore download da IA Source: {e}")
        return False

# ==========================================
# STRATEGIA 2: FALLBACK COMPLETO SU MANGADEX API
# ==========================================
def get_mangadex_chapters(manga_id):
    """Recupera l'intero feed dei capitoli da MangaDex tramite tuple native."""
    url = f"https://mangadex.org{manga_id}/feed"
    params = [
        ("limit", "100"),  # Aumentato a 100 per catturare i capitoli iniziali mancanti
        ("translatedLanguage[]", "en"),
        ("order[chapter]", "asc"),
        ("includeExternalUrl", "0")
    ]
    headers = {"User-Agent": "MangaWay3DSWorker/1.0"}
    try:
        res = requests.get(url, params=params, headers=headers)
        if res.status_code == 200:
            return res.json().get("data", [])
        return []
    except:
        return []

def download_from_mangadex(chapter_id, final_path):
    """Ricostruisce il CBZ raw binario direttamente dai server at-home di MangaDex."""
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

        with zipfile.ZipFile(final_path, "w", zipfile.ZIP_STORED) as cbz:
            for i, page in enumerate(pages):
                page_url = f"{base_url}/data/{hash_code}/{page}"
                img_res = requests.get(page_url, stream=True)
                if img_res.status_code == 200:
                    ext = page.split(".")[-1]
                    cbz.writestr(f"{i+1:03d}.{ext}", img_res.content)
        return True
    except:
        return False

# ==========================================
# CLOUD UPLOAD VERSO IL TUO SERVER (MANGAWAYIA)
# ==========================================
def upload_to_my_ia(file_path, file_name):
    """Carica il file finale pulito sul tuo archivio personale."""
    print(f"    [*] Uploading {file_name} sul tuo archivio cloud...")
    try:
        item = get_item(MY_TARGET_ARCHIVE)
        r = item.upload({file_name: file_path}, config=IA_CONFIG, verbose=False)
        return r.status_code == 200
    except Exception as e:
        print(f"    [!] Errore upload: {e}")
        return False

# ==========================================
# CORE CONTROLLER
# ==========================================
def main():
    if not os.path.exists(LISTA_MANGA_FILE):
        print(f"[!] Errore: Manca il file {LISTA_MANGA_FILE}")
        return

    # Sincronizza lo stato dei due archivi cloud
    my_remote_files = get_archive_files(MY_TARGET_ARCHIVE)
    mega_source_files = get_archive_files(MEGA_SOURCE_ARCHIVE)

    with open(LISTA_MANGA_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        if not line.strip() or "|" not in line: continue
        manga_name, manga_id = map(str.strip, line.split("|"))
        manga_slug = clean_name(manga_name)
        
        print(f"\n==================================================")
        print(f"[*] ANALISI SERIE: {manga_name}")
        print(f"==================================================\n")
        
        # Recupera il feed completo dei capitoli esistenti per questa serie
        chapters = get_mangadex_chapters(manga_id)
        if not chapters:
            print("    [!] Impossibile recuperare il feed dei capitoli. Salto la serie.")
            continue

        for ch in chapters:
            attrs = ch.get("attributes", {})
            vol = f"vol{attrs.get('volume')}" if attrs.get('volume') else "vol0"
            cap = f"ch{attrs.get('chapter')}" if attrs.get('chapter') else "ch0"
            
            cbz_name = f"{manga_slug}_{vol}_{cap}.cbz"
            local_path = os.path.join(OUTPUT_DIR, cbz_name)

            # 1. Se lo hai già nel tuo archivio, skippa a piè pari
            if cbz_name in my_remote_files:
                print(f"    [-] Presente sul tuo cloud: {cbz_name}")
                continue

            # 2. STRATEGIA PRINCIPALE: Prova a vedere se c'è nel mega database di Internet Archive
            # Cerca una corrispondenza parziale o esatta nel mega-dump (gestendo le variazioni di nome del dump)
            matching_source_file = None
            # Cerchiamo se nel dump esiste un file che contiene il nome del manga e il capitolo esatto
            cap_search_pattern = f"_{cap}.cbz"
            for f_source in mega_source_files:
                if manga_slug in f_source.lower() and cap_search_pattern in f_source.lower():
                    matching_source_file = f_source
                    break

            success = False
            if matching_source_file:
                print(f"    [🔍 STRATEGIA 1] Trovato nel Mega-Archivio ({MEGA_SOURCE_ARCHIVE}) come '{matching_source_file}'. Scarico diretto...")
                success = download_from_mega_source(matching_source_file, local_path)
            
            # 3. STRATEGIA FALLBACK: Se non c'è nel dump (es. capitoli da 1 a 149), attacca le API di MangaDex
            if not success:
                print(f"    [⚠️ STRATEGIA 2] Capitolo non trovato nel Mega-Archivio (Probabile capitolo iniziale mancante). Fallback su MangaDex...")
                success = download_from_mangadex(ch.get("id"), local_path)

            # 4. Se una delle due strategie ha funzionato, spingi il file nel tuo archivio
            if success:
                if upload_to_my_ia(local_path, cbz_name):
                    print(f"    [+] Sincronizzato con successo: {cbz_name}")
                    my_remote_files.add(cbz_name)
                else:
                    print(f"    [!] Fallito upload cloud di {cbz_name}")
                
                # Rimuovi il locale per risparmiare spazio sul PC
                if os.path.exists(local_path): os.remove(local_path)
            else:
                print(f"    [!] Errore critico: Impossibile scaricare {cbz_name} da nessuna sorgente.")

if __name__ == "__main__":
    main()
