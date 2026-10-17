import os
import zipfile
from PIL import Image

def ottimizza_e_compila_cbz(cartella_immagini, nome_output_cbz):
    """
    Prende una cartella piena di immagini di un capitolo, le ridimensiona per il 3DS,
    le comprime e crea un file .cbz leggerissimo.
    """
    # 1. Crea un file ZIP temporaneo (che rinomineremo in .cbz)
    nome_zip = nome_output_cbz.replace(".cbz", ".zip")
    
    # Risoluzione ottimale per lo scorrimento sui lettori 3DS (Max 1024px in altezza)
    MAX_ALTEZZA = 1024 
    
    print(f"[*] Inizio ottimizzazione per: {nome_output_cbz}")
    
    # Elenca tutte le immagini nella cartella ordinandole alfabeticamente (Pagina 1, 2, 3...)
    pagine = sorted([f for f in os.listdir(cartella_immagini) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))])
    
    if not pagine:
        print("[-] Errore: Nessuna immagine trovata nella cartella specificata.")
        return

    with zipfile.ZipFile(nome_zip, 'w', zipfile.ZIP_DEFLATED) as cbz:
        for i, pagina in enumerate(pagine):
            percorso_completo = os.path.join(cartella_immagini, pagina)
            
            try:
                with Image.open(percorso_completo) as img:
                    # Converte in RGB se l'immagine è in altri formati (es. RGBA con trasparenza o WebP)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Calcola il ridimensionamento mantenendo le proporzioni (Aspect Ratio)
                    larghezza_orig, altezza_orig = img.size
                    if altezza_orig > MAX_ALTEZZA:
                        fattore = MAX_ALTEZZA / float(altezza_orig)
                        nuova_larghezza = int(float(larghezza_orig) * fattore)
                        img = img.resize((nuova_larghezza, MAX_ALTEZZA), Image.Resampling.LANCZOS)
                    
                    # Salva temporaneamente l'immagine ottimizzata e compressa in JPEG (Qualità 75% è ottima)
                    nome_pagina_compressa = f"page_{i:03d}.jpg"
                    img.save(nome_pagina_compressa, "JPEG", quality=75)
                    
                    # Inserisce la pagina compressa dentro l'archivio
                    cbz.write(nome_pagina_compressa, nome_pagina_compressa)
                    
                    # Rimuove il file temporaneo dal PC
                    os.remove(nome_pagina_compressa)
                    print(f"[+] Compressa pagina {i+1}/{len(pagine)}")
                    
            except Exception as e:
                print(f"[-] Errore durante l'elaborazione della pagina {pagina}: {e}")

    # Rinomina lo ZIP in .cbz
    if os.path.exists(nome_zip):
        os.rename(nome_zip, nome_output_cbz)
        print(f"\n[🎉] COMPILAZIONE COMPLETATA!")
        print(f"[->] File pronto da caricare su Internet Archive: {nome_output_cbz}")
        print(f"[->] Dimensione ridotta drasticamente!")
        
        # Genera la riga di testo pronta da incollare nel tuo catalog.json
        print("\n=== COPIA QUESTO LOG NEL TUO CATALOG.JSON ===")
        print("{\n"
              f'  "titolo": "Inserisci il Titolo Qui",\n'
              f'  "url_cbz": "https://archive.org{nome_output_cbz}",\n'
              f'  "filename": "{nome_output_cbz}"\n'
              "}")
        print("=============================================\n")

# --- ESEMPIO DI UTILIZZO SUL TUO PC ---
# Crea una cartella sul PC chiamata "capitolo_test", mettici dentro le immagini pesanti e decommenta sotto:
# ottimizza_e_compila_cbz("capitolo_test", "My_DressUp_Darling_c01_3DS.cbz")
