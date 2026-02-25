import os
import logging
from datetime import datetime

from functions.setup import read_config, api_check, params
from functions.sql_reader import fetch_users, fetch_clients
from functions.client_manager import sync_all_clients, group_clients_by_key
from functions.signer_manager import sync_all_signers, group_users_by_key
import functions.logger_setup as logger_setup


if __name__ == "__main__":

    # ---------------------------------------------------------
    # 1. CONFIGURAZIONE
    # ---------------------------------------------------------
    params.update(read_config("data/config.json"))

    db_config_path = os.path.join("data", "db_config.json")
    db_config = read_config(db_config_path)
    params["connection_string"] = db_config.get("connection_string")

    if not params.get("connection_string"):
        logging.error("Parametro 'connection_string' mancante in db_config.json")
        exit(1)

    # logger_setup.setup_logging(log_folder="log")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(BASE_DIR, "log")
    logger_setup.setup_logging(log_folder=log_path)


    headers = {
        "X-api-key": params["api_key"],
        "Organization-ID": params["organization_id"],
        "Workspace-ID": "0"   # workspace neutro per flusso firmatari
    }

    # ---------------------------------------------------------
    # 2. TEST API
    # ---------------------------------------------------------
    try:
        api_check(params["endpoint"], headers)
    except Exception:
        logging.error("Connessione API fallita", exc_info=True)
        exit(1)

    # ---------------------------------------------------------
    # 3. LETTURA ULTIMA SINCRONIZZAZIONE
    # ---------------------------------------------------------
    last_sync_file = "data/last_user_sync.txt"
    if os.path.exists(last_sync_file):
        with open(last_sync_file, "r") as f:
            last_sync = f.read().strip()
    else:
        last_sync = None

    logging.info(f"Ultima sincronizzazione: {last_sync or 'Nessuna (prima esecuzione)'}")

    # ---------------------------------------------------------
    # 4. LETTURA DATI DAL DB
    # ---------------------------------------------------------
    users_raw = fetch_users()      # {"externals": [...], "naturals": [...]}
    clients_raw = fetch_clients()  # lista controparti grezze

    if not clients_raw and not users_raw["externals"] and not users_raw["naturals"]:
        logging.info("Nessuna controparti o firmatari da sincronizzare.")
        exit(0)

    # ---------------------------------------------------------
    # 5. COSTRUZIONE STRUTTURA FINALE CONTROPARTI
    # ---------------------------------------------------------
    final_clients = group_clients_by_key(clients_raw)
    logging.info(f"Controparti logiche raggruppate: {len(final_clients)} elementi.")

    # ---------------------------------------------------------
    # 6. SINCRONIZZAZIONE CONTROPARTI
    # ---------------------------------------------------------
    try:
        logging.info(f"Inizio sincronizzazione di {len(final_clients)} controparti logiche...")
        controparti_map_all, summary_clients = sync_all_clients(
            final_clients,
            params["endpoint"],
            headers,
            params["organization_id"]
        )
        logging.info(
            f"Controparti sincronizzate. Workspace gestiti: {len(controparti_map_all)}"
        )
    except Exception:
        logging.error("Errore critico durante la sincronizzazione controparti", exc_info=True)
        logging.error("Interrompo il flusso: i firmatari NON verranno sincronizzati.")
        exit(1)


    # ---------------------------------------------------------
    # 7. COSTRUZIONE STRUTTURA FINALE FIRMATARI
    # ---------------------------------------------------------
    final_users = group_users_by_key(users_raw)
    logging.info(f"Firmatari logici raggruppati: {len(final_users)} elementi.")


    # ---------------------------------------------------------
    # 8. SINCRONIZZAZIONE FIRMATARI
    # ---------------------------------------------------------
    try:
        logging.info(
            f"Inizio sincronizzazione firmatari di {len(final_users)} chiavi logiche "
            f"({len(users_raw['externals'])} external, {len(users_raw['naturals'])} natural in origine)..."
        )

        remote_signers,summary_signers = sync_all_signers(
            final_users,
            controparti_map_all,
            params["endpoint"],
            headers
        )

        logging.info(f"Firmatari sincronizzati: {len(remote_signers)} elementi gestiti.")

    except Exception:
        logging.error("Errore durante la sincronizzazione firmatari", exc_info=True)

    # ---------------------------------------------------------
    # 9. AGGIORNAMENTO TIMESTAMP
    # ---------------------------------------------------------
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(last_sync_file, "w") as f:
        f.write(now_str)

    logging.info(f"Sincronizzazione completata alle {now_str} UTC")

    # ---------------------------------------------------------
    # 10. RIEPILOGO FINALE
    # ---------------------------------------------------------
    logging.info(
        f"Riepilogo finale: "
        f"{len(final_clients)} controparti logiche, "
        f"{len(users_raw['externals'])} external, "
        f"{len(users_raw['naturals'])} natural, "
        f"{len(final_users)} firmatari logici."
    )
    
    # ---------------------------------------------------------
    # 11. LOG RIEPILOGO FIRMATARI (SUMMARY)
    # ---------------------------------------------------------
    logging.info("===== RIEPILOGO FIRMATARI =====")

    logging.info(f"Creati: {len(summary_signers['created'])}")
    for s in summary_signers["created"]:
        logging.info(f"  + Creato: {s['mail']} (ID {s['user_id']})")

    logging.info(f"Aggiornati: {len(summary_signers['updated'])}")
    for s in summary_signers["updated"]:
        logging.info(f"  ~ Aggiornato: {s['mail']} (ID {s['user_id']})")

    logging.info(f"Associazioni: {len(summary_signers['associations'])}")
    for a in summary_signers["associations"]:
        logging.info(
            f"  ↔ {a.get('mail')} → {a.get('controparte_id') or a.get('controparte_key')} "
            f"(status: {a['status']})"
        )

    logging.info(f"Errori: {len(summary_signers['errors'])}")
    for e in summary_signers["errors"]:
        logging.error(f"  ! Errore per {e.get('mail')}: {e.get('error')}")
