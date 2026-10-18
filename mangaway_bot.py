import os
import json
import urllib.parse
import requests
from PIL import Image
import struct

CATALOG_FILE = "catalog.json"
COVERS_DIR = "covers"
COVER_SIZE = (128, 256)

GITHUB_USER = "LO-SCRIBA"
GITHUB_REPO = "MangaWay-Library"

# 🎯 METTI QUI IL NOME DEL TUO ARCHIVIO PERSONALE SU INTERNET ARCHIVE
MY_ARCHIVE_ID = "EMPTYFILES" 

def setup_environment():
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)

def save_as_t3x(img_path, t3x_path):
    try:
        with Image.open(img_path) as img:
            img = img.convert('RGBA').resize(COVER_SIZE, Image.Resampling.LANCZOS)
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
    except:
        return False

def main():
    print(f"[*] Sincronizzazione con l'archivio personale: {MY_ARCHIVE_ID}")
    setup_environment()
    
    url_metadata = f"https://archive.org{MY_ARCHIVE_ID}"
    headers = {"User-Agent": "Mozilla/5.0"}
    catalogo_finale = []
    
    try:
        res = requests.get(url_metadata, headers=headers, timeout=15).json()
        file_lista = res.get("files", [])
        
        # Filtriamo tutti i file .cbz presenti nell'archivio
        manga_files = [f["name"] for f in file_lista if f["name"].lower().endswith(".cbz")]
        
        for filename in manga_files:
            # Rimuove l'estensione .cbz e pulisce il nome per il titolo del 3DS
            titolo_pulito = filename.replace(".cbz", "").replace("_", " ").replace("-", " ")
            manga_id = "".join([c if c.isalnum() else "_" for c in titolo_pulito.lower()]).strip("_")
            
            # Genera i link diretti
            url_manga_grezzo = f"https://archive.org{MY_ARCHIVE_ID}/{filename}"
            url_manga_sicuro = urllib.parse.quote(url_manga_grezzo, safe=':/')
            
            # Cerchiamo se nell'archivio c'è un'immagine con lo stesso nome del manga per la cover
            base_name = filename.replace(".cbz", "")
            nome_cover = ""
            for f in file_lista:
                if f["name"].lower().startswith(base_name.lower()) and f["name"].lower().endswith((".jpg", ".jpeg", ".png")):
                    nome_cover = f["name"]
                    break
            
            url_cover_3ds = ""
            if nome_cover:
                url_cover_grezza = f"https://archive.org{MY_ARCHIVE_ID}/{nome_cover}"
                local_path = os.path.join(COVERS_DIR, f"{manga_id}.jpg")
                t3x_path = os.path.join(COVERS_DIR, f"{manga_id}.t3x")
                
                img_res = requests.get(url_cover_grezza, timeout=10)
                if img_res.status_code == 200:
                    with open(local_path, 'wb') as f:
                        f.write(img_res.content)
                    if save_as_t3x(local_path, t3x_path):
                        url_cover_3ds = f"https://githubusercontent.com{GITHUB_USER}/{GITHUB_REPO}/main/covers/{manga_id}.t3x"

            titolo_3ds = titolo_pulito if len(titolo_pulito) < 40 else titolo_pulito[:37] + "..."
            
            catalogo_finale.append({
                "titolo": titolo_3ds,
                "url_cbz": url_manga_sicuro,
                "filename": filename,
                "cover_url": url_cover_3ds
            })
            print(f"[🎉] Aggiunto dal tuo archivio: {titolo_3ds}")
            
    except Exception as e:
        print(f"[-] Errore: {e}")

    with open(CATALOG_FILE, "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("[✔] Fine. Catalogo locale generato.")

if __name__ == "__main__":
    main()
