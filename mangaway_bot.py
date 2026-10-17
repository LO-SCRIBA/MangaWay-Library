import os
import json
import requests
import zipfile
from PIL import Image
import urllib3
from internetarchive import upload, get_session

# Disattiviamo gli avvisi SSL per evitare blocchi sui server virtuali
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Recupera le chiavi segrete salvate su GitHub
IA_ACCESS_KEY = os.environ.get("IA_ACCESS_KEY")
IA_SECRET_KEY = os.environ.get("IA_SECRET_KEY")

# Connessione sicura a Internet Archive
session = get_session(config={"s3": {"access": IA_ACCESS_KEY, "secret": IA_SECRET_KEY}})

BASE_URL = "https://mangadex.org"

def ottieni_manga_popolari(limite=5):
    """Cerca i manga più popolari del momento su MangaDex"""
    print(f"[*] Ricerca dei {limite} manga più popolari su MangaDex...")
    url = f"{BASE_URL}/manga"
    parametri = {
        "limit": limite,
        "order[followedCount]": "desc",
        "includes[]": ["cover_art"]
    }
    try:
        risposta = requests.get(url, params=parametri).json()
        lista_manga = []
        
        for item in risposta.get("data", []):
            id_manga = item["id"]
            # Prende il titolo in inglese o la prima lingua disponibile
            titolo = item["attributes"]["title"].get("en", list(item["attributes"]["title"].values())[0])
            descrizione = item["attributes"]["description"].get("en", "Nessuna descrizione disponibile.")
            
            # Cerca il link della copertina
            nome_file_copertina = ""
            for rel in item["relationships"]:
                if rel["type"] == "cover_art":
                    nome_file_copertina = rel["attributes"]["fileName"]
            
            url_copertina = ""
            if nome_file_copertina:
                url_copertina = f"https://mangadex.org{id_manga}/{nome_file_copertina}"
            
            lista_manga.append({
                "id": id_manga,
                "titolo": titolo,
                "descrizione": descrizione,
                "url_copertina": url_copertina
            })
        return lista_manga
    except Exception as e:
        print(f"[-] Errore ricerca MangaDex: {e}")
        return []

def ottieni_pagine_primo_capitolo(id_manga):
    """Trova il primo capitolo in inglese del manga e restituisce i link delle pagine"""
    print(f"[*] Cerco il primo capitolo per il manga ID: {id_manga}")
    url_feed = f"{BASE_URL}/manga/{id_manga}/feed"
    parametri = {
        "limit": 100,
        "translatedLanguage[]": ["en"], # Filtra solo capitoli in INGLESE
        "order[chapter]": "asc"
    }
    try:
        risposta = requests.get(url_feed, params=parametri).json()
        capitoli = risposta.get("data", [])
        if not capitoli:
            print("[-] Nessun capitolo in inglese trovato.")
            return []
        
        # Prendiamo il primo capitolo della lista (il più vecchio/iniziale)
        primo_capitolo = capitoli[0]
        id_capitolo = primo_capitolo["id"]
        
        # Chiediamo i server dove sono ospitate le immagini delle pagine
        url_server = f"{BASE_URL}/at-home/server/{id_capitolo}"
        dati_server = requests.get(url_server).json()
        
        hash_capitolo = dati_server["chapter"]["hash"]
        nomi_pagine = dati_server["chapter"]["dataSaver"] # dataSaver usa immagini più leggere, ottime per il 3DS
        url_base_server = dati_server["baseUrl"]
        
        link_pagine = []
        for pagina in nomi_pagine:
            link_pagine.append(f"{url_base_server}/data-saver/{hash_capitolo}/{pagina}")
            
        return link_pagine
    except Exception as e:
        print(f"[-] Errore recupero pagine capitolo: {e}")
        return []

def ottimizza_e_salva_copertina(url_copertina, percorso_output):
    """Scarica la copertina e la ridimensiona a 1024px per lo schermo del 3DS"""
    if not url_copertina:
        return False
    try:
        img_data = requests.get(url_copertina).content
        temp = "temp_raw_cov.jpg"
        with open(temp, "wb") as f: f.write(img_data)
        
        with Image.open(temp) as img:
            if img.mode != 'RGB': img = img.convert('RGB')
            if img.height > 1024:
                prop = 1024 / float(img.height)
                img = img.resize((int(float(img.width) * prop), 1024), Image.Resampling.LANCZOS)
            img.save(percorso_output, "JPEG", quality=75)
        if os.path.exists(temp): os.remove(temp)
        return True
    except:
        return False

