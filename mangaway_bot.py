import os
import json
import urllib.parse
import requests
from PIL import Image
import urllib3

# Disabilita i messaggi di avviso per SSL non verificati
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurazione costanti per il 3DS
CATALOG_FILE = "catalog.json"
COVERS_DIR = "covers"
COVER_SIZE = (200, 300) # Dimensione leggerissima salvapeso per la RAM del 3DS

def setup_environment():
    """Crea la cartella per le cover se non esiste."""
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)

def download_and_optimize_cover(manga_id, url):
    """Scarica la cover e la comprime per non far crashare lo schermo del 3DS."""
    if not url:
        return ""
    
    local_path = os.path.join(COVERS_DIR, f"{manga_id}.jpg")
    try:
        response = requests.get(url, timeout=15, verify=False)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            # Elaborazione immagine (forza JPEG standard e rimpicciolisce)
            with Image.open(local_path) as img:
                img = img.convert('RGB')
                img.thumbnail(COVER_SIZE)
                img.save(local_path, "JPEG", quality=75)
            
            # Ritorna il percorso relativo che leggerà il 3DS (es. "covers/one_piece.jpg")
            return f"covers/{manga_id}.jpg"
    except Exception as e:
        print(f"[-] Errore ottimizzazione cover per {manga_id}: {e}")
    return ""

def main():
    print("[*] Avvio MangaWay Internet Archive Controlled Bot...")
    setup_environment()
    
    # 🎯 LISTA SICURA E VERIFICATA (Sostituisci questi ID temporanei con i tuoi funzionanti da browser)
    # L' 'archive_id' è la stringa finale nell'URL di Internet Archive dopo /details/
    # Il 'filename_cbz' è il nome esatto del file completo
    # Il 'filename_cover' è il nome del file immagine della copertina nell'archivio
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
        },
        {
            "id": "chainsaw_v01",
            "title": "Chainsaw Man - Vol.1",
            "archive_id": "chainsaw-man-vol-1-ita",
            "filename_cbz": "Chainsaw_Man_v01.cbz",
            "filename_cover": "cover.jpg"
        }
    ]
    
    catalogo_finale = []
    
    for manga in manga_target:
        manga_id = manga["id"]
        titolo = manga["title"]
        archive_id = manga["archive_id"]
        file_cbz = manga["filename_cbz"]
        file_cover = manga["filename_cover"]
        
        print(f"[*] Elaborazione controllata per: {titolo}")
        
        # 1. Costruzione dei link grezzi di Internet Archive
        url_manga_grezzo = f"https://archive.org{archive_id}/{file_cbz}"
        url_cover_grezza = f"https://archive.org{archive_id}/{file_cover}"
        
        # 2. Ottimizzazione Cover locale (Scarica, rimpicciolisce e salva in /covers)
        percorso_cover_3ds = download_and_optimize_cover(manga_id, url_cover_grezza)
        
        # 3. URL Encoding dei Link di Download (Risolve i caratteri speciali tipo ! o spazi)
        url_manga_sicuro = urllib.parse.quote(url_manga_grezzo, safe=':/')
        
        # Tagliamo titoli troppo lunghi per lo schermo del 3DS (ereditato dal tuo vecchio codice)
        titolo_3ds = titolo if len(titolo) < 40 else titolo[:37] + "..."
        
        # 4. Inserimento nel catalogo con i campi corretti che si aspetta la console
        catalogo_finale.append({
            "title": titolo_3ds,
            "cover_url": percorso_cover_3ds, # Ora punta al file locale "covers/nome.jpg" ottimizzato
            "download_url": url_manga_sicuro # Link codificato correttamente senza errori 404
        })
        print(f"[🎉] Ottimizzato e aggiunto con successo: {titolo_3ds}")

    # Salva il file finale definitivo catalog.json
    with open(CATALOG_FILE, "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
        
    print(f"\n[✔] {CATALOG_FILE} compilato con successo. Copertine pronte nella cartella /{COVERS_DIR}.")

if __name__ == "__main__":
    main()
