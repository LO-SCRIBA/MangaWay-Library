import os
import json
import zipfile
import hmac
import hashlib
from datetime import datetime
import requests
from PIL import Image, ImageDraw

def genera_data_xml():
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <metadata>
        <collection>opensource</collection>
        <mediatype>texts</mediatype>
        <creator>MangaWay Bot</creator>
    </metadata>"""

def carica_file_s3(bucket_id, nome_file, percorso_locale, access_key, secret_key):
    """Effettua l'upload diretto su Internet Archive usando il protocollo S3 standard via HTTP"""
    url = f"https://{bucket_id}.s3.us.archive.org/{nome_file}"
    
    # Intestazioni di autenticazione richieste da Internet Archive S3
    headers = {
        "Authorization": f"LOW {access_key}:{secret_key}",
        "Content-Type": "application/octet-stream",
        "x-archive-auto-make-bucket": "1",
        "x-archive-meta01-collection": "opensource",
        "x-archive-meta-mediatype": "texts"
    }
    
    try:
        with open(percorso_locale, "rb") as f:
            dati = f.read()
        res = requests.put(url, headers=headers, data=dati, timeout=30)
        if res.status_code == 200:
            print(f"[+] Caricato con successo via S3: {nome_file}")
            return True
        else:
            print(f"[-] Errore server S3 ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"[-] Fallimento connessione HTTP S3: {e}")
        return False

def main():
    print("[*] Avvio MangaWay HTTP-S3 Core Compiler...")
    
    IA_ACCESS_KEY = os.environ.get("IA_ACCESS_KEY", "").strip()
    IA_SECRET_KEY = os.environ.get("IA_SECRET_KEY", "").strip()
    
    if not IA_ACCESS_KEY or not IA_SECRET_KEY:
        print("[-] Errore: Chiavi di autenticazione IA mancanti o non configurate nei Secrets.")
        return

    catalogo_finale = []
    
    # Definiamo i volumi di test stabili
    volumi = [
        {"id": "mangaway-backup-ch1", "titolo": "MangaWay Stabile Volume 1"},
        {"id": "mangaway-backup-ch2", "titolo": "MangaWay Stabile Volume 2"}
    ]
    
    for vol in volumi:
        id_item = vol["id"]
        titolo = vol["titolo"]
        
        nome_copertina = f"{id_item}_cover.jpg"
        nome_cbz = f"{id_item}.cbz"
        
        # Genera immagine locale
        img = Image.new('RGB', (600, 1024), color = (0, 76, 153))
        d = ImageDraw.Draw(img)
        d.rectangle([(0, 0), (600, 60)], fill=(255, 128, 0))
        img.save(nome_copertina, "JPEG", quality=75)
        
        # Genera file .cbz
        temp_zip = nome_cbz.replace(".cbz", ".zip")
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as cbz:
            cbz.write(nome_copertina, "page_000.jpg")
        if os.path.exists(temp_zip):
            os.rename(temp_zip, nome_cbz)
            
        # Upload dei file via richieste HTTP pulite
        up_cov = carica_file_s3(id_item, nome_copertina, nome_copertina, IA_ACCESS_KEY, IA_SECRET_KEY)
        up_cbz = carica_file_s3(id_item, nome_cbz, nome_cbz, IA_ACCESS_KEY, IA_SECRET_KEY)
        
        if up_cbz:
            catalogo_finale.append({
                "title": titolo,
                "cover_url": f"https://archive.org{id_item}/{nome_copertina}" if up_cov else "",
                "download_url": f"https://archive.org{id_item}/{nome_cbz}"
            })
            
        # Pulizia file temporanei locali
        for f in [nome_copertina, nome_cbz]:
            if os.path.exists(f): os.remove(f)
            
    with open("catalog.json", "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("[✔] Compilazione completata. catalog.json salvato.")

if __name__ == "__main__":
    main()
