import os
import json
import urllib.parse
import requests
from PIL import Image
import urllib3
import struct

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CATALOG_FILE = "catalog.json"
COVERS_DIR = "covers"
COVER_SIZE = (128, 256)

GITHUB_USER = "LO-SCRIBA"
GITHUB_REPO = "MangaWay-Library"

def setup_environment():
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)

def save_as_t3x(img_path, t3x_path):
    try:
        with Image.open(img_path) as img:
            img = img.convert('RGBA')
            img = img.resize(COVER_SIZE, Image.Resampling.LANCZOS)
            width, height = img.size
            header = struct.pack('<4sHHHH', b'T3X1', width, height, 3, 1)
            
            pixel_data = bytearray()
            for y in range(height):
                for x in range(width):
                    r, g, b, a = img.getpixel((x, y))
                    pixel_data.extend([a, b, g, r])
            
            with open(t3x_path, 'wb') as f:
                f.write(header)
                f.write(pixel_data)
            return True
    except Exception as e:
        print(f"[-] Errore conversione interna T3X: {e}")
    return False

def download_and_optimize_cover(manga_id, url):
    if not url:
        return ""
    local_path = os.path.join(COVERS_DIR, f"{manga_id}.jpg")
    t3x_path = os.path.join(COVERS_DIR, f"{manga_id}.t3x")
    try:
        response = requests.get(url, timeout=15, verify=False)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            if save_as_t3x(local_path, t3x_path):
                return f"https://githubusercontent.com{GITHUB_USER}/{GITHUB_REPO}/main/covers/{manga_id}.t3x"
    except Exception as e:
        print(f"[-] Impossibile ottimizzare la cover per {manga_id}: {e}")
    return ""

def main():
    print("[*] Avvio MangaWay Scraper (Hybrid Controlled Edition)...")
    setup_environment()
    
    # Lista stabile con ID di Internet Archive reali e separati correttamente
    manga_target = [
        {
            "id": "one_piece_v01",
            "title": "One Piece - Vol.1",
            "archive_id": "manga_One_Piece_v01-20"
        },
        {
            "id": "naruto_v01",
            "title": "Naruto - Vol.1",
            "archive_id": "manga_Naruto_v01-10"
        }
    ]
    
    headers = {"User-Agent": "MangaWayStoreBot/3.0"}
    catalogo_finale = []
    
    for manga in manga_target:
        archive_id = manga["archive_id"]
        titolo_pulito = manga["title"]
        manga_id = manga["id"]
        
        print(f"\n[*] Ispezione interna per l'archivio: {archive_id}")
        url_metadata = f"https://archive.org{archive_id}"
        
        try:
            res = requests.get(url_metadata, headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"[-] Impossibile raggiungere l'archivio {archive_id} (Stato: {res.status_code})")
                continue
                
            meta_res = res.json()
            file_lista = meta_res.get("files", [])
            
            nome_cbz = ""
            nome_cover = ""
            
            for f in file_lista:
                nome_f = f["name"]
                if nome_f.lower().endswith(".cbz") and not nome_cbz:
                    nome_cbz = nome_f
                if nome_f.lower().endswith((".jpg", ".jpeg", ".png")) and "cover" in nome_f.lower() and not nome_cover:
                    nome_cover = nome_f
            
            if not nome_cover:
                for f in file_lista:
                    nome_f = f["name"]
                    if nome_f.lower().endswith((".jpg", ".jpeg")):
                        nome_cover = nome_f
                        break
            
            if nome_cbz:
                url_manga_grezzo = f"https://archive.org{archive_id}/{nome_cbz}"
                url_cover_grezza = f"https://archive.org{archive_id}/{nome_cover}" if nome_cover else ""
                
                url_manga_sicuro = urllib.parse.quote(url_manga_grezzo, safe=':/')
                url_cover_3ds = download_and_optimize_cover(manga_id, url_cover_grezza)
                
                catalogo_finale.append({
                    "titolo": titolo_pulito,
                    "url_cbz": url_manga_sicuro,
                    "filename": nome_cbz,
                    "cover_url": url_cover_3ds
                })
                print(f"[🎉] Sincronizzato con successo: {titolo_pulito}")
            else:
                print(f"[-] Nessun file .cbz trovato dentro l'archivio {archive_id}")
                
        except Exception as e:
            print(f"[-] Errore durante l'ispezione di {archive_id}: {e}")

    with open(CATALOG_FILE, "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
        
    print(f"\n[✔] Scansione terminata. {CATALOG_FILE} popolato con {len(catalogo_finale)} elementi.")

if __name__ == "__main__":
    main()
