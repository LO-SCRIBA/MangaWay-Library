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

def scarica_manga_diretto(id_manga, titolo_manga):
    """Scarica un manga specifico tramite il suo ID univoco di MangaDex"""
    print(f"[*] Avvio download forzato per: {titolo_manga}")
    
    # 1. Recupera la copertina
    url_manga = f"{BASE_URL}/manga/{id_manga}?includes[]=cover_art"
    url_copertina = ""
    descrizione = "Ottimizzato per MangaWay 3DS."
    try:
        res = requests.get(url_manga).json()
        descrizione = res["data"]["attributes"]["description"].get("en", descrizione)[:200]
        for rel in res["data"]["relationships"]:
            if rel["type"] == "cover_art" and "attributes" in rel:
                nome_file = rel["attributes"].get("fileName", "")
                if nome_file:
                    url_copertina = f"https://mangadex.org{id_manga}/{nome_file}"
    except Exception as e:
        print(f"[-] Errore recupero metadati: {e}")

    # 2. Recupera le pagine del primo capitolo disponibile
    url_feed = f"{BASE_URL}/manga/{id_manga}/feed"
    parametri = {"limit": 10, "translatedLanguage[]": ["en"], "order[chapter]": "asc"}
    link_pagine = []
    try:
        feed_res = requests.get(url_feed, params=parametri).json()
        for capitolo in feed_res.get("data", []):
            id_capitolo = capitolo["id"]
            dati_server = requests.get(f"{BASE_URL}/at-home/server/{id_capitolo}").json()
            if "chapter" in dati_server and dati_server["chapter"]["dataSaver"]:
                hash_capitolo = dati_server["chapter"]["hash"]
                url_base = dati_server["baseUrl"]
                link_pagine = [f"{url_base}/data-saver/{hash_capitolo}/{pag}" for pag in dati_server["chapter"]["dataSaver"]]
                break
    except Exception as e:
        print(f"[-] Errore recupero pagine capitolo: {e}")

    if not link_pagine:
        print(f"[-] Impossibile estrarre pagine per {titolo_manga}")
        return None

    # Id univoco pulito per Internet Archive
    id_unico_ia = "mangaway-" + "".join(c for c in titolo_manga.lower() if c.isalnum() or c in " -").replace(" ", "-")
    id_unico_ia = id_unico_ia[:50].strip("-")
    
    nome_copertina = f"{id_unico_ia}_cover.jpg"
    nome_cbz = f"{id_unico_ia}.cbz"
    
    # 3. Ottimizzazione Grafica 3DS (1024px, JPEG 75%)
    cov_ok = False
    if url_copertina:
        try:
            img_data = requests.get(url_copertina).content
            with open("temp_c.jpg", "wb") as f: f.write(img_data)
            with Image.open("temp_c.jpg") as img:
                if img.mode != 'RGB': img = img.convert('RGB')
                if img.height > 1024:
                    img = img.resize((int(float(img.width) * (1024 / float(img.height))), 1024), Image.Resampling.LANCZOS)
                img.save(nome_copertina, "JPEG", quality=75)
            os.remove("temp_c.jpg")
            cov_ok = True
        except: pass

    # Creazione file .cbz
    temp_zip = nome_cbz.replace(".cbz", ".zip")
    pagine_ok = 0
    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for i, url in enumerate(link_pagine):
            try:
                img_data = requests.get(url).content
                nome_temp = f"temp_p_{i}.png"
                with open(nome_temp, "wb") as f: f.write(img_data)
                with Image.open(nome_temp) as img:
                    if img.mode != 'RGB': img = img.convert('RGB')
                    if img.height > 1024:
                        img = img.resize((int(float(img.width) * (1024 / float(img.height))), 1024), Image.Resampling.LANCZOS)
                    nome_pag_3ds = f"page_{i:03d}.jpg"
                    img.save(nome_pag_3ds, "JPEG", quality=75)
                    cbz.write(nome_pag_3ds, nome_pag_3ds)
                    os.remove(nome_pag_3ds)
                os.remove(nome_temp)
                pagine_ok += 1
            except: pass

    if pagine_ok > 0 and os.path.exists(temp_zip):
        os.rename(temp_zip, nome_cbz)
        
        # 4. Caricamento effettivo su Internet Archive
        dict_file = {nome_cbz: nome_cbz}
        if cov_ok: dict_file[nome_copertina] = nome_copertina
        
        metadati = {
            "collection": "opensource",
            "title": f"MangaWay - {titolo_manga}",
            "mediatype": "texts",
            "description": descrizione,
            "creator": "MangaWay Bot"
        }
        
        print(f"[*] Upload in corso su Internet Archive per {titolo_manga}...")
        try:
            upload(itemid=id_unico_ia, files=dict_file, metadata=metadati, archive_session=session)
            print(f"[🎉] Fatto! Caricato nell'archivio online.")
            
            output = {
                "title": titolo_manga,
                "cover_url": f"https://archive.org{id_unico_ia}/{nome_copertina}" if cov_ok else "",
                "download_url": f"https://archive.org{id_unico_ia}/{nome_cbz}"
            }
            
            # Pulizia file locali sul server GitHub
            for f in [nome_copertina, nome_cbz]:
                if os.path.exists(f): os.remove(f)
            return output
        except Exception as e:
            print(f"[-] Errore upload Internet Archive: {e}")
            
    if os.path.exists(temp_zip): os.remove(temp_zip)
    return None

def main():
    catalogo_finale = []
    
    # Lista controllata di Manga Famosi per evitare blocchi IP generici
    # Ogni dizionario ha il titolo e l'ID fisso ricavato da MangaDex
    manga_target = [
        {"titolo": "Chainsaw Man", "id": "a77742b1-cdef-4c34-bf32-c507456bbd54"},
        {"titolo": "Boku no Hero Academia", "id": "f213b48a-accd-4ef4-a30f-d1b5ed4e3a8d"}
    ]
    
    for item in manga_target:
        risultato = scarica_manga_diretto(item["id"], item["titolo"])
        if risultato:
            catalogo_finale.append(risultato)
            
    with open("catalog.json", "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("[✔] Script terminato. catalog.json generato.")

if __name__ == "__main__":
    main()
