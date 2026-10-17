#include <3ds.h>
#include <citro3d.h>
#include <citro2d.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <malloc.h>
#include <curl/curl.h>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include "json.hpp"

using json = nlohmann::json;

// --- TEMA COLORI VIVACE (Stile Star Shop / E-Commerce) ---
#define COLOR_BG          C2D_Color32(18, 18, 24, 255)   // Sfondo scuro profondo
#define COLOR_CARD        C2D_Color32(32, 34, 46, 255)   // Pannelli manga grigio-blu
#define COLOR_CARD_SEL    C2D_Color32(255, 100, 0, 255)  // Arancione Neon Vivace per selezione
#define COLOR_TEXT        C2D_Color32(240, 240, 250, 255)// Bianco brillante per testi
#define COLOR_CYAN        C2D_Color32(0, 210, 255, 255)  // Cyan elettrico per Logo e Accenti
#define COLOR_SHADOW      C2D_Color32(5, 5, 10, 255)     // Nero per i contorni del testo
#define COLOR_WARNING_BG  C2D_Color32(230, 40, 70, 255)   // Rosso acceso per banner avvisi

// Struttura dati per gestire la lista dei manga in memoria
struct MangaItem {
    std::string title;
    std::string url_cbz;
    std::string filename;
};

std::vector<MangaItem> manga_list;
int selected_index = 0;
bool catalog_loaded = false;
bool show_warning_popup = false;
std::string status_msg = "Initializing network...";

// Funzione di supporto scrittura SD
size_t write_data(void *ptr, size_t size, size_t nmemb, FILE *stream) {
    return fwrite(ptr, size, nmemb, stream);
}

// Funzione di download standard
bool downloadCatalog(const std::string& url, const std::string& dest_path) {
    CURL *curl = curl_easy_init();
    if (curl) {
        FILE *fp = fopen(dest_path.c_str(), "wb");
        if (!fp) return false;

        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_data);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, fp);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
        curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
        curl_easy_setopt(curl, CURLOPT_USERAGENT, "MangaWayStore-3DS/1.0");

        CURLcode res = curl_easy_perform(curl);
        fclose(fp);
        curl_easy_cleanup(curl);
        return (res == CURLE_OK);
    }
    return false;
}

// Lettura catalogo e riempimento del vettore
void loadCatalog() {
    std::string json_path = "sdmc:/3ds/3dslibris/book/catalog.json";
    std::ifstream file(json_path);
    if (!file.is_open()) {
        status_msg = "Error: Local catalog missing.";
        return;
    }

    try {
        json j;
        file >> j;
        if (j.is_array()) {
            manga_list.clear();
            for (auto& element : j) {
                MangaItem item;
                item.title = element.value("titolo", "Unknown Manga");
                item.url_cbz = element.value("url_cbz", "");
                item.filename = element.value("filename", "manga.cbz");
                manga_list.push_back(item);
            }
            catalog_loaded = true;
            status_msg = "Store synchronized successfully.";
        }
    } catch (...) {
        status_msg = "Error: JSON format corrupted.";
    }
}

// Funzione per disegnare testo con contorno/ombra personalizzata
void DrawTextWithOutline(C2D_Text* text, float x, float y, float scale, u32 text_color) {
    // Disegna l'ombra spostata sotto/lato per creare il contorno dettagliato
    C2D_DrawText(text, C2D_AtBaseline, x + 1, y + 1, 0, scale, scale, COLOR_SHADOW);
    C2D_DrawText(text, C2D_AtBaseline, x - 1, y + 1, 0, scale, scale, COLOR_SHADOW);
    // Disegna il testo principale sopra
    C2D_DrawText(text, C2D_AtBaseline, x, y, 0, scale, scale, text_color);
}

