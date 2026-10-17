import os
import requests
import zipfile
from PIL import Image
import urllib3
import json as python_json

# Silenziamo gli avvisi di sicurezza SSL sul server virtuale di GitHub
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def genera_capitolo_test_3ds():
    """
    Scarica immagini di esempio da un server pubblico aperto, le ottimizza
    alla risoluzione del 3DS e compila il file .cbz aggiornando il catalogo.
    """
    print("[*] Initializing MangaWay Open-Source Sample Test...")
    
    # Lista di immagini di test pubbliche stabili da usare come pagine del manga
    urls_immagini = [
        "https://githubusercontent.com",
        "https://githubusercontent.com"
    ]
    
    nome_output_cbz = "MangaWay_Sample_Ch1_3DS.cbz"
    nome_zip_temp = nome_output_cbz.replace(".cbz", ".zip")
    MAX_ALTEZZA = 1024 
    
    print(f"[*] Downloading and compressing {len(urls_immagini)} sample pages directly to 3DS format...")

    with zipfile.ZipFile(nome_zip_temp, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for i, url_pagina in enumerate(urls_immagini):
            try:
                # Scarica l'immagine dal server aperto
                img_data = requests.get(url_pagina, verify=False).content
                nome_temp_img = f"temp_page_{i}.png"
                
                with open(nome_temp_img, "wb") as f_img:
                    f_img.write(img_data)
                
                # Ottimizzazione e compressione in JPEG adatta alla RAM del 3DS
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
                print(f"[+] Processed sample page {i+1}/{len(urls_immagini)}")
            except Exception as e:
                print(f"[-] Error processing page {i}: {e}")

    if os.path.exists(nome_zip_temp):
        os.rename(nome_zip_temp, nome_output_cbz)
        print(f"\n[🎉] SUCCESS! File compiled successfully: {nome_output_cbz}")
        
        # Recupera in automatico l'ambiente della tua repository corrente
        repo_ambiente = os.environ.get('GITHUB_REPOSITORY', 'LO-SCRIBA/MangaWay')
        
        blocco_manga = {
            "titolo": "MangaWay Sample - Chapter 1",
            "url_cbz": f"https://githubusercontent.com{repo_ambiente}/main/{nome_output_cbz}",
            "filename": nome_output_cbz
        }
        
        # Genera o aggiorna in automatico il catalogo locale da inviare al 3DS
        with open("catalog.json", "w") as f_cat:
            python_json.dump([blocco_manga], f_cat, indent=2)
        print("[+] catalog.json compiled and linked successfully!")

# Avvia l'elaborazione del canale aperto di test
genera_capitolo_test_3ds()
