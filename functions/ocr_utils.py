import fitz  # PyMuPDF
import os
from typing import List, Dict, Optional
from collections import namedtuple


BBox = namedtuple("BBox", ["x0", "y0", "width", "height"])

def find_tags_with_ocr(
    pdf_path: str,
    tags: List[str],
    debug_dir: Optional[str] = None,
    max_workers: int = 1  # non usato in questa versione base
) -> List[Dict]:
    """
    Cerco le occorrenze di specifici tag di testo all'interno del PDF.
    Ritorno una lista di dict con tag, coordinates (BBox), e pagina.

    In questa versione aggiornata:
    - normalizzo i tag solo UNA volta all'inizio
    - applico una logica di match PARZIALE: se il tag appare anche "in mezzo"
      in una parola più grande, lo considero valido (es: "__@@FIRMACLIENTE@@__"
      oppure "testo@@firmacna@@testo").
    - mantengo l'intera struttura originale, senza rimuovere alcun meccanismo
      
    """

    results = []

    # = NUOVO Francesco 18/11/2025: normalizzo i tag una volta sola
    # Lo faccio qui perché in PDF i tag possono essere scritti maiuscoli,
    # minuscoli, oppure sporchi da caratteri attaccati.
    normalized_tags = [t.lower() for t in tags]

    # Apro il documento
    doc = fitz.open(pdf_path)

    # Ciclo pagina per pagina
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)

        # Estraggo le parole tramite PyMuPDF
        # Ottengo tuple: (x0, y0, x1, y1, word, block_no, line_no, word_no)
        text_instances = page.get_text("words")

        # Costruisco un elenco più semplice:
        # (word, x0, y0, x1, y1)
        words = [(w[4], w[0], w[1], w[2], w[3]) for w in text_instances]

        # Ora ciclo ogni parola del PDF
        for word, x0, y0, x1, y1 in words:
            w = word.lower()  # lo normalizzo una volta sola

            # NUOVO FRANCESCO 18/11/2025: match parziale — cerco il tag dentro la parola
            # Questo risolve i casi come:
            # "__@@FIRMACLIENTE@@__", "attivo@@firmacliente@@attivo", ecc.
            for tag_lower in normalized_tags:
                if tag_lower in w:  # match flessibile
                    # Creo il bounding box
                    bbox = BBox(
                        x0=x0,
                        y0=y0,
                        width=(x1 - x0),
                        height=(y1 - y0)
                    )

                    # Recupero il tag originale per l’output
                    original_tag = tags[normalized_tags.index(tag_lower)]

                    # Aggiungo alla lista risultati
                    results.append({
                        "tag": original_tag,
                        "coordinates": bbox,
                        "page": page_num + 1
                    })

                   
                    if debug_dir:
                        if not os.path.exists(debug_dir):
                            os.makedirs(debug_dir)

                        pix = page.get_pixmap()
                        img_path = os.path.join(
                            debug_dir,
                            f"page_{page_num + 1}_{original_tag}.png"
                        )
                        pix.save(img_path)
                        

    doc.close()
    return results
