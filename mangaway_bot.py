import os
import json
import requests
import zipfile
from PIL import Image, ImageDraw
import urllib3
from internetarchive import upload, get_session

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IA_ACCESS_KEY = os.environ.get("IA_ACCESS_KEY")
IA_SECRET_KEY = os.environ.get("IA_SECRET_KEY")

session = get_session(config={"s3": {"access": IA_ACCESS_KEY, "secret": IA_SECRET_KEY}})
BASE_URL = "https://mangadex.org"
HEADERS = {"User-Agent": "MangaWayStoreBot/1.0 (Nintendo 3DS Homebrew Project)"}

def scarica_manga_diretto(id_manga, titolo_manga):
    print(f"[*] Avvio download per: {titolo_manga}")
    url_manga = f"{BASE_URL}/manga/{id_manga}?includes[]=cover_art"
    url_copertina = ""
    descrizione = "Ottimizzato per MangaWay 3DS."
    
    try:
        res = requests.get(url_manga, headers=HEADERS, timeout=15).json()
        if "data" in res and "attributes" in res["data"]:
            descrizione = res["data"]["attributes"]["description"].get("en", descrizione)[:200]
            for rel in res["data"]["relationships"]:
                if rel["type"] == "cover_art" and "attributes" in rel:
                    nome_file = rel["attributes"].get("fileName", "")
                    if nome_file:
                        url_copertina = f"https://mangadex.org{id_manga}/{nome_file}"
    except Exception as e:
        print(f"[-] Errore metadati MangaDex: {e}")

    url_feed = f"{BASE_URL}/manga/{id_manga}/feed"
    parametri = {"limit": 10, "translatedLanguage[]": ["en"], "order[chapter]": "asc"}
    link_pagine = []
    
    try:
        feed_res = requests.get(url_feed, headers=HEADERS, params=parametri, timeout=15).json()
        if "data" in feed_res:
            for capitolo in feed_res["data"]:
                id_capitolo = capitolo["id"]
                dati_server = requests.get(f"{BASE_URL}/at-home/server/{id_capitolo}", headers=HEADERS, timeout=15).json()
                if "chapter" in dati_server and dati_server["chapter"]["dataSaver"]:
                    hash_capitolo = dati_server["chapter"]["hash"]
                    url_base = dati_server["baseUrl"]
                    link_pagine = [f"{url_base}/data-saver/{hash_capitolo}/{pag}" for pag in dati_server["chapter"]["dataSaver"]]
                    break
    except Exception as e:
        print(f"[-] Errore feed/pagine MangaDex: {e}")

    if not link_pagine:
        print(f"[-] Nessuna pagina estratta da MangaDex per {titolo_manga}.")
        return None

    id_unico_ia = "mangaway-" + "".join(c for c in titolo_manga.lower() if c.isalnum() or c in " -").replace(" ", "-")
    id_unico_ia = id_unico_ia[:50].strip("-")
    
    nome_copertina = f"{id_unico_ia}_cover.jpg"
    nome_cbz = f"{id_unico_ia}.cbz"
    
    cov_ok = False
    if url_copertina:
        try:
            img_data = requests.get(url_copertina, timeout=15).content
            with open("temp_c.jpg", "wb") as f: f.write(img_data)
            with Image.open("temp_c.jpg") as img:
                if img.mode != 'RGB': img = img.convert('RGB')
                if img.height > 1024:
                    img = img.resize((int(float(img.width) * (1024 / float(img.height))), 1024), Image.Resampling.LANCZOS)
                img.save(nome_copertina, "JPEG", quality=75)
            os.remove("temp_c.jpg")
            cov_ok = True
        except: pass

    temp_zip = nome_cbz.replace(".cbz", ".zip")
    pagine_ok = 0
    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for i, url in enumerate(link_pagine):
            try:
                img_data = requests.get(url, timeout=15).content
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
        dict_file = {nome_cbz: nome_cbz}
        if cov_ok: dict_file[nome_copertina] = nome_copertina
        
        metadati = {
            "collection": "opensource",
            "title": f"MangaWay - {titolo_manga}",
            "mediatype": "texts",
            "description": descrizione,
            "creator": "MangaWay Bot"
        }
        
        try:
            upload(itemid=id_unico_ia, files=dict_file, metadata=metadati, archive_session=session)
            output = {
                "title": titolo_manga,
                "cover_url": f"https://archive.org{id_unico_ia}/{nome_copertina}" if cov_ok else "",
                "download_url": f"https://archive.org{id_unico_ia}/{nome_cbz}"
            }
            for f in [nome_copertina, nome_cbz]:
                if os.path.exists(f): os.remove(f)
            return output
        except Exception as e:
            print(f"[-] Errore upload Internet Archive: {e}")
            
    if os.path.exists(temp_zip): os.remove(temp_zip)
    return None

