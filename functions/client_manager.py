import os
import json
import logging
import time
from functions.http_requests import get_request, post_request, put_request
# import functions.logger_setup as logger_setup # A REGIME LANCIATO IL MAIN QUESTO VA RIMOSSO, PER TESTARE I FILE DI TEST SINGOLI INVECE SERVE
from datetime import datetime

# Inizializzo il logging centralizzato 
# logger_setup.setup_logging(log_folder="log")  # A REGIME LANCIATO IL MAIN QUESTO VA RIMOSSO, PER TESTARE I FILE DI TEST SINGOLI INVECE SERVE

# ==============================================================================
# FILE: client_manager.py
# SCOPO:
#   Gestione completa della sincronizzazione delle controparti (clienti)
#   tra database locale e Contract Geek, con logica multi-workspace.
#
# VERSIONE:
#   Dicembre 2025 — Versione definitiva con:
#     • struttura finale controparti (record + workspaces)
#     • workspace logici → workspace API tramite workspace_map.json
#     • GET controparti per workspace
#     • POST/PUT controparti per workspace
#     • aggiunta ai workspace mancanti
#     • mappa finale controparti compatibile con signer_manager
#     • commenti estesi per massima leggibilità
#
# NOTA IMPORTANTE:
#   Le controparti NON usano Workspace-ID = "0".
#   Ogni operazione (GET/POST/PUT) deve essere fatta nel workspace specifico.
#
#   Workspace-ID = "0" è usato solo per:
#       • GET /Organization/Workspace
#       • GET /Controparte/User (nel signer_manager)
# ==============================================================================



# ==============================================================================
# 1. COSTRUZIONE CHIAVE LOGICA CONTROPARTE
# ==============================================================================

def _build_key(record: dict) -> str | None:
    """
    Costruisce la chiave logica per identificare una controparte.
    Priorità:
        1. PIVA valida
        2. CF valido
    """
    piva = (record.get("controparte_piva") or "").strip()
    cf = (record.get("controparte_cf") or "").strip()

    if piva and piva != "00000000000":
        return piva
    elif cf and not cf.startswith("000000"):
        return cf
    else:
        return None



# ==============================================================================
# 2. CARICAMENTO WORKSPACE MAP (logico → API)
# ==============================================================================

