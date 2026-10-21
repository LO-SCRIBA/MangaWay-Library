import os
import time
import zipfile
import requests
from internetarchive import upload, get_item, download
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IA_ARCHIVE_ID = "MANGAWAYIA"
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

BASE_API_URL = "https://api.mangadex.org"
INDEX_FILE_NAME = "last_processed_index.txt"

session = requests.Session()
session.headers.update({
    "User-Agent": "MangaWayStore3DSWorker/5.0 (Nintendo 3DS Homebrew Link)"
})

def get_uploaded_archive_files():
    print(f"[*] Fetching remote file list from Internet Archive ({IA_ARCHIVE_ID})...")
    try:
        item = get_item(IA_ARCHIVE_ID)
        return {f['name'] for f in item.files}
    except Exception as e:
        print(f"[⚠️] Unable to map remote archive ({e}). Proceeding without history check.")
        return set()

def get_last_processed_index():
    print(f"[*] Checking for progress state file ({INDEX_FILE_NAME}) on cloud...")
    try:
        download(IA_ARCHIVE_ID, files=[INDEX_FILE_NAME], destdir=".", ignore_errors=True)
        if os.path.exists(INDEX_FILE_NAME):
            with open(INDEX_FILE_NAME, "r", encoding="utf-8") as f:
                index = int(f.read().strip())
                print(f"[+] Resuming from manga index: {index}")
                return index
    except Exception as e:
        print(f"[⚠️] No progress state found or error reading it ({e}). Starting from 0.")
    return 0

def save_last_processed_index(index):
    print(f"[*] Saving current progress index ({index}) to cloud...")
    with open(INDEX_FILE_NAME, "w", encoding="utf-8") as f:
        f.write(str(index))
    try:
        upload(IA_ARCHIVE_ID, files=[INDEX_FILE_NAME], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
        os.remove(INDEX_FILE_NAME)
    except Exception as e:
        print(f"[-] Failed to upload state file to cloud: {e}")

def get_english_chapters(manga_id):
    all_chapters = []
    limit = 100
    offset = 0
    
    while True:
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
            time.sleep(0.2)
            res = session.get(raw_url, verify=False, timeout=15)
            
            if res.status_code == 200:
                res_json = res.json()
                data = res_json.get("data", [])
                total = res_json.get("total", 0)
                
                if not data:
                    break
                
                all_chapters.extend(data)
                offset += limit
                
                if len(all_chapters) >= total:
                    break
            else:
                print(f"[-] Server feed error (Status {res.status_code}).")
                break
        except Exception as e:
            print(f"[-] Exception during extraction: {e}")
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
                
                time.sleep(0.2)
                img_res = session.get(page_url, verify=False, timeout=15)
                
                if img_res.status_code == 200:
                    zip_file.writestr(f"{i+1:03d}.jpg", img_res.content)
                    
        return os.path.exists(cbz_filename) and os.path.getsize(cbz_filename) > 0
    except Exception as e:
        print(f"[-] Download failed for chapter {cbz_filename}: {e}")
        if os.path.exists(cbz_filename):
            os.remove(cbz_filename)
        return False

def main():
    if not os.path.exists("lista_manga.txt"):
        print("[-] Error: file lista_manga.txt not found.")
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
        print("[-] No manga configured inside lista_manga.txt")
        return

    start_index = get_last_processed_index()
    if start_index >= len(manga_queue):
        print("[*] Reached the end of the manga list in previous runs. Resetting index to 0.")
        start_index = 0

    end_index = start_index + 20
    chunk_to_process = manga_queue[start_index:end_index]
    
    print(f"[*] Processing chunk from index {start_index} to {min(end_index, len(manga_queue))} (Total items: {len(chunk_to_process)})")

    existing_files = get_uploaded_archive_files()

    for official_title, manga_id in chunk_to_process:
        print(f"\n[🔍] Scanning database for: {official_title} (ID: {manga_id})")
        
        chapters = get_english_chapters(manga_id)
        print(f"[+] Total queue loaded: {len(chapters)} chapters ready for processing.")
        
        uploaded_count = 0
        
        for ch in chapters:
            attributes = ch["attributes"]
            volume = attributes.get("volume") or "0"
            chapter_num = attributes.get("chapter") or "0"
            
            clean_title = "".join([c if c.isalnum() else "_" for c in official_title.lower()]).strip("_")
            filename = f"{clean_title}_vol{volume}_ch{chapter_num}.cbz"
            
            if filename in existing_files:
                continue
                
            print(f"[*] Downloading raw chapter: {chapter_num} -> {filename}")
            success = download_raw_cbz(filename, ch["id"])
            
            if success:
                try:
                    upload(IA_ARCHIVE_ID, files=[filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                    print(f"[🎉] Sent package to Internet Archive: {filename}")
                    os.remove(filename) 
                    existing_files.add(filename)
                    uploaded_count += 1
                except Exception as e:
                    print(f"[-] Cloud sync error for {filename}: {e}")
                    if os.path.exists(filename): 
                        os.remove(filename)

        print(f"[✔] Sync complete for {official_title}. New chapters uploaded: {uploaded_count}")

    new_index = end_index if end_index < len(manga_queue) else 0
    save_last_processed_index(new_index)
    print(f"\n[🏁] Batch processing completed. Next run will start from index: {new_index}")

if __name__ == "__main__":
    main()
