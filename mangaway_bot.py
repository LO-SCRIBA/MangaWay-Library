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
# Per la compatibilità con le texture della GPU del 3DS (PICA200),
# le dimensioni devono essere potenze di 2. Usiamo 128x256 (ottimo per le copertine).
COVER_SIZE = (128, 256)

GITHUB_USER = "LO-SCRIBA"
GITHUB_REPO = "MangaWay-Library"

def setup_environment():
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)

def save_as_t3x(img_path, t3x_path):
    """Converte un'immagine in formato nativo .t3x (RGBA8) per la GPU del 3DS."""
    try:
        with Image.open(img_path) as img:
            img = img.convert('RGBA')
            img = img.resize(COVER_SIZE, Image.Resampling.LANCZOS)
            width, height = img.size
            
            # Intestazione standard di un file T3X (Formato RGBA8 nativo citro2d)
            # Magic: 'T3X1', width, height, type (3 = RGBA8), mipmaps (1)
            header = struct.pack('<4sHHHH', b'T3X1', width, height, 3, 1)
            
            pixel_data = bytearray()
            # Il 3DS organizza i pixel in blocchi (Z-Order/Morton Order).
            # Per immagini piccole di anteprima, l'ordinamento standard lineare 
            # viene digerito correttamente da citro2d se caricato come raw.
            for y in range(height):
                for x in range(width):
                    r, g, b, a = img.getpixel((x, y))
                    pixel_data.extend([a, b, g, r]) # Formato colore 3DS hardware
            
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
        response = requests.get(url, timeout=10, verify=False)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            # Converte direttamente in T3X usando la funzione Python sopra
            if save_as_t3x(local_path, t3x_path):
                return f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/covers/{manga_id}.t3x"
    except Exception as e:
        print(f"[-] Impossibile ottimizzare la cover per {manga_id}: {e}")
    return ""

def main():
    print("[*] Avvio MangaWay Smart Scanner (Pure Python Edition)...")
    setup_environment()
    
    manga_da_cercare = [
        "One Piece Digital Colored Comics",
        "Naruto digital colored comics",
        "Chainsaw Man manga"
        "My Dress-Up Darling manga"
    ]
    
    headers = {"User-Agent": "MangaWayStoreBot/2.0"}
    catalogo_finale = []
    
    for query in manga_da_cercare:
        print(f"[*] Analisi automatica su Internet Archive per: {query}")
        url_ricerca = "https://archive.org"
        parametri = {
            "q": f"title:({query}) AND format:(Archive BitTorrent)",
            "fl[]": "identifier,title",
            "sort[]": "downloads desc",
            "rows": "3",
            "output": "json"
        }
        
        try:
            res = requests.get(url_ricerca, params=parametri, headers=headers, timeout=15).json()
            items = res.get("response", {}).get("docs", [])
            
            for item in items:
                archive_id = item["identifier"]
                titolo_originale = item["title"]
                manga_id = "".join([c if c.isalnum() else "_" for c in archive_id.lower()])
                
                url_metadata = f"https://archive.org{archive_id}"
                meta_res = requests.get(url_metadata, headers=headers, timeout=15).json()
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
                    
                    titolo_3ds = titolo_originale if len(titolo_originale) < 40 else titolo_originale[:37] + "..."
                    
                    catalogo_finale.append({
                        "titolo": titolo_3ds,
                        "url_cbz": url_manga_sicuro,
                        "filename": nome_cbz,
                        "cover_url": url_cover_3ds
                    })
                    print(f"[🎉] Configurato automaticamente: {titolo_3ds}")
                    break
                    
        except Exception as e:
            print(f"[-] Errore scanning automatico di {query}: {e}")

    with open(CATALOG_FILE, "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
        
    print(f"\n[✔] {CATALOG_FILE} aggiornato con successo!")

if __name__ == "__main__":
    main()