def load_workspace_map():
    """
    Carica il file workspace_map.json dalla cartella ../data.
    Serve per convertire workspace logici → workspace_id API.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))  # .../functions
    map_path = os.path.join(base_dir, "..", "data", "workspace_map.json")

    try:
        with open(map_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Errore nel caricamento della mappa workspace: {e}")
        return {}



# ==============================================================================
# 3. RAGGRUPPAMENTO CONTROPARTI (STRUTTURA FINALE)
# ==============================================================================

def group_clients_by_key(clients: list) -> dict:
    """
    Raggruppa i record della sorgente dati per controparte (PIVA/CF)
    e raccoglie tutti i workspace API associati.

    OUTPUT:
        {
            "PIVA/CF": {
                "record": {...},
                "workspaces": ["478", "480", ...]
            }
        }
    """
    grouped = {}

    for c in clients:
        key = _build_key(c)
        if not key:
            continue

        ws = str(c.get("workspace_id")).strip()

        if key not in grouped:
            clean_record = {
                k: v for k, v in c.items()
                if k not in ("workspace_id", "workspace_logico")
            }

            grouped[key] = {
                "record": clean_record,
                "workspaces": set()
            }

        grouped[key]["workspaces"].add(ws)

    # Convert set → list
    for key in grouped:
        grouped[key]["workspaces"] = list(grouped[key]["workspaces"])

    return grouped


# ==============================================================================
# 4. RAGGRUPPAMENTO FIRMATARI (PER SIGNER MANAGER)
# ==============================================================================
def group_users_by_key(users: dict) -> dict:
    """
    Raggruppa i firmatari per chiave logica (mail|CF),
    unisce correttamente tutte le controparti_keys
    e costruisce un record pulito e coerente per sync_external_signer().
    """

    grouped = {}
    all_users = users["externals"] + users["naturals"]

    for u in all_users:
        mail = (u.get("mail") or "").strip().lower()
        cf = (u.get("cf") or "").strip()
        key = f"{mail}|{cf}"

        if not mail:
            # senza mail non può esistere un firmatario
            continue

        cont_keys = u.get("controparti_keys", []) or []

        # Primo inserimento
        if key not in grouped:
            grouped[key] = {
                "record": {
                    "mail": mail,
                    "name": u.get("name", ""),
                    "surname": u.get("surname", ""),
                    "phone": u.get("phone", ""),
                    "cf": cf,
                    "metadata": u.get("metadata", '{"sync":"auto"}'),
                    "controparti_keys": list(cont_keys)
                }
            }

        else:
            # Unione controparti_keys
            existing = grouped[key]["record"].get("controparti_keys", [])
            merged = list(set(existing + cont_keys))
            grouped[key]["record"]["controparti_keys"] = merged

    return grouped




# ==============================================================================
# 5. FUNZIONI DI SUPPORTO MULTI-WORKSPACE
# ==============================================================================

def get_workspaces_for_client(key: str, controparti_map_all: dict) -> list:
    """
    Restituisce la lista dei workspace_id API in cui la controparte è già presente.
    """
    result = []
    for ws_id, cont_map in controparti_map_all.items():
        if key in cont_map:
            result.append(ws_id)
    return result



def ensure_client_in_all_workspaces(
    cont_id: int,
    key: str,
    required_ws_ids: list,
    controparti_map_all: dict,
    endpoint: str,
    headers: dict
):
    """
    Garantisce che la controparte sia presente in TUTTI i workspace richiesti.
    Se manca in un workspace → POST /Controparte/{id}/workspace/{ws}
    """
    existing_ws = get_workspaces_for_client(key, controparti_map_all)

    for ws_id in required_ws_ids:
        if ws_id not in existing_ws:
            logging.info(f"[WS {ws_id}] Aggiungo controparte {cont_id} al workspace")

            ok = add_client_to_workspace(cont_id, ws_id, endpoint, headers)

            if ok:
                if ws_id not in controparti_map_all:
                    controparti_map_all[ws_id] = {}

                controparti_map_all[ws_id][key] = [cont_id]



# ==============================================================================
# 6. CARICAMENTO WORKSPACE E CONTROPARTI REMOTE
# ==============================================================================

def load_workspaces(endpoint: str, headers: dict, organization_id: str) -> list:
    """
    Recupera la lista di tutti i workspace disponibili per l'organizzazione.
    Workspace-ID = "0" → visione globale.
    """
    url = f"{endpoint}/Organization/Workspace"
    hdrs = headers.copy()
    hdrs["Organization-ID"] = organization_id
    hdrs["Workspace-ID"] = "0"

    response = get_request(url, hdrs)

    if response and response.status_code == 200:
        workspaces = response.json()
        logging.info(f"Trovati {len(workspaces)} workspace disponibili.")
        return workspaces

    logging.error(f"Errore nel recupero workspace: {response.text if response else 'nessuna risposta'}")
    return []



def load_remote_controparti_per_workspace(endpoint: str, headers: dict, workspaces: list) -> dict:
    """
    Per ogni workspace recupero le controparti già presenti.
    OUTPUT:
        {
            "478": { "01379590357": [1111] },
            "480": { "01379590357": [1111] }
        }
    """
    result = {}

    for ws in workspaces:
        ws_id = str(ws["workspace_id"])
        ws_headers = headers.copy()
        ws_headers["Workspace-ID"] = ws_id

        url = f"{endpoint}/Controparte"
        response = get_request(url, ws_headers)

        cont_map = {}

        if response and response.status_code == 200:
            for c in response.json():
                key = _build_key(c)
                if not key:
                    logging.warning(f"[WS {ws_id}] Controparte senza identificativo valido: {c}")
                    continue

                if key in cont_map:
                    cont_map[key].append(c["controparte_id"])
                    logging.warning(
                        f"[WS {ws_id}] Duplicato rilevato per chiave {key}: {cont_map[key]}"
                    )
                else:
                    cont_map[key] = [c["controparte_id"]]
        else:
            logging.error(f"[WS {ws_id}] Errore GET /Controparte: {response.text if response else 'nessuna risposta'}")

        result[ws_id] = cont_map
        logging.info(f"[WS {ws_id}] Caricate {len(cont_map)} controparti uniche.")

    return result



# ==============================================================================
# 7. AGGIUNTA CONTROPARTE A WORKSPACE
# ==============================================================================

def add_client_to_workspace(cont_id: int, workspace_id: str, endpoint: str, headers: dict) -> bool:
    """
    Aggiunge una controparte già esistente ad un nuovo workspace.
    """
    ws_headers = headers.copy()
    ws_headers["Workspace-ID"] = str(workspace_id)

    url = f"{endpoint}/Controparte/{cont_id}/workspace/{workspace_id}"
    resp = post_request(url, headers=ws_headers, json={})

    if resp and resp.status_code == 201:
        logging.info(f"[WS {workspace_id}] Controparte {cont_id} aggiunta correttamente.")
        return True

    if resp and resp.status_code == 409:
        logging.info(f"[WS {workspace_id}] Controparte {cont_id} già presente.")
        return True

    if resp and resp.status_code == 403:
        logging.error(f"[WS {workspace_id}] 403 Forbidden aggiungendo controparte {cont_id}.")
        return False

    logging.error(f"[WS {workspace_id}] Errore aggiunta controparte {cont_id}: {resp.text if resp else 'nessuna risposta'}")
    return False


# ==============================================================================
# 8. SYNC DI UNA SINGOLA CONTROPARTE
# ==============================================================================

def sync_client(
    client_record: dict,
    controparti_map_all: dict,
    endpoint: str,
    headers: dict,
):
    record = client_record["record"]
    key = _build_key(record)

    if not key:
        return {
            "status": "error",
            "key": None,
            "name": record.get("controparte_name"),
            "cont_id": None,
            "added_ws": []
        }

    required_ws_ids = client_record["workspaces"]

    if not required_ws_ids:
        return {
            "status": "error",
            "key": key,
            "name": record.get("controparte_name"),
            "cont_id": None,
            "added_ws": []
        }

    existing_ws = get_workspaces_for_client(key, controparti_map_all)

    # ----------------------------------------------------------------------
    # CASO 1: CONTROPARTE GIÀ ESISTENTE
    # ----------------------------------------------------------------------
    if existing_ws:
        ws_id = existing_ws[0]
        cont_id = controparti_map_all[ws_id][key][0]

        ws_headers = headers.copy()
        ws_headers["Workspace-ID"] = ws_id

        payload = {
            "controparte_id": cont_id,
            "controparte_name": record.get("controparte_name", ""),
            "controparte_nation": "Italia",
            "controparte_city": record.get("controparte_city", ""),
            "controparte_mail": record.get("controparte_mail", ""),
            "controparte_pec": record.get("controparte_pec", ""),
            "controparte_address": record.get("controparte_address", ""),
            "controparte_phone": record.get("controparte_phone", ""),
            "controparte_last_edit": datetime.utcnow().isoformat() + "Z",
            "controparte_piva": record.get("controparte_piva", ""),
            "controparte_webpage": "",
            "controparte_type": 0,
            "controparte_cf": record.get("controparte_cf", None)
        }

        resp = put_request(f"{endpoint}/Controparte", headers=ws_headers, json=payload)

        added_ws = [ws for ws in required_ws_ids if ws not in existing_ws]

        ensure_client_in_all_workspaces(
            cont_id, key, required_ws_ids, controparti_map_all, endpoint, headers
        )

        return {
            "status": "updated",
            "key": key,
            "name": record.get("controparte_name"),
            "cont_id": cont_id,
            "added_ws": added_ws
        }

    # ----------------------------------------------------------------------
    # CASO 2: CONTROPARTE NUOVA
    # ----------------------------------------------------------------------
    first_ws = required_ws_ids[0]
    ws_headers = headers.copy()
    ws_headers["Workspace-ID"] = first_ws

    payload = {
        "controparte_id": 0,
        "controparte_name": record.get("controparte_name", ""),
        "controparte_nation": "Italia",
        "controparte_city": record.get("controparte_city", ""),
        "controparte_mail": record.get("controparte_mail", ""),
        "controparte_pec": record.get("controparte_pec", ""),
        "controparte_address": record.get("controparte_address", ""),
        "controparte_phone": record.get("controparte_phone", ""),
        "controparte_last_edit": datetime.utcnow().isoformat() + "Z",
        "controparte_piva": record.get("controparte_piva", ""),
        "controparte_webpage": "",
        "controparte_type": 0,
        "controparte_cf": record.get("controparte_cf", None)
    }

    resp = post_request(f"{endpoint}/Controparte", headers=ws_headers, json=payload)

    if not resp or resp.status_code not in (200, 201):
        return {
            "status": "error",
            "key": key,
            "name": record.get("controparte_name"),
            "cont_id": None,
            "added_ws": []
        }

    cont_id = resp.json().get("controparte_id")

    if first_ws not in controparti_map_all:
        controparti_map_all[first_ws] = {}

    controparti_map_all[first_ws][key] = [cont_id]

    ensure_client_in_all_workspaces(
        cont_id, key, required_ws_ids, controparti_map_all, endpoint, headers
    )

    return {
        "status": "created",
        "key": key,
        "name": record.get("controparte_name"),
        "cont_id": cont_id,
        "added_ws": required_ws_ids
    }


# ==============================================================================
# 9. SYNC COMPLETO DI TUTTE LE CONTROPARTI (CON SUMMARY)
# ==============================================================================
def sync_all_clients(clients: dict, endpoint: str, headers: dict, organization_id: str):

    logging.info("Carico la mappa workspace...")
    workspace_map = load_workspace_map()

    logging.info("Uso le controparti già raggruppate dal main...")
    grouped_clients = clients
    logging.info(f"Trovate {len(grouped_clients)} controparti uniche nella sorgente dati.")

    logging.info("Carico la lista dei workspace disponibili nell'organizzazione...")
    workspaces = load_workspaces(endpoint, headers, organization_id)

    logging.info("Carico le controparti remote per ogni workspace...")
    controparti_map_all = load_remote_controparti_per_workspace(endpoint, headers, workspaces)

    logging.info("Inizio sincronizzazione multi-workspace...")

    # ============================================================
    # SUMMARY STRUTTURATO
    # ============================================================
    summary = {
        "created": [],      # controparti nuove
        "updated": [],      # controparti aggiornate
        "added_ws": [],     # aggiunte a workspace mancanti
        "errors": []        # errori
    }

    for key, client_record in grouped_clients.items():
        try:
            start = time.perf_counter()
            result = sync_client(client_record, controparti_map_all, endpoint, headers)
            elapsed = time.perf_counter() - start

            # -------------------------
            # CONTROPARTE CREATA
            # -------------------------
            if result["status"] == "created":
                summary["created"].append({
                    "key": result["key"],
                    "name": result["name"],
                    "cont_id": result["cont_id"],
                    "workspaces": client_record["workspaces"]
                })

            # -------------------------
            # CONTROPARTE AGGIORNATA
            # -------------------------
            elif result["status"] == "updated":
                summary["updated"].append({
                    "key": result["key"],
                    "name": result["name"],
                    "cont_id": result["cont_id"]
                })

                # workspace aggiunti
                for ws in result["added_ws"]:
                    summary["added_ws"].append({
                        "key": result["key"],
                        "name": result["name"],
                        "workspace": ws
                    })

            # -------------------------
            # ERRORI
            # -------------------------
            else:
                summary["errors"].append(result)

            logging.debug(f"Durata sync_client per {key}: {elapsed:.2f} secondi")

        except Exception as e:
            msg = f"Errore durante la sincronizzazione della controparte {key}: {e}"
            logging.error(msg)
            summary["errors"].append({"key": key, "error": str(e)})

    logging.info("Sincronizzazione controparti completata.")

    # RITORNA ANCHE IL SUMMARY
    return controparti_map_all, summary


