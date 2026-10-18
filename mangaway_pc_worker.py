import os
import json
import zipfile
import requests
from PIL import Image
from io import BytesIO
from internetarchive import upload
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IA_ARCHIVE_ID = "EMPTYFILE" 
IA_ACCESS_KEY = "Lqt9jGuSMWjbRyQU"
IA_SECRET_KEY = "YS2wwTS4rsL1q98w"

MAX_WIDTH = 1024 
JPEG_QUALITY = 70 
BASE_API_URL = "https://mangadex.org"

session = requests.Session()
session.headers.update({"User-Agent": "MangaWayCloudUploader/5.0"})

def main():
    print("[*] Starting MangaDex to Internet Archive Pipeline...")
    if not os.path.exists("manga_sources.json"):
        with open("manga_sources.json", "w") as f:
            json.dump(["Naruto", "Chainsaw Man", "Berserk"], f)

    with open("manga_sources.json", "r") as f:
        manga_queue = json.load(f)

    for title in manga_queue:
        print(f"\n[🔍] Scanning MangaDex: {title}")
        try:
            res = session.get(f"{BASE_API_URL}/manga", params={"title": title, "limit": 1}, verify=False).json()
            results = res.get("data", [])
            if not results:
                continue
            manga_id = results[0]["id"]
            official_title = results[0]["attributes"]["title"].get("en", title)
            
            # Fetch English chapters
            ch_res = session.get(f"{BASE_API_URL}/manga/{manga_id}/feed", params={"translatedLanguage[]": ["en"], "order[chapter]": "asc", "limit": 100}, verify=False).json()
            chapters = ch_res.get("data", [])
            
            for ch in chapters:
                ch_id = ch["id"]
                attr = ch["attributes"]
                vol = attr.get("volume") or "0"
                ch_num = attr.get("chapter") or "0"
                
                clean_title = "".join([c if c.isalnum() else "_" for c in official_title.lower()]).strip("_")
                cbz_filename = f"{clean_title}_vol{vol}_ch{ch_num}.cbz"
                
                print(f"[*] Downloading & Compressing chapter {ch_num}...")
                server_res = session.get(f"{BASE_API_URL}/at-home/server/{ch_id}", verify=False).json()
                base_url = server_res["baseUrl"]
                ch_hash = server_res["chapter"]["hash"]
                page_files = server_res["chapter"]["data"]
                
                cbz_buffer = BytesIO()
                with zipfile.ZipFile(cbz_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for i, page in enumerate(page_files):
                        img_res = session.get(f"{base_url}/data/{ch_hash}/{page}", verify=False)
                        if img_res.status_code == 200:
                            img = Image.open(BytesIO(img_res.content))
                            if img.mode in ("RGBA", "P"):
                                img = img.convert("RGB")
                            if img.width > MAX_WIDTH:
                                ratio = MAX_WIDTH / float(img.width)
                                img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.Resampling.LANCZOS)
                            
                            p_buf = BytesIO()
                            img.save(p_buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                            zip_file.writestr(f"{i:03d}.jpg", p_buf.getvalue())
                
                with open(cbz_filename, "wb") as f:
                    f.write(cbz_buffer.getvalue())
                
                upload(IA_ARCHIVE_ID, files=[cbz_filename], access_key=IA_ACCESS_KEY, secret_key=IA_SECRET_KEY, verbose=False)
                print(f"[🎉] Successfully uploaded: {cbz_filename}")
                os.remove(cbz_filename)
        except Exception as e:
            print(f"[-] Error processing {title}: {e}")

if __name__ == "__main__":
    main()
