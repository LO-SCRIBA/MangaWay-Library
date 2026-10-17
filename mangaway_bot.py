import os
import json
import requests
import zipfile
from bs4 import BeautifulSoup
from PIL import Image
import urllib3
from internetarchive import upload, get_session

# Silenziamo gli avvisi di sicurezza SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurazione Internet Archive presa dai Secrets di GitHub
IA_ACCESS_KEY = os.environ.get("IA_ACCESS_KEY")
IA_SECRET_KEY = os.environ.get("IA_SECRET_KEY")

# Avvia la connessione con Internet Archive
session = get_session(config={"s3": {"access": IA_ACCESS_KEY, "secret": IA_SECRET_KEY}})

def ottimizza_e_crea_copertina(url_copertina, percorso_output):
    """Scarica e ottimizza la copertina principale per il catalogo del 3DS"""
    try:
        img_data = requests.get(url_copertina, verify=False).content
        temp_name = "temp_raw_cover.jpg"
        with open(temp_name, "wb") as f:
            f.write(img_data)
            
        with Image.open(temp_name) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            if img.height > 1024:
                proporzione = 1024 / float(img.height)
                nuova_larghezza = int(float(img.width) * float(proporzione))
                img = img.resize((nuova_larghezza, 1024), Image.Resampling.LANCZOS)
            img.save(percorso_output, "JPEG", quality=75)
            
        if os.path.exists(temp_name): os.remove(temp_name)
        return True
    except Exception as e:
        print(f"[-] Errore ottimizzazione copertina: {e}")
        return False

def crea_manga_cbz_ottimizzato(lista_url_pagine, nome_output_cbz):
    """Scarica le pagine, le comprime per la RAM del 3DS e crea il file .cbz"""
    nome_zip_temp = nome_output_cbz.replace(".cbz", ".zip")
    MAX_ALTEZZA = 1024 
    
    print(f"[*] Compilazione capitolo in formato .cbz per 3DS...")

    with zipfile.ZipFile(nome_zip_temp, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for i, url_pagina in enumerate(lista_url_pagine):
            try:
                img_data = requests.get(url_pagina, verify=False).content
                nome_temp_img = f"temp_page_{i}.png"
                
                with open(nome_temp_img, "wb") as f_img:
                    f_img.write(img_data)
                
                with Image.open(nome_temp_img) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                        
                    larghezza_orig, altezza_orig = img.size
                    if altezza_orig > MAX_ALTEZZA:
                        fattore = MAX_ALTEZZA / float(altezza_orig)
                        nuova_larghezza = int(float(larghezza_orig) * fattore)
                        img = img.resize((nuova_larghezza, MAX_ALTEZZA), Image.Resampling.LANCZOS)
                    
                    nome_pagina_compressa = f"page_{i:03d}.jpg"
                    img.save(nome_pagina_compressa, "JPEG", quality=75)
                    
                    cbz.write(nome_pagina_compressa, nome_pagina_compressa)
                    os.remove(nome_pagina_compressa)
                
                os.remove(nome_temp_img)
            except Exception as e:
                print(f"[-] Errore pagina {i}: {e}")

    if os.path.exists(nome_zip_temp):
        os.rename(nome_zip_temp, nome_output_cbz)
        return True
    return False

def carica_su_internet_archive(id_manga, titolo, dizionario_file):
    """Spedisce i file elaborati direttamente su Internet Archive"""
    metadati = {
        "collection": "opensource",
        "title": f"MangaWay - {titolo}",
        "mediatype": "texts",
        "description": f"Manga ottimizzato automaticamente da MangaWay per Nintendo 3DS.",
        "creator": "MangaWay Bot"
    }
    try:
        upload(itemid=id_manga, files=dizionario_file, metadata=metadati, archive_session=session)
        return True
    except Exception as e:
        print(f"[-] Errore caricamento Internet Archive: {e}")
        return False

def main():
    catalogo_finale = []
    
    # 📝 STRUTTURA DATI DI TEST (Simula il comportamento dello scraper futuro)
    # Questa lista contiene le informazioni di prova con immagini di test pubbliche
    manga_da_elaborare = [
        {
            "titolo": "MangaWay Test CBZ",
            "id_unico": "mangaway-test-cbz-v1",
            "url_copertina": "https://wikimedia.org",
            # Lista di pagine da scaricare e inserire nel file .cbz
            "pagine": [
                "https://wikimedia.org",
                "https://wikimedia.org"
            ]
        }
    ]

    for manga in manga_da_elaborare:
        print(f"\n[*] Elaborazione in corso per: {manga['titolo']}")
        
        nome_copertina = f"{manga['id_unico']}_cover.jpg"
        nome_cbz = f"{manga['id_unico']}.cbz"
        
        # 1. Crea la copertina ottimizzata
        ottimizza_e_crea_copertina(manga["url_copertina"], nome_copertina)
        
        # 2. Crea il file .cbz con le pagine ottimizzate
        crea_manga_cbz_ottimizzato(manga["pagine"], nome_cbz)
        
        # Pacchetto file da inviare
        file_da_inviare = {
            nome_copertina: nome_copertina,
            nome_cbz: nome_cbz
        }
        
        # 3. Carica tutto su Internet Archive
        successo = carica_su_internet_archive(manga["id_unico"], manga["titolo"], file_da_inviare)
        
        if successo:
            # Genera i Direct Link stabili su Internet Archive per la libcurl del 3DS
            url_copertina_ia = f"https://archive.org{manga['id_unico']}/{nome_copertina}"
            url_manga_ia = f"https://archive.org{manga['id_unico']}/{nome_cbz}"
            
            catalogo_finale.append({
                "title": manga["titolo"],
                "cover_url": url_copertina_ia,
                "download_url": url_manga_ia
            })
            print(f"[🎉] Completato con successo e caricato online!")
            
        # Pulizia dei file pesanti generati sul server temporaneo di GitHub
        for f in [nome_copertina, nome_cbz]:
            if os.path.exists(f): os.remove(f)

    # Aggiorna il file catalog.json per il 3DS
    with open("catalog.json", "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("[+] catalog.json salvato correttamente.")

if __name__ == "__main__":
    main()