int main(int argc, char* argv[]) {
    // Inizializzazione Rete e Cartelle SD
    static u32* soc_sharedmem = (u32*)memalign(0x1000, 0x100000);
    if(soc_sharedmem) socInit(soc_sharedmem, 0x100000);
    curl_global_init(CURL_GLOBAL_DEFAULT);
    
    mkdir("sdmc:/3ds", 0777);
    mkdir("sdmc:/3ds/3dslibris", 0777);
    mkdir("sdmc:/3ds/3dslibris/book", 0777);

    // Inizializzazione Grafica Citro2D
    gfxInitDefault();
    C3D_Init(C3D_DEFAULT_CMDBUF_SIZE);
    C2D_Init(C2D_DEFAULT_MAX_OBJECTS);
    C2D_Prepare();

    C3D_RenderTarget* top_screen = C2D_CreateScreenTarget(GFX_TOP, GFX_LEFT);
    C3D_RenderTarget* bottom_screen = C2D_CreateScreenTarget(GFX_BOTTOM, GFX_LEFT);

    C2D_TextBuf buf = C2D_TextBufNew(4096);

    // 🔄 AUTO-UPDATE ON BOOT: Scarica il catalogo prima di mostrare l'interfaccia
    std::string catalog_url = "https://githubusercontent.com";
    std::string catalog_dest = "sdmc:/3ds/3dslibris/book/catalog.json";
    if (downloadCatalog(catalog_url, catalog_dest)) {
        loadCatalog();
    } else {
        status_msg = "Offline Mode - Loading cached catalog.";
        loadCatalog();
    }

    while (aptMainLoop()) {
        hidScanInput();
        u32 kDown = hidKeysDown();

        if (kDown & KEY_START) break;

        // Gestione scorrimento lista dei Manga
        if (catalog_loaded && !manga_list.empty()) {
            if (kDown & KEY_DOWN) {
                selected_index++;
                if (selected_index >= (int)manga_list.size()) selected_index = 0;
            }
            if (kDown & KEY_UP) {
                selected_index--;
                if (selected_index < 0) selected_index = (int)manga_list.size() - 1;
            }
            // Pressione tasto X per mostrare l'avviso prima del download
            if (kDown & KEY_X) {
                show_warning_popup = !show_warning_popup; // Attiva/Disattiva il pop-up di avviso
            }
        }

        // --- SVUOTA E RICOSTRUISCI DISEGNI DI TESTO ---
        C2D_TextBufClear(buf);
        C2D_Text t_logo, t_author, t_manga_title, t_filename, t_pop1, t_pop2, t_instruction;
        
        C2D_TextParse(&t_logo, buf, "MANGAWAY");
        C2D_TextParse(&t_author, buf, "App by LO-SCRIBA");
        C2D_TextParse(&t_instruction, buf, "Use D-Pad [UP/DOWN] to browse | Press [X] to Select");
        C2D_TextParse(&t_pop1, buf, "NOTICE: Make sure you have '3dslibris' installed!");
        C2D_TextParse(&t_pop2, buf, "Press [A] to confirm download or [B] to go back.");

        if (catalog_loaded && !manga_list.empty()) {
            C2D_TextParse(&t_manga_title, buf, manga_list[selected_index].title.c_str());
            C2D_TextParse(&t_filename, buf, manga_list[selected_index].filename.c_str());
            C2D_TextOptimize(&t_manga_title);
            C2D_TextOptimize(&t_filename);
        } else {
            C2D_TextParse(&t_manga_title, buf, "No manga available in catalog.");
            C2D_TextOptimize(&t_manga_title);
        }

        C2D_TextOptimize(&t_logo);
        C2D_TextOptimize(&t_author);
        C2D_TextOptimize(&t_instruction);
        C2D_TextOptimize(&t_pop1);
        C2D_TextOptimize(&t_pop2);

        // --- RENDERING TARGETS ---
        C3D_FrameBegin(C3D_FRAME_SYNCDRAW);

        // Schermo Superiore: Dettagli, Logo Dettagliato e Copertina
        C2D_TargetClear(top_screen, COLOR_BG);
        C2D_SceneBegin(top_screen);
        
        // Disegno del Logo con contorni geometrici sfumati
        DrawTextWithOutline(&t_logo, 20, 35, 0.90f, COLOR_CYAN);
        C2D_DrawText(&t_author, C2D_AtBaseline, 300, 32, 0, 0.40f, 0.40f, COLOR_CARD_SEL);

        // Finestra Dettagli / Preview
        C2D_DrawRectSolid(15, 55, 0, 370, 165, COLOR_CARD);
        
        // Placeholder per la Copertina Grafica del Manga (Scatola geometrica a sinistra)
        C2D_DrawRectSolid(30, 70, 0, 100, 135, COLOR_BG);
        C2D_DrawLine(30, 70, COLOR_CYAN, 130, 205, COLOR_CYAN, 2, 0); // Croce estetica copertina
        
        // Testi descrittivi a destra della copertina
        C2D_DrawText(&t_manga_title, C2D_AtBaseline, 145, 95, 0, 0.55f, 0.55f, COLOR_TEXT);
        if (catalog_loaded && !manga_list.empty()) {
            C2D_DrawText(&t_filename, C2D_AtBaseline, 145, 130, 0, 0.42f, 0.42f, COLOR_CYAN);
        }

        // Banner Pop-up di Avviso prima di scaricare
        if (show_warning_popup) {
            C2D_DrawRectSolid(10, 80, 0, 380, 80, COLOR_WARNING_BG);
            C2D_DrawText(&t_pop1, C2D_AtBaseline, 25, 110, 0, 0.45f, 0.45f, COLOR_TEXT);
            C2D_DrawText(&t_pop2, C2D_AtBaseline, 25, 140, 0, 0.42f, 0.42f, COLOR_TEXT);
        }

        // Schermo Inferiore: Lista dei manga scorrevole vivace
        C2D_TargetClear(bottom_screen, COLOR_BG);
        C2D_SceneBegin(bottom_screen);

        // Genera dinamicamente le card dei titoli
        if (catalog_loaded && !manga_list.empty()) {
            for (int i = 0; i < (int)manga_list.size(); i++) {
                int y_pos = 20 + (i * 45);
                u32 card_color = (i == selected_index) ? COLOR_CARD_SEL : COLOR_CARD;
                
                // Disegna il rettangolo vivace della card manga
                C2D_DrawRectSolid(10, y_pos, 0, 300, 35, card_color);
                
                C2D_Text t_item;
                C2D_TextParse(&t_item, buf, manga_list[i].title.c_str());
                C2D_TextOptimize(&t_item);
                C2D_DrawText(&t_item, C2D_AtBaseline, 25, y_pos + 22, 0, 0.48f, 0.48f, COLOR_TEXT);
            }
        }
        
        // Istruzioni in basso sullo schermo touch
        C2D_DrawRectSolid(0, 215, 0, 320, 25, COLOR_CARD);
        C2D_DrawText(&t_instruction, C2D_AtBaseline, 10, 232, 0, 0.38f, 0.40f, COLOR_CYAN);

        C3D_FrameEnd(0);
    }

    C2D_TextBufDelete(buf);
    C2D_Fini();
    C3D_Fini();
    curl_global_cleanup();
    socExit();
    if(soc_sharedmem) free(soc_sharedmem);
    gfxExit();
    return 0;
}

