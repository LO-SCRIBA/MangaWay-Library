import os
import sys
import time
import zipfile
import requests
from internetarchive import upload, get_item, download
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IA_ARCHIVE_ID = "MANGAWAYIA"
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

# 🌐 USIAMO LA CORRETTA STRUTTURA DEL REINDIRIZZAMENTO API
BASE_API_URL = "https://mangadex.org"
INDEX_FILE_NAME = "last_processed_index.txt"

os.environ["IA_ACCESS_KEY"] = IA_ACCESS_KEY
os.environ["IA_SECRET_KEY"] = IA_SECRET_KEY

session = requests.Session()
# 📑 INTEGRAZIONE REQUISITI BROWSER: Maschera completamente le richieste simulate provenienti dai nodi Cloud di GitHub
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://mangadex.org",
    "Referer": "https://mangadex.org"
})

def get_uploaded_archive_files():
    print(f"[*] Fetching remote file list from Internet Archive ({IA_ARCHIVE_ID})...", flush=True)
    try:
        catalog_url = f"https://archive.org/{IA_ARCHIVE_ID}"
        res = session.get(catalog_url, timeout=15)
        if res.status_code == 200:
            files_data = res.json().get("files", [])
            return {f['name'] for f in files_data}
    except Exception as e:
        print(f"[⚠️] Unable to map remote archive via API ({e}). Trying backup method...", flush=True)
        
    try:
        item = get_item(IA_ARCHIVE_ID)
        return {f['name'] for f in item.files}
    except Exception as e:
        print(f"[⚠️] Internet Archive connection failed entirely ({e}). Proceeding without history check.", flush=True)
        return set()

def get_last_processed_index():
    print(f"[*] Checking for progress state file ({INDEX_FILE_NAME}) on cloud...", flush=True)
    if os.path.exists(INDEX_FILE_NAME):
        os.remove(INDEX_FILE_NAME)
        
    try:
        index_url = f"https://archive.org/{IA_ARCHIVE_ID}/{INDEX_FILE_NAME}"
        res = session.get(index_url, timeout=10)
        if res.status_code == 200:
            index = int(res.text.strip())
            print(f"[+] Resuming from manga index: {index}", flush=True)
            return index
    except Exception as e:
        print(f"[⚠️] HTTP state check omitted ({e}). Trying fallback download...", flush=True)

    try:
        download(IA_ARCHIVE_ID, files=[INDEX_FILE_NAME], destdir=".", ignore_errors=True, timeout=10)
        if os.path.exists(INDEX_FILE_NAME):
            with open(INDEX_FILE_NAME, "r", encoding="utf-8") as f:
                index = int(f.read().strip())
                print(f"[+] Resuming from manga index via fallback: {index}", flush=True)
                return index
    except Exception as e:
        print(f"[⚠️] No progress state found or error reading it ({e}). Starting from 0.", flush=True)
    return 0

def save_last_processed_index(index):
    print(f"[*] Saving current progress index ({index}) to cloud...", flush=True)
    with open(INDEX_FILE_NAME, "w", encoding="utf-8") as f:
        f.write(str(index))
    try:
        upload(IA_ARCHIVE_ID, files=[INDEX_FILE_NAME], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False, retries=3)
        if os.path.exists(INDEX_FILE_NAME):
            os.remove(INDEX_FILE_NAME)
    except Exception as e:
        print(f"[-] Failed to upload state file to cloud: {e}", flush=True)

def get_english_chapters(manga_id):
    all_chapters = []
    limit = 100
    offset = 0
    
    # Costruiamo i dizionari nativi dei parametri per evitare incompatibilità strutturali
    payload_params = {
        "translatedLanguage[]": "en",
        "limit": str(limit),
        "offset": str(offset),
        "order[chapter]": "asc",
        "contentRating[]": ["safe", "suggestive", "erotica", "pornographic"]
    }
    
    raw_url = f"{BASE_API_URL}/manga/{manga_id}/feed"
    
    while True:
        try:
            time.sleep(1.0) # Ritardo di sicurezza aumentato per eludere i controlli anti-bot automatizzati
            payload_params["offset"] = str(offset)
            
            res = session.get(raw_url, params=payload_params, verify=False, timeout=15)
            
            # Se l'API principale fallisce o è bloccata, proviamo a usare lo specchio alternativo proxy
            if res.status_code != 200:
                print(f"[⚠️] Primary API blocked (Status {res.status_code}). Triggering CORS Proxy fallback...", flush=True)
                backup_url = f"https://allorigins.win{requests.utils.quote(raw_url + '?translatedLanguage[]=en&limit=' + str(limit) + '&offset=' + str(offset) + '&order[chapter]=asc&contentRating[]=safe&contentRating[]=suggestive&contentRating[]=erotica&contentRating[]=pornographic')}"
                res = requests.get(backup_url, timeout=20)
                if res.status_code == 200:
                    res_json = res.json()
                    import json
                    res_data = json.loads(res_json["contents"])
                else:
                    break
            else:
                res_data = res.json()
                
            data = res_data.get("data", [])
            total = res_data.get("total", 0)
            
            if not data:
                break
            
            all_chapters.extend(data)
            offset += limit
            
            if len(all_chapters) >= total:
                break
        except Exception as e:
            print(f"[-] Exception during extraction: {e}", flush=True)
            break
            
    return all_chapters