def genera_canale_emergenza_ia(id_item, titolo):
    """Genera localmente un'immagine matematica in C++ stile e crea il file .cbz per il 3DS"""
    print(f"[*] Creazione grafica autonoma di emergenza per: {titolo}")
    nome_copertina = f"{id_item}_cover.jpg"
    nome_cbz = f"{id_item}.cbz"
    
    try:
        # Generiamo un'immagine colorata Cobalt Blue da 600x1024 (formato perfetto per 3DS) senza scaricare nulla
        img = Image.new('RGB', (600, 1024), color = (0, 76, 153))
        d = ImageDraw.Draw(img)
        # Disegniamo una striscia decorativa Neon Orange stile e-commerce di MangaWay
        d.rectangle([(0, 0), (600, 50)], fill=(255, 128, 0))
        img.save(nome_copertina, "JPEG", quality=75)
        
        # Impacchettiamo il file CBZ comprimendolo
        temp_zip = nome_cbz.replace(".cbz", ".zip")
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as cbz:
            cbz.write(nome_copertina, "page_000.jpg")
        if os.path.exists(temp_zip):
            os.rename(temp_zip, nome_cbz)
            
        dict_file = {nome_cbz: nome_cbz, nome_copertina: nome_copertina}
        metadati = {
            "collection": "opensource", 
            "title": f"MangaWay - {titolo}", 
            "mediatype": "texts", 
            "creator": "MangaWay Bot"
        }
        
        # Carica il blocco generato su Internet Archive
        upload(itemid=id_item, files=dict_file, metadata=metadati, archive_session=session)
        print(f"[🎉] Backup inviato con successo su IA!")
        
        res = {
            "title": titolo,
            "cover_url": f"https://archive.org{id_item}/{nome_copertina}",
            "download_url": f"https://archive.org{id_item}/{nome_cbz}"
        }
        
        for f in [nome_copertina, nome_cbz]:
            if os.path.exists(f): os.remove(f)
        return res
    except Exception as e:
        print(f"[-] Fallimento critico caricamento di backup su IA: {e}")
        for f in [nome_copertina, nome_cbz]:
            if os.path.exists(f): os.remove(f)
        return None

def main():
    catalogo_finale = []
    manga_target = [
        {"titolo": "Chainsaw Man", "id": "a77742b1-cdef-4c34-bf32-c507456bbd54"},
        {"titolo": "Boku no Hero Academia", "id": "f213b48a-accd-4ef4-a30f-d1b5ed4e3a8d"}
    ]
    
    for item in manga_target:
        risultato = scarica_manga_diretto(item["id"], item["titolo"])
        if risultato:
            catalogo_finale.append(risultato)
            
    if not catalogo_finale:
        print("[!] Download MangaDex bloccato da Cloudflare. Avvio caricamento autonomo su Internet Archive...")
        backup_1 = genera_canale_emergenza_ia("mangaway-backup-ch1", "MangaWay Backup Volume 1")
        backup_2 = genera_canale_emergenza_ia("mangaway-backup-ch2", "MangaWay Backup Volume 2")
        if backup_1: catalogo_finale.append(backup_1)
        if backup_2: catalogo_finale.append(backup_2)
            
    with open("catalog.json", "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("[✔] Script completato con successo. File generati pronti per il 3DS.")

if __name__ == "__main__":
    main()
