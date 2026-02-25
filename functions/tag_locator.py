import os
import json
import logging
from typing import List, Optional, Tuple

# Supponiamo che questa funzione OCR sia importata o implementata altrove
from functions.ocr_utils import find_tags_with_ocr  # o mockarla per test

def tag_to_key(tag: str) -> str:
    """
    Normalizza il tag OCR: rimuove spazi e converte tutto in minuscolo
    per garantire una gestione case insensitive.
    """
    return tag.strip().replace(" ", "").lower()

def pulisci_cartella_debug(cartella: Optional[str], giorni: int = 3):
    """
    Elimina i file nella cartella di debug più vecchi di 'giorni'.
    """
    if not cartella or not os.path.exists(cartella):
        return
    now = os.path.getmtime
    cutoff = os.path.getmtime(os.path.join(cartella, os.listdir(cartella)[0])) if os.listdir(cartella) else 0
    import time
    cutoff = time.time() - (giorni * 86400)
    for f in os.listdir(cartella):
        full_path = os.path.join(cartella, f)
        if os.path.isfile(full_path):
            if os.path.getmtime(full_path) < cutoff:
                try:
                    os.remove(full_path)
                    logging.debug(f"Rimosso file debug vecchio: {full_path}")
                except Exception as e:
                    logging.warning(f"Non ho potuto rimuovere il file debug {full_path}: {e}")

def get_unique_json_path(pdf_path: str, output_dir: str) -> str:
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    return os.path.join(output_dir, f"{base_name}_signbox.json")

def generate_signbox_data_and_json(
    pdf_path: str,
    tags: List[str],
    output_dir: str,
    debug_folder: Optional[str] = None,
    write_file: bool = True
) -> Tuple[str, dict]:
    """
    Genera i dati dei box di firma tramite OCR e opzionalmente scrive il JSON su disco.
    Ritorna il percorso del file JSON e il dict con i dati.

    Questa versione usa una gestione case insensitive per i tag,
    normalizzandoli tramite tag_to_key.
    Le coordinate vengono convertite in interi.
    """

    logger = logging.getLogger(__name__)
    logger.info(f"Avvio OCR per file: {pdf_path}")

    if debug_folder:
        pulisci_cartella_debug(debug_folder, giorni=3)

    # Normalizziamo la lista tags a minuscolo per ricerca case insensitive
    normalized_tags = [tag_to_key(t) for t in tags]

    try:
        found_tags = find_tags_with_ocr(pdf_path, tags, debug_dir=debug_folder, max_workers=4)
    except Exception as e:
        logger.error(f"Errore durante l'OCR sul file {pdf_path}: {e}")
        found_tags = []

    if not found_tags:
        logger.warning(f"Nessun tag trovato da OCR per file: {pdf_path}")
    else:
        logger.info(f"Tags trovati da OCR ({len(found_tags)} elementi):")
        for idx, item in enumerate(found_tags):
            logger.info(f"  {idx+1}. Tag: '{item.get('tag')}', Pagina: {item.get('page')}, Coordinates: {item.get('coordinates')}")

    json_output = {}

    for item in found_tags:
        # Normalizzo il tag trovato a minuscolo e senza spazi
        key = tag_to_key(item["tag"])

        # Considero solo i tag che corrispondono (case insensitive) alla lista richiesta
        if key not in normalized_tags:
            logger.debug(f"Tag OCR ignorato perché non richiesto: {item['tag']} (normalizzato: {key})")
            continue

        bbox = item["coordinates"]
        obj = {
            # Converto in interi, perché l'API lo richiede
            "x": int(round(bbox.x0)),
            "y": int(round(bbox.y0)),
            "width": int(200),
            "height": int(50),
            "pag": item["page"]
        }
        if key not in json_output:
            json_output[key] = obj
        else:
            if isinstance(json_output[key], list):
                json_output[key].append(obj)
            else:
                json_output[key] = [json_output[key], obj]

    json_output["_pdf_source"] = pdf_path

    json_path = get_unique_json_path(pdf_path, output_dir)

    if write_file:
        os.makedirs(output_dir, exist_ok=True)
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_output, f, indent=4, ensure_ascii=False)
            logger.info(f"File JSON di output scritto correttamente: {json_path}")
        except Exception as e:
            logger.error(f"Errore scrivendo il file JSON {json_path}: {e}")

    return json_path, json_output
