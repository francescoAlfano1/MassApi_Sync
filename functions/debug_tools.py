import logging

def debug_firmatario(email, final_users, controparti_map_all):
    """
    Debug completo per un singolo firmatario:
    - mostra controparti_keys
    - verifica se ogni chiave è presente in controparti_map_all
    - mostra in quali workspace è presente la controparte
    """

    logging.info(f"=== DEBUG FIRMATARIO: {email} ===")

    # 1. Recupero il record del firmatario
    record = None
    for key, data in final_users.items():
        if data["record"].get("mail") == email.lower():
            record = data["record"]
            break

    if not record:
        logging.error(f"[DEBUG] Firmatario {email} NON trovato in final_users")
        return

    cont_keys = record.get("controparti_keys", [])
    logging.info(f"[DEBUG] controparti_keys del firmatario: {cont_keys}")

    # 2. Raccolgo tutte le chiavi presenti nelle controparti remote
    all_client_keys = set()
    for ws_id, ws_map in controparti_map_all.items():
        all_client_keys.update(ws_map.keys())

    logging.info(f"[DEBUG] Chiavi controparti presenti nel sistema: {list(all_client_keys)}")

    # 3. Verifico match per ogni chiave
    for ck in cont_keys:
        if ck in all_client_keys:
            logging.info(f"[DEBUG] MATCH: {ck} trovata tra le controparti")
            # Mostro in quali workspace si trova
            for ws_id, ws_map in controparti_map_all.items():
                if ck in ws_map:
                    logging.info(f"[DEBUG] → presente in workspace {ws_id} con ID {ws_map[ck]}")
        else:
            logging.warning(f"[DEBUG] NO MATCH: {ck} NON trovata in nessun workspace")

    logging.info(f"=== FINE DEBUG FIRMATARIO: {email} ===\n")


def debug_controparti(final_clients, controparti_map_all):
    """
    Debug generale delle controparti:
    - mostra le chiavi logiche finali
    - mostra le chiavi presenti nei workspace remoti
    """

    logging.info("=== DEBUG CONTROPARTI ===")

    logging.info(f"[DEBUG] Chiavi controparti locali (final_clients): {list(final_clients.keys())}")

    for ws_id, ws_map in controparti_map_all.items():
        logging.info(f"[DEBUG] Workspace {ws_id} → {len(ws_map)} controparti")
        logging.info(f"[DEBUG] Chiavi: {list(ws_map.keys())}")

    logging.info("=== FINE DEBUG CONTROPARTI ===\n")
