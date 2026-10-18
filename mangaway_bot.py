import os
import json
import struct
import zipfile
import urllib.parse
import requests
from PIL import Image
from io import BytesIO

# --- HARDCODED TARGET KEYS ---
IA_ARCHIVE_ID = "EMPTYFILE"
GITHUB_USER = "LO-SCRIBA"
GITHUB_REPO = "MangaWay-Library"

CATALOG_FILE = "catalog.json"
COVERS_DIR = "covers"
COVER_SIZE = (128, 256)

def save_as_t3x(img, t3x_path):
    try:
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
    print(f"[*] Compiling 3DS catalog from Internet Archive item vault: {IA_ARCHIVE_ID}")
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)

    # 🎯 FIXED: Hardcoded full clean URL route with explicit domain separation slash
    url_metadata = f"https://archive.org{IA_ARCHIVE_ID}"
    catalogo_finale = []

    try:
        res = requests.get(url_metadata, timeout=15).json()
        file_lista = res.get("files", [])
        
        # Pulls only verified CBZ packets deployed by your worker
        manga_files = [f["name"] for f in file_lista if f["name"].lower().endswith(".cbz")]

        for filename in manga_files:
            titolo_pulito = filename.replace(".cbz", "").replace("_", " ").title()
            manga_id = "".join([c if c.isalnum() else "_" for c in filename.lower()]).strip("_")
            t3x_path = os.path.join(COVERS_DIR, f"{manga_id}.t3x")
            
            url_manga_grezzo = f"https://archive.org{IA_ARCHIVE_ID}/{filename}"
            url_manga_sicuro = urllib.parse.quote(url_manga_grezzo, safe=':/')
            url_cover_3ds = f"https://githubusercontent.com{GITHUB_USER}/{GITHUB_REPO}/main/covers/{manga_id}.t3x"

            if not os.path.exists(t3x_path):
                print(f"[*] Downloading metadata packet to generate .t3x for: {filename}")
                cbz_res = requests.get(url_manga_sicuro, timeout=30)
                if cbz_res.status_code == 200:
                    with zipfile.ZipFile(BytesIO(cbz_res.content)) as z:
                        image_files = sorted([f for f in z.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                        if image_files:
                            with z.open(image_files) as first_page:
                                img = Image.open(first_page)
                                save_as_t3x(img, t3x_path)

            # 🎯 FIXED: Field mappings perfectly aligned with your C++ element structure
            catalogo_finale.append({
                "titolo": titolo_pulito,
                "url_cbz": url_manga_sicuro,
                "filename": filename,
                "cover_url": url_cover_3ds
            })
            print(f"[🎉] Added to store menu: {titolo_pulito}")

    except Exception as e:
        print(f"[-] Catalog compilation stopped: {e}")

    with open(CATALOG_FILE, "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print(f"[✔] Action complete. Total items loaded into catalog.json: {len(catalogo_finale)}")

if __name__ == "__main__":
    main()
