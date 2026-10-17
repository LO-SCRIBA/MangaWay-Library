import os
import json
import zipfile
import requests
from PIL import Image, ImageDraw

def main():
    print("[*] Avvio MangaWay Real Manga Compiler...")
    
    repo_name = os.environ.get('GITHUB_REPOSITORY', 'LO-SCRIBA/MangaWay-Library')
    
    manga_reali = [
        {
            "title": "One Piece - Chapter 1",
            "id": "one-piece-ch1",
            "cover_url": "https://wikimedia.org",
            "pagine": [
                "https://wikimedia.org",
                "https://wikimedia.org"
            ]
        },
        {
            "title": "Naruto - Chapter 1",
            "id": "naruto-ch1",
            "cover_url": "https://wikimedia.org",
            "pagine": [
                "https://wikimedia.org",
                "https://wikimedia.org"
            ]
        }
    ]
    
    catalogo_finale = []

    for manga in manga_reali:
        print(f"[*] Elaborazione reale per: {manga['title']}")
        
        nome_copertina = f"{manga['id']}_cover.jpg"
        nome_cbz = f"{manga['id']}.cbz"
        cov_ok = False
        
        # 1. Scarica la copertina vera del manga
        try:
            cov_data = requests.get(manga["cover_url"], timeout=15).content
            with open("temp_cov.jpg", "wb") as f: f.write(cov_data)
            with Image.open("temp_cov.jpg") as img:
                if img.mode != 'RGB': img = img.convert('RGB')
                if img.height > 1024:
                    img = img.resize((int(float(img.width) * (1024 / float(img.height))), 1024), Image.Resampling.LANCZOS)
                img.save(nome_copertina, "JPEG", quality=75)
            os.remove("temp_cov.jpg")
            cov_ok = True
            print(f"[+] Copertina scaricata con successo per {manga['title']}")
        except Exception as e:
            print(f"[-] Impossibile scaricare copertina web ({e}). Genero copertina autonoma...")
            # 🔥 PARACADUTE: Se il link web fallisce, disegna da solo la copertina colorata per non far crashare Git
            img = Image.new('RGB', (600, 1024), color = (0, 76, 153))
            d = ImageDraw.Draw(img)
            d.rectangle([(0, 0), (600, 60)], fill=(255, 128, 0))
            img.save(nome_copertina, "JPEG", quality=75)
            cov_ok = True

        # 2. Scarica le pagine e compila il file .cbz
        temp_zip = nome_cbz.replace(".cbz", ".zip")
        pagine_ok = 0
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as cbz:
            for i, url_pag in enumerate(manga["pagine"]):
                try:
                    img_data = requests.get(url_pag, timeout=15).content
                    nome_temp_p = f"temp_p_{i}.png"
                    with open(nome_temp_p, "wb") as f: f.write(img_data)
                    
                    with Image.open(nome_temp_p) as img:
                        if img.mode != 'RGB': img = img.convert('RGB')
                        if img.height > 1024:
                            img = img.resize((int(float(img.width) * (1024 / float(img.height))), 1024), Image.Resampling.LANCZOS)
                        nome_pag_3ds = f"page_{i:03d}.jpg"
                        img.save(nome_pag_3ds, "JPEG", quality=75)
                        cbz.write(nome_pag_3ds, nome_pag_3ds)
                        os.remove(nome_pag_3ds)
                    os.remove(nome_temp_p)
                    pagine_ok += 1
                except:
                    pass
                    
        if pagine_ok > 0 and os.path.exists(temp_zip):
            os.rename(temp_zip, nome_cbz)
            
            url_copertina_3ds = f"https://githubusercontent.com{repo_name}/main/{nome_copertina}" if cov_ok else ""
            url_manga_3ds = f"https://githubusercontent.com{repo_name}/main/{nome_cbz}"
            
            catalogo_finale.append({
                "title": manga["title"],
                "cover_url": url_copertina_3ds,
                "download_url": url_manga_3ds
            })
            print(f"[✔] Compilato e pronto: {manga['title']}")
        else:
            if os.path.exists(temp_zip): os.remove(temp_zip)

    # Scrive il catalogo finale
    with open("catalog.json", "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("[✔] catalog.json generato con successo.")

if __name__ == "__main__":
    main()
