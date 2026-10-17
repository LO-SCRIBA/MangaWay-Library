import os
import requests
import zipfile
from PIL import Image
import urllib3

# Disabilita i messaggi di avviso SSL sul server
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def cerca_e_scarica_capitolo_3ds(nome_manga, numero_capitolo, lingua="en"):
    """
    Cerca un manga su MangaDex, scarica il capitolo, ridimensiona le immagini per il 3DS
    e compila il file .cbz aggiornando automaticamente il catalogo locale.
    """
    print(f"[*] Searching for '{nome_manga}' on MangaDex...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    # 1. Cerca il Manga
    url_ricerca = "https://mangadex.org"
    params_ricerca = {"title": nome_manga, "limit": 1}
    
    r = requests.get(url_ricerca, params=params_ricerca, headers=headers, verify=False)
    if r.status_code != 200:
        print(f"[-] Error: Server responded with status code {r.status_code}")
        return

    data_ricerca = r.json()
    if not data_ricerca.get("data") or len(data_ricerca["data"]) == 0:
        print("[-] Error: Manga not found on MangaDex.")
        return
        
    # 🔥 CORREZIONE CHIRURGICA INDICI: Estrazione corretta dall'array "data" di MangaDex
    manga_struttura = data_ricerca["data"][0] 
    manga_id = manga_struttura["id"]
    titolo_reale = manga_struttura["attributes"]["title"].get("en", nome_manga)
    print(f"[+] Found: {titolo_reale} (ID: {manga_id})")

    # 2. Cerca il capitolo specifico nel feed del Manga
    print(f"[*] Looking for Chapter {numero_capitolo} (Language: {lingua})...")
    url_capitoli = f"https://mangadex.org/{manga_id}/feed"
    params_capitoli = {
        "chapters[]": [str(numero_capitolo)],
        "translatedLanguage[]": [lingua],
        "limit": 1
    }
    r_cap = requests.get(url_capitoli, params=params_capitoli, headers=headers, verify=False)
    
    if r_cap.status_code != 200 or not r_cap.json().get("data") or len(r_cap.json()["data"]) == 0:
        print(f"[-] Error: Chapter {numero_capitolo} in language '{lingua}' not found.")
        return
        
    chapter_struttura = r_cap.json()["data"][0]
    chapter_id = chapter_struttura["id"]
    print(f"[+] Found Chapter ID: {chapter_id}")

    # 3. Ottieni i link delle immagini dal server At-Home
    url_server = f"https://mangadex.org{chapter_id}"
    r_server = requests.get(url_server, headers=headers, verify=False)
    if r_server.status_code != 200:
        print("[-] Error: Unable to retrieve image server from MangaDex.")
        return
        
    dati_server = r_server.json()
    base_url = dati_server["baseUrl"]
    hash_capitolo = dati_server["chapter"]["hash"]
    lista_pagine = dati_server["chapter"]["dataSaver"] 

    # 4. Scarica, ridimensiona e compila il file .cbz
    nome_manga_pulito = titolo_reale.replace(" ", "_").replace(":", "").replace("?", "").replace("-", "_")
    nome_output_cbz = f"{nome_manga_pulito}_Ch{numero_capitolo}_3DS.cbz"
    nome_zip_temp = nome_output_cbz.replace(".cbz", ".zip")
    
    MAX_ALTEZZA = 1024 
    print(f"[*] Downloading and compressing {len(lista_pagine)} pages directly to 3DS format...")

    with zipfile.ZipFile(nome_zip_temp, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for i, filename_pagina in enumerate(lista_pagine):
            url_pagina = f"{base_url}/data-saver/{hash_capitolo}/{filename_pagina}"
            
            img_data = requests.get(url_pagina, headers=headers, verify=False).content
            nome_temp_img = f"temp_page_{i}.jpg"
            
            with open(nome_temp_img, "wb") as f_img:
                f_img.write(img_data)
                
            try:
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
            except Exception as e:
                print(f"[-] Error processing page {i}: {e}")
                
            os.remove(nome_temp_img)
            print(f"[+] Processed page {i+1}/{len(lista_pagine)}")

    if os.path.exists(nome_zip_temp):
        os.rename(nome_zip_temp, nome_output_cbz)
        print(f"\n[🎉] SUCCESS! File compiled successfully: {nome_output_cbz}")
        
        # 🔥 AUTOMAZIONE CATALOGO: Scrive direttamente la struttura corretta dentro il file local catalog.json
        import json as python_json
        blocco_manga = {
            "titolo": f"{titolo_reale} - Chapter {numero_capitolo}",
            "url_cbz": f"https://githubusercontent.com{nome_output_cbz}",
            "filename": nome_output_cbz
        }
        
        # Sovrascrive il catalog.json locale con il nuovo array aggiornato
        with open("catalog.json", "w") as f_cat:
            python_json.dump([blocco_manga], f_cat, indent=2)
        print("[+] catalog.json updated successfully on server cache!")

# Avvia il bot
cerca_e_scarica_capitolo_3ds("My Dress-Up Darling", 1, lingua="en")