def crea_cbz_3ds(lista_url_pagine, percorso_cbz):
    """Scarica le pagine del capitolo, le ottimizza al 75% di qualità e crea l'archivio .cbz"""
    temp_zip = percorso_cbz.replace(".cbz", ".zip")
    pagine_scaricate = 0
    
    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for i, url in enumerate(lista_url_pagine):
            try:
                img_data = requests.get(url).content
                nome_temp = f"temp_p_{i}.png"
                with open(nome_temp, "wb") as f: f.write(img_data)
                
                with Image.open(nome_temp) as img:
                    if img.mode != 'RGB': img = img.convert('RGB')
                    if img.height > 1024:
                        prop = 1024 / float(img.height)
                        img = img.resize((int(float(img.width) * prop), 1024), Image.Resampling.LANCZOS)
                    
                    nome_pag_3ds = f"page_{i:03d}.jpg"
                    img.save(nome_pag_3ds, "JPEG", quality=75)
                    cbz.write(nome_pag_3ds, nome_pag_3ds)
                    os.remove(nome_pag_3ds)
                os.remove(nome_temp)
                pagine_scaricate += 1
            except Exception as e:
                print(f"[-] Errore elaborazione pagina {i}: {e}")
                
    if pagine_scaricate > 0 and os.path.exists(temp_zip):
        os.rename(temp_zip, percorso_cbz)
        return True
    if os.path.exists(temp_zip): os.remove(temp_zip)
    return False

def main():
    catalogo_finale = []
    
    # Prende i 5 manga più famosi da MangaDex
    manga_trovati = ottieni_manga_popolari(limite=5)
    
    for manga in manga_trovati:
        titolo_pulito = manga["titolo"]
        # Crea un ID valido per Internet Archive (solo lettere minuscole, numeri e trattini)
        id_unico_ia = f"mangaway-" + "".join(c for c in titolo_pulito.lower() if c.isalnum() or c in " -").replace(" ", "-")
        id_unico_ia = id_unico_ia[:50] # Evita ID troppo lunghi
        
        print(f"\n[+] Elaborazione: {titolo_pulito}")
        
        # 1. Trova le pagine del primo capitolo
        urls_pagine = ottieni_pagine_primo_capitolo(manga["id"])
        if not urls_pagine:
            print(f"[-] Salto {titolo_pulito}: nessun capitolo utilizzabile.")
            continue
            
        nome_copertina = f"{id_unico_ia}_cover.jpg"
        nome_cbz = f"{id_unico_ia}.cbz"
        
        # 2. Ottimizza Copertina e crea il file CBZ
        cov_ok = ottimizza_e_salva_copertina(manga["url_copertina"], nome_copertina)
        cbz_ok = crea_cbz_3ds(urls_pagine, nome_cbz)
        
        if cbz_ok:
            dict_file = {nome_cbz: nome_cbz}
            if cov_ok:
                dict_file[nome_copertina] = nome_copertina
                
            # Metadati per Internet Archive
            metadati = {
                "collection": "opensource",
                "title": f"MangaWay - {titolo_pulito}",
                "mediatype": "texts",
                "description": manga["descrizione"][:400], # Massimo 400 caratteri
                "creator": "MangaWay Bot"
            }
            
            # 3. Upload su Internet Archive
            print(f"[*] Caricamento file su Internet Archive...")
            try:
                upload(itemid=id_unico_ia, files=dict_file, metadata=metadati, archive_session=session)
                
                # Crea i link stabili pronti per la libcurl del 3DS
                url_copertina_3ds = f"https://archive.org{id_unico_ia}/{nome_copertina}" if cov_ok else ""
                url_manga_3ds = f"https://archive.org{id_unico_ia}/{nome_cbz}"
                
                catalogo_finale.append({
                    "title": titolo_pulito,
                    "cover_url": url_copertina_3ds,
                    "download_url": url_manga_3ds
                })
                print(f"[🎉] Caricato con successo su Internet Archive!")
            except Exception as e:
                print(f"[-] Fallito upload IA per {titolo_pulito}: {e}")
                
        # Pulizia file locali generati
        for f in [nome_copertina, nome_cbz]:
            if os.path.exists(f): os.remove(f)

    # Scrive il catalogo aggiornato per la console
    with open("catalog.json", "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("\n[✔] catalog.json compilato con tutti i manga reali!")

if __name__ == "__main__":
    main()
