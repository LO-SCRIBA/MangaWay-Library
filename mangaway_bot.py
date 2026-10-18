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

# 🌐 CONFIGURA I TUOI DATI GITHUB (Per generare i link corretti per il 3DS)
GITHUB_USER = "LO-SCRIBA"
GITHUB_REPO = "MangaWay-Library"

def setup_environment():
    if not os.path.exists(COVERS_DIR):
        os.makedirs(COVERS_DIR)

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
            with Image.open(local_path) as img:
                img = img.convert('RGB')
                img.thumbnail(COVER_SIZE)
                img.save(local_path, "JPEG", quality=75)
            
            # Conversione nativa in texture 3DS tramite l'ambiente GitHub Actions
            subprocess.run(["tex3ds", local_path, "-o", t3x_path], check=True)
            return f"https://githubusercontent.com{GITHUB_USER}/{GITHUB_REPO}/main/covers/{manga_id}.t3x"
    except Exception as e:
        print(f"[-] Impossibile ottimizzare la cover per {manga_id}: {e}")
    return ""

def main():
    print("[*] Avvio MangaWay Smart Scanner 100% Automatico...")
    setup_environment()
    
    # 🔍 INSERISCI QUI SOLO LE PAROLE CHIAVE. Il bot cercherà tutto da solo!
    manga_da_cercare = [
        "One Piece Digital Colored Comics",
        "Naruto digital colored comics",
        "Chainsaw Man manga"
    ]
    
    headers = {"User-Agent": "MangaWayStoreBot/2.0 (Nintendo 3DS Automation)"}
    catalogo_finale = []
    
    for query in manga_da_cercare:
        print(f"\n[*] Analisi automatica su Internet Archive per: {query}")
        
        # Interroghiamo il motore di ricerca di Internet Archive
        url_ricerca = "https://archive.org"
        parametri = {
            "q": f"title:({query}) AND format:(Archive BitTorrent)", # Filtro di qualità per evitare archivi corrotti
            "fl[]": "identifier,title",
            "sort[]": "downloads desc", # Prende i più popolari e completi
            "rows": "5", # Controlla i primi 5 risultati per trovare quello migliore
            "output": "json"
        }
        
        try:
            res = requests.get(url_ricerca, params=parametri, headers=headers, timeout=15).json()
            items = res.get("response", {}).get("docs", [])
            
            for item in items:
                archive_id = item["identifier"]
                titolo_originale = item["title"]
                
                # Creiamo un ID pulito per i file di sistema (es. "one_piece_digital_colored")
                manga_id = "".join([c if c.isalnum() else "_" for c in archive_id.lower()])
                
                # 🕵️‍♂️ ISPEZIONE AUTOMATICA DENTRO L'ARCHIVIO
                # Chiediamo la lista reale dei file per non andare alla cieca
                url_metadata = f"https://archive.org{archive_id}"
                meta_res = requests.get(url_metadata, headers=headers, timeout=15).json()
                file_lista = meta_res.get("files", [])
                
                nome_cbz = ""
                nome_cover = ""
                
                # Cerchiamo in automatico il file .cbz e l'immagine della copertina
                for f in file_lista:
                    nome_f = f["name"]
                    if nome_f.lower().endswith(".cbz") and not nome_cbz:
                        nome_cbz = nome_f
                    if nome_f.lower().endswith((".jpg", ".jpeg", ".png")) and "cover" in nome_f.lower() and not nome_cover:
                        nome_cover = nome_f
                
                # Se non c'è un file chiamato "cover", prende la prima immagine disponibile come anteprima
                if not nome_cover:
                    for f in file_lista:
                        nome_f = f["name"]
                        if nome_f.lower().endswith((".jpg", ".jpeg")):
                            nome_cover = nome_f
                            break
                
                # 🌟 SE IL BOT HA TROVATO IL CAPITOLO, LO ELABORA PER IL 3DS
                if nome_cbz:
                    url_manga_grezzo = f"https://archive.org{archive_id}/{nome_cbz}"
                    url_cover_grezza = f"https://archive.org{archive_id}/{nome_cover}" if nome_cover else ""
                    
                    # 1. URL Encoding automatico (Risolve gli spazi e i caratteri speciali che rompevano il 3DS)
                    url_manga_sicuro = urllib.parse.quote(url_manga_grezzo, safe=':/')
                    
                    # 2. Scarica la copertina e la trasforma in .t3x nativo per il 3DS
                    url_cover_3ds = download_and_optimize_cover(manga_id, url_cover_grezza)
                    
                    # Accorcia il titolo per lo schermo della console
                    titolo_3ds = titolo_originale if len(titolo_originale) < 40 else titolo_originale[:37] + "..."
                    
                    # 3. Compilazione dei campi esatti richiesti dal tuo codice C++
                    catalogo_finale.append({
                        "titolo": titolo_3ds,
                        "url_cbz": url_manga_sicuro,
                        "filename": nome_cbz,
                        "cover_url": url_cover_3ds
                    })
                    print(f"[🎉] Trovato e configurato automaticamente: {titolo_3ds}")
                    break # Passa al prossimo manga della lista appena ne trova uno valido
                    
        except Exception as e:
            print(f"[-] Errore durante lo scanning automatico di {query}: {e}")

    # Scrittura finale del catalogo sincronizzato
    with open(CATALOG_FILE, "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
        
    print(f"\n[✔] {CATALOG_FILE} aggiornato! Trovati {len(catalogo_finale)} manga online.")

if __name__ == "__main__":
    main()

