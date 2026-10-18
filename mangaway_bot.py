import os
import json
import urllib.parse
import requests
from PIL import Image
import urllib3
import subprocess

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CATALOG_FILE = "catalog.json"
COVERS_DIR = "covers"
COVER_SIZE = (200, 300)

# Sostituisci con il tuo vero nome utente e repository GitHub per i link diretti delle cover
GITHUB_USER = "LO-SCRIBA"
GITHUB_REPO = "MangaWay-Library"

def setup_environment():
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)

def download_and_optimize_cover(manga_id, url):
    if not url:
        return ""
    local_path = os.path.join(COVERS_DIR, f"{manga_id}.jpg")
    try:
        response = requests.get(url, timeout=15, verify=False)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            with Image.open(local_path) as img:
                img = img.convert('RGB')
                img.thumbnail(COVER_SIZE)
                img.save(local_path, "JPEG", quality=75)

            subprocess.run(["tex3ds", local_path, "-o", t3x_path], check=True)
            
            # Ritorna l'URL pubblico di GitHub dove risiederà la cover ottimizzata
            return f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/covers/{manga_id}.jpg"
    except Exception as e:
        print(f"[-] Errore cover per {manga_id}: {e}")
    return ""

def main():
    print("[*] Avvio MangaWay Bot calibrato sul codice C++...")
    setup_environment()
    
    # Inserisci qui le tue fonti stabili di Internet Archive
    manga_target = [
        {
            "id": "one_piece_v01",
            "title": "One Piece - Vol.1",
            "archive_id": "manga_One_Piece_v01-20",
            "filename_cbz": "One_Piece_v01.cbz",
            "filename_cover": "!cover.jpg"
        },
        {
            "id": "naruto_v01",
            "title": "Naruto - Vol.1",
            "archive_id": "manga_Naruto_v01-10",
            "filename_cbz": "Naruto_v01.cbz",
            "filename_cover": "!cover.jpg"
        }
    ]
    
    catalogo_finale = []
    
    for manga in manga_target:
        manga_id = manga["id"]
        titolo = manga["title"]
        archive_id = manga["archive_id"]
        file_cbz = manga["filename_cbz"]
        file_cover = manga["filename_cover"]
        
        print(f"[*] Ottimizzazione: {titolo}")
        
        url_manga_grezzo = f"https://archive.org{archive_id}/{file_cbz}"
        url_cover_grezza = f"https://archive.org{archive_id}/{file_cover}"
        
        # Genera il link web della cover ottimizzata su GitHub
        url_cover_provvisorio = download_and_optimize_cover(manga_id, url_cover_grezza)
        url_manga_sicuro = urllib.parse.quote(url_manga_grezzo, safe=':/')
        
        titolo_3ds = titolo if len(titolo) < 40 else titolo[:37] + "..."
        
        # Nel ciclo for del bot Python, assicurati che la struttura generata sia questa:
catalogo_finale.append({
    "titolo": titolo_3ds,
    "url_cbz": url_manga_sicuro,
    "filename": file_cbz,
    "cover_url": f"https://githubusercontent.com{GITHUB_USER}/{GITHUB_REPO}/main/covers/{manga_id}.t3x"
})

        print(f"[🎉] Allineato e aggiunto: {titolo_3ds}")

    with open(CATALOG_FILE, "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
        
    print(f"[✔] {CATALOG_FILE} pronto e mappato per il codice C++.")

if __name__ == "__main__":
    main()