def download_raw_cbz(cbz_filename, chapter_id):
    try:
        time.sleep(0.5)
        res = session.get(f"{BASE_API_URL}/at-home/server/{chapter_id}", verify=False, timeout=15)
        if res.status_code != 200:
            return False
            
        server_res = res.json()
        base_url = server_res["baseUrl"]
        chapter_hash = server_res["chapter"]["hash"]
        page_files = server_res["chapter"]["data"]
        
        with zipfile.ZipFile(cbz_filename, 'w', zipfile.ZIP_STORED) as zip_file:
            for i, page in enumerate(page_files):
                page_url = f"{base_url}/data/{chapter_hash}/{page}"
                
                time.sleep(0.3)
                img_res = session.get(page_url, verify=False, timeout=15)
                
                if img_res.status_code == 200:
                    zip_file.writestr(f"{i+1:03d}.jpg", img_res.content)
                    
        return os.path.exists(cbz_filename) and os.path.getsize(cbz_filename) > 0
    except Exception as e:
        print(f"[-] Download failed for chapter {cbz_filename}: {e}", flush=True)
        if os.path.exists(cbz_filename):
            os.remove(cbz_filename)
        return False

def main():
    print("[*] Launching MangaWay Cloud Sync...", flush=True)
    if not os.path.exists("lista_manga.txt"):
        print("[-] Error: file lista_manga.txt not found.", flush=True)
        return

    manga_queue = []
    with open("lista_manga.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.replace("\r", "").replace("\n", "").strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                parts = line.split("|")
                manga_queue.append((parts[0].strip(), parts[1].strip()))

    if not manga_queue:
        print("[-] No manga configured inside lista_manga.txt", flush=True)
        return

    start_index = get_last_processed_index()
    if start_index >= len(manga_queue):
        print("[*] Reached the end of the manga list in previous runs. Resetting index to 0.", flush=True)
        start_index = 0

    end_index = start_index + 20
    chunk_to_process = manga_queue[start_index:end_index]
    
    print(f"[*] Processing chunk from index {start_index} to {min(end_index, len(manga_queue))} (Total items: {len(chunk_to_process)})", flush=True)

    existing_files = get_uploaded_archive_files()

    for official_title, manga_id in chunk_to_process:
        print(f"\n[🔍] Scanning database for: {official_title} (ID: {manga_id})", flush=True)
        
        chapters = get_english_chapters(manga_id)
        print(f"[+] Total queue loaded: {len(chapters)} chapters ready for processing.", flush=True)
        
        uploaded_count = 0
        
        for ch in chapters:
            attributes = ch["attributes"]
            volume = attributes.get("volume") or "0"
            chapter_num = attributes.get("chapter") or "0"
            
            clean_title = "".join([c if c.isalnum() else "_" for c in official_title.lower()]).strip("_")
            filename = f"{clean_title}_vol{volume}_ch{chapter_num}.cbz"
            
            if filename in existing_files:
                continue
                
            print(f"[*] Downloading raw chapter: {chapter_num} -> {filename}", flush=True)
            success = download_raw_cbz(filename, ch["id"])
            
            if success:
                try:
                    upload(IA_ARCHIVE_ID, files=[filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False, retries=3)
                    print(f"[🎉] Sent package to Internet Archive: {filename}", flush=True)
                    os.remove(filename) 
                    existing_files.add(filename)
                    uploaded_count += 1
                except Exception as e:
                    print(f"[-] Cloud sync error for {filename}: {e}", flush=True)
                    if os.path.exists(filename): 
                        os.remove(filename)

        print(f"[✔] Sync complete for {official_title}. New chapters uploaded: {uploaded_count}", flush=True)

    new_index = end_index if end_index < len(manga_queue) else 0
    save_last_processed_index(new_index)
