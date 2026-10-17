import os
import json
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def main():
    print("[*] Avvio MangaWay Internet Archive Cloud Scanner...")
    
    catalogo_finale = []
    
    # 🔍 Parole chiave dei manga reali da cercare direttamente su Internet Archive
    manga_target = [
        "One Piece Digital Colored Comics",
        "Naruto digital colored comics",
        "Chainsaw Man manga"
    ]
    
    headers = {"User-Agent": "MangaWayStoreBot/1.0 (Nintendo 3DS Homebrew Project)"}
    
    for query in manga_target:
        print(f"[*] Ricerca in corso su Internet Archive per: {query}")
        
        # Chiamata all'API di ricerca di Internet Archive (Advanced Search)
        url_ricerca = "https://archive.org"
        parametri = {
            "q": f"title:({query}) AND format:(Archive BitTorrent)", # Filtra solo elementi con file scaricabili
            "fl[]": "identifier,title,description",
            "sort[]": "downloads desc", # Prende i più scaricati/affidabili
            "rows": "2",
            "output": "json"
        }
        
        try:
            res = requests.get(url_ricerca, params=parametri, headers=headers, timeout=15).json()
            items = res.get("response", {}).get("docs", [])
            
            for item in items:
                id_item = item["identifier"]
                titolo = item["title"]
                
                # Chiediamo la lista dei file interni di questo specifico archivio
                url_files = f"https://archive.org{id_item}"
                file_res = requests.get(url_files, headers=headers, timeout=15).json()
                
                file_lista = file_res.get("files", [])
                
                nome_cbz = ""
                nome_copertina = ""
                
                # Cerchiamo il file .cbz e l'immagine della copertina originale
                for f in file_lista:
                    nome_f = f["name"]
                    if nome_f.lower().endswith(".cbz") and not nome_cbz:
                        nome_cbz = nome_f
                    if nome_f.lower().endswith((".jpg", ".jpeg", ".png")) and "cover" in nome_f.lower() and not nome_copertina:
                        nome_copertina = nome_f
                
                # Se non trova una foto con la parola "cover", prende la prima immagine disponibile nell'archivio
                if not nome_copertina:
                    for f in file_lista:
                        nome_f = f["name"]
                        if nome_f.lower().endswith((".jpg", ".jpeg")):
                            nome_copertina = nome_f
                            break
                
                # Se abbiamo trovato almeno il file del manga .cbz, lo aggiungiamo al catalogo del 3DS
                if nome_cbz:
                    # Genera i link di Direct Download ufficiali stabili di Internet Archive
                    url_manga_diretto = f"https://archive.org{id_item}/{nome_cbz}"
                    url_copertina_diretta = f"https://archive.org{id_item}/{nome_copertina}" if nome_copertina else ""
                    
                    # Tagliamo titoli troppo lunghi per lo schermo del 3DS
                    titolo_3ds = titolo if len(titolo) < 40 else titolo[:37] + "..."
                    
                    catalogo_finale.append({
                        "title": titolo_3ds,
                        "cover_url": url_copertina_diretta,
                        "download_url": url_manga_diretto
                    })
                    print(f"[🎉] Trovato e aggiunto: {titolo_3ds}")
                    
        except Exception as e:
            print(f"[-] Errore durante la ricerca di {query}: {e}")

    # Se la ricerca API fallisce o non trova nulla, inseriamo due record di backup scritti bene con veri file IA stabili
    if not catalogo_finale:
        print("[!] Nessun file trovato. Attivazione canali stabili pre-configurati...")
        catalogo_finale = [
            {
                "title": "One Piece - Vol.1 (Manga)",
                "cover_url": "https://archive.orgmanga_One_Piece_v01-20/%21cover.jpg",
                "download_url": "https://archive.orgmanga_One_Piece_v01-20/One_Piece_v01.cbz"
            },
            {
                "title": "Naruto - Vol.1 (Manga)",
                "cover_url": "https://archive.orgmanga_Naruto_v01-10/%21cover.jpg",
                "download_url": "https://archive.orgmanga_Naruto_v01-10/Naruto_v01.cbz"
            }
        ]

    # Salva il catalogo finale su GitHub
    with open("catalog.json", "w", encoding="utf-8") as f_cat:
        json.dump(catalogo_finale, f_cat, indent=4, ensure_ascii=False)
    print("[✔] catalog.json compilato con successo sfruttando Internet Archive Cloud.")

if __name__ == "__main__":
    main()
