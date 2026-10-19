import os
import json
import struct
import zipfile
import urllib.parse
import requests
from PIL import Image
from io import BytesIO

# --- HARDCODED PLATFORM ENGINES ---
GITHUB_USER = "LO-SCRIBA"
GITHUB_REPO = "MangaWay-Library"

IA_ARCHIVE_ID = "MANGAWAY"  # 🎯 Il tuo nuovo archivio pulito
CATALOG_FILE = "catalog.json"
COVERS_DIR = "covers"
COVER_SIZE = (128, 256)

def save_as_t3x(img, t3x_path):
    """Converte l'immagine sorgente nel formato hardware nativo .t3x del 3DS"""
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

def parse_manga_filename(filename):
    """
    Scompone il nome del file standard (es. berserk_vol1_ch0.cbz)
    per separare il titolo della serie dai dettagli del capitolo.
    """
    # Rimuove l'estensione .cbz e pulisce
    base_name = filename.replace(".cbz", "")
    
    # Cerchiamo dove iniziano i tag di volume o capitolo per isolare la serie
    parts = base_name.split("_")
    serie_parts = []
    volume = "0"
    chapter = "0"
    
    for part in parts:
        if part.startswith("vol"):
            volume = part.replace("vol", "")
        elif part.startswith("ch"):
            chapter = part.replace("ch", "")
        elif part.strip():
            serie_parts.append(part)
            
    # Ricostruisce il nome pulito ed elegante per la UI (es. "Berserk")
    manga_name = " ".join(serie_parts).strip().title()
    # Crea un ID unico senza spazi per la cartella delle cover (es. "berserk")
    manga_id = "_".join(serie_parts).lower().strip("_")
    
    # Nome visualizzabile del capitolo sullo schermo touch
    chapter_title = f"Vol.{volume} Ch.{chapter}" if volume != "0" else f"Ch.{chapter}"
    
    return manga_name, manga_id, chapter_title

def main():
    print(f"[*] Inizializzazione della Pipeline di compilazione Catalogo per l'archivio: {IA_ARCHIVE_ID}")
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)

    # 🌐 FIX CRITICO: Cambiato l'endpoint nell'API corretta di Internet Archive (/metadata/) per ricevere il JSON vero
    url_metadata = f"https://archive.org{IA_ARCHIVE_ID}"
    
    # Struttura ad albero temporanea per il raggruppamento dinamico
    series_map = {}

    try:
        res = requests.get(url_metadata, timeout=15).json()
        file_lista = res.get("files", [])
        
        # Filtro stringente: prende solo i file .cbz escludendo tassativamente file di sistema o con nome MANGAWAY
        manga_files = [
            f["name"] for f in file_lista 
            if f["name"].lower().endswith(".cbz") and not f["name"].lower().startswith("mangaway")
        ]

        if not manga_files:
            print("[-] Nessun file .cbz valido trovato nel cloud. L'archivio potrebbe essere vuoto o in aggiornamento.")
            return

        print(f"[+] Trovati {len(manga_files)} pacchetti compressi da elaborare.")

        for filename in manga_files:
            manga_name, manga_id, chapter_title = parse_manga_filename(filename)
            
            # Genera gli URL stabili per i download e l'iniezione delle texture
            url_manga_grezzo = f"https://archive.org{IA_ARCHIVE_ID}/{filename}"
            url_manga_sicuro = urllib.parse.quote(url_manga_grezzo, safe=':/')
            url_cover_3ds = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/covers/{manga_id}.t3x"
            
            t3x_path = os.path.join(COVERS_DIR, f"{manga_id}.t3x")

            # Estrazione automatica della copertina direttamente dalla prima pagina del primo CBZ utile
            if not os.path.exists(t3x_path):
                print(f"[*] Estrazione Asset di Copertina dalla prima pagina -> {filename}")
                cbz_res = requests.get(url_manga_sicuro, timeout=30)
                if cbz_res.status_code == 200:
                    with zipfile.ZipFile(BytesIO(cbz_res.content)) as z:
                        image_files = sorted([f for f in z.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                        if image_files:
                            with z.open(image_files[0]) as first_page:
                                img = Image.open(first_page)
                                save_as_t3x(img, t3x_path)

            # Se la serie non esiste nella mappa del catalogo, la inizializziamo da zero
            if manga_id not in series_map:
                series_map[manga_id] = {
                    "manga_name": manga_name,
                    "cover_url": url_cover_3ds,
                    "chapters": []  # Array nidificato ad albero per la memoria del C++
                }

            # Inserisce il capitolo specifico dentro la serie di appartenenza
            series_map[manga_id]["chapters"].append({
                "title": chapter_title,
                "url_cbz": url_manga_sicuro,
                "filename": filename
            })
            print(f"[🎉] Capitolo mappato con successo: {manga_name} -> {chapter_title}")

    except Exception as e:
        print(f"[-] Errore fatale durante l'elaborazione dei flussi: {e}")
        return

    # Convertiamo la mappa ad albero in una lista pulita per il JSON finale
    catalogo_finale = list(series_map.values())

    # Ordinamento alfabetico delle serie per una visualizzazione corretta su schermo 3DS
    catalogo_finale.sort(key=lambda x: x["manga_name"])

    # Salvataggio del catalogo strutturato a due livelli
    with open(CATALOG_FILE, "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
        
    print(f"\n[✔] CATALOGO COMPILATO CON SUCCESSO!")
    print(f"[📊] Serie totali generate: {len(catalogo_finale)}")
    print(f"[📝] File pronto: '{CATALOG_FILE}' per il framework C++.")

if __name__ == "__main__":
    main()
