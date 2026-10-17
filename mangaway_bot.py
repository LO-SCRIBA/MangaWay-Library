import os
import json
import zipfile
from PIL import Image, ImageDraw

def genera_canale_emergenza_ia(id_item, titolo, access_key, secret_key):
    """Genera file CBZ di test e li carica su Internet Archive inserendo le chiavi direttamente nel comando"""
    print(f"[*] Compilazione pacchetto autonomo di emergenza per: {titolo}")
    nome_copertina = f"{id_item}_cover.jpg"
    nome_cbz = f"{id_item}.cbz"
    
    try:
        # Crea un'immagine geometrica locale
        img = Image.new('RGB', (600, 1024), color = (0, 76, 153))
        d = ImageDraw.Draw(img)
        d.rectangle([(0, 0), (600, 60)], fill=(255, 128, 0))
        img.save(nome_copertina, "JPEG", quality=75)
        
        # Pacchettizza l'archivio .cbz
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
        
        # Importazione locale per evitare crash di inizializzazione globale
        from internetarchive import upload
        
        # 🔥 FIX CONFIGURAZIONE: Le chiavi vengono passate direttamente qui dentro come configurazione esplicita della chiamata
        upload(
            identifier=id_item, 
            files=dict_file, 
            metadata=metadati, 
            access_key=access_key,
            secret_key=secret_key
        )
        print(f"[🎉] Caricato con successo su Internet Archive!")
        
        res = {
            "title": titolo,
            "cover_url": f"https://archive.org{id_item}/{nome_copertina}",
            "download_url": f"https://archive.org{id_item}/{nome_cbz}"
        }
        
        for f in [nome_copertina, nome_cbz]:
            if os.path.exists(f): os.remove(f)
        return res
        
    except Exception as e:
        print(f"[-] Errore fatale durante l'upload su IA: {e}")
        for f in [nome_copertina, nome_cbz]:
            if os.path.exists(f): os.remove(f)
        return None

def main():
    print("[*] Avvio MangaWay Core Compiler...")
    
    # Recupera le chiavi all'interno della funzione principale
    IA_ACCESS_KEY = os.environ.get("IA_ACCESS_KEY", "")
    IA_SECRET_KEY = os.environ.get("IA_SECRET_KEY", "")
    
    catalogo_finale = []
    
    # Passa le credenziali direttamente alle funzioni di lavoro
    backup_1 = genera_canale_emergenza_ia("mangaway-backup-ch1", "MangaWay Stabile Volume 1", IA_ACCESS_KEY, IA_SECRET_KEY)
    backup_2 = genera_canale_emergenza_ia("mangaway-backup-ch2", "MangaWay Stabile Volume 2", IA_ACCESS_KEY, IA_SECRET_KEY)
    
    if backup_1: catalogo_finale.append(backup_1)
    if backup_2: catalogo_finale.append(backup_2)
            
    with open("catalog.json", "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("[✔] Catalogo catalog.json generato correttamente.")

if __name__ == "__main__":
    main()
