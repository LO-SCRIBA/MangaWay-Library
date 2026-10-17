import os
import json
import requests
import zipfile
from PIL import Image
import urllib3
from internetarchive import upload, get_session

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IA_ACCESS_KEY = os.environ.get("IA_ACCESS_KEY")
IA_SECRET_KEY = os.environ.get("IA_SECRET_KEY")

session = get_session(config={"s3": {"access": IA_ACCESS_KEY, "secret": IA_SECRET_KEY}})
BASE_URL = "https://mangadex.org"

def ottieni_manga_disponibili(limite=8):
    """Cerca manga popolari assicurandosi che abbiano contenuti disponibili"""
    print(f"[*] Ricerca di {limite} manga stabili su MangaDex...")
    url = f"{BASE_URL}/manga"
    parametri = {
        "limit": limite,
        "order[followedCount]": "desc",
        "includes[]": ["cover_art"],
        "contentRating[]": ["safe", "suggestive"] # Evita contenuti espliciti non adatti
    }
    try:
        risposta = requests.get(url, params=parametri).json()
        lista_manga = []
        
        for item in risposta.get("data", []):
            id_manga = item["id"]
            titolo = item["attributes"]["title"].get("en", list(item["attributes"]["title"].values())[0])
            descrizione = item["attributes"]["description"].get("en", "MangaWay collection.")
            
            nome_file_copertina = ""
            for rel in item["relationships"]:
                if rel["type"] == "cover_art" and "attributes" in rel:
                    nome_file_copertina = rel["attributes"].get("fileName", "")
            
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

def ottieni_pagine_capitolo(id_manga):
    """Trova il primo capitolo disponibile in inglese o italiano"""
    print(f"[*] Cerco capitoli accessibili per il manga ID: {id_manga}")
    url_feed = f"{BASE_URL}/manga/{id_manga}/feed"
    parametri = {
        "limit": 50,
        "translatedLanguage[]": ["en", "it"], # Cerca sia Inglese che Italiano
        "order[chapter]": "asc"
    }
    try:
        risposta = requests.get(url_feed, params=parametri).json()
        capitoli = risposta.get("data", [])
        if not capitoli:
            return []
        
        # Scorriamo i capitoli finché non ne troviamo uno valido che si fa scaricare
        for capitolo in capitoli:
            id_capitolo = capitolo["id"]
            url_server = f"{BASE_URL}/at-home/server/{id_capitolo}"
            dati_server = requests.get(url_server).json()
            
            if "chapter" not in dati_server:
                continue
                
            hash_capitolo = dati_server["chapter"]["hash"]
            nomi_pagine = dati_server["chapter"]["dataSaver"]
            url_base_server = dati_server["baseUrl"]
            
            if not nomi_pagine:
                continue
                
            link_pagine = [f"{url_base_server}/data-saver/{hash_capitolo}/{pag}" for pag in nomi_pagine]
            print(f"[+] Capitolo trovato con {len(link_pagine)} pagine.")
            return link_pagine
            
        return []
    except Exception as e:
        print(f"[-] Errore recupero pagine: {e}")
        return []

def ottimizza_e_salva_copertina(url_copertina, percorso_output):
    if not url_copertina: return False
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
            except:
                pass
                
    if pagine_scaricate > 0 and os.path.exists(temp_zip):
        os.rename(temp_zip, percorso_cbz)
        return True
    if os.path.exists(temp_zip): os.remove(temp_zip)
    return False

def main():
    catalogo_finale = []
    manga_trovati = ottieni_manga_disponibili(limite=8)
    
    for manga in manga_trovati:
        titolo_pulito = manga["titolo"]
        id_unico_ia = "mangaway-" + "".join(c for c in titolo_pulito.lower() if c.isalnum() or c in " -").replace(" ", "-")
        id_unico_ia = id_unico_ia[:50].strip("-")
        
        urls_pagine = ottieni_pagine_capitolo(manga["id"])
        if not urls_pagine:
            print(f"[-] Nessun capitolo disponibile per {titolo_pulito}, salto.")
            continue
            
        nome_copertina = f"{id_unico_ia}_cover.jpg"
        nome_cbz = f"{id_unico_ia}.cbz"
        
        cov_ok = ottimizza_e_salva_copertina(manga["url_copertina"], nome_copertina)
        cbz_ok = crea_cbz_3ds(urls_pagine, nome_cbz)
        
        if cbz_ok:
            dict_file = {nome_cbz: nome_cbz}
            if cov_ok: dict_file[nome_copertina] = nome_copertina
                
            metadati = {
                "collection": "opensource",
                "title": f"MangaWay - {titolo_pulito}",
                "mediatype": "texts",
                "description": manga["descrizione"][:300],
                "creator": "MangaWay Bot"
            }
            
            print(f"[*] Caricamento di {titolo_pulito} su Internet Archive...")
            try:
                upload(itemid=id_unico_ia, files=dict_file, metadata=metadati, archive_session=session)
                
                url_copertina_3ds = f"https://archive.org{id_unico_ia}/{nome_copertina}" if cov_ok else ""
                url_manga_3ds = f"https://archive.org{id_unico_ia}/{nome_cbz}"
                
                catalogo_finale.append({
                    "title": titolo_pulito,
                    "cover_url": url_copertina_3ds,
                    "download_url": url_manga_3ds
                })
                print(f"[🎉] Caricato online!")
            except Exception as e:
                print(f"[-] Errore upload: {e}")
                
        for f in [nome_copertina, nome_cbz]:
            if os.path.exists(f): os.remove(f)

    with open("catalog.json", "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("\n[✔] catalog.json aggiornato con successo!")

if __name__ == "__main__":
    main()
