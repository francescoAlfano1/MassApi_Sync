import os
import logging
from functions.setup import read_config, check_params, setup_logging, api_check, params
from functions.workflow_manager import process_files
from functions.http_requests import get_request

def get_dynamic_workspaces(params, headers):
    """
    Legge le cartelle di primo livello nel folder_path e associa a ciascuna
    il workspace_id corrispondente ottenuto via API.
    
    Restituisce un dizionario {workspace_name: workspace_id} per i workspace validi.
    """
    folder_path = params.get("folder_path")
    endpoint = params.get("endpoint")

    if not folder_path or not os.path.exists(folder_path):
        logging.error(f"Percorso cartella input non valido: {folder_path}")
        return {}

    # --- Recupera tutti i workspace disponibili via API
    try:
        response = get_request(f"{endpoint}/Organization/Workspace", headers)
        all_workspaces = {
            data["workspace_name"]: data["workspace_id"]
            for data in response.json()
        }
        logging.info(f"Workspaces disponibili sul portale: {list(all_workspaces.keys())}")
    except Exception as e:
        logging.error(f"Errore nel recupero dei workspace dal server: {e}")
        return {}

    # --- Scansiona le sottocartelle locali (workspace)
    local_dirs = [
        d for d in os.listdir(folder_path)
        if os.path.isdir(os.path.join(folder_path, d))
    ]
    logging.info(f"Workspaces trovati localmente: {local_dirs}")

    # --- Crea mappa dei workspace validi
    valid_workspaces = {}
    for subfolder in local_dirs:
        if subfolder in all_workspaces:
            valid_workspaces[subfolder] = all_workspaces[subfolder]
            logging.info(f"Workspace '{subfolder}' riconosciuto (ID {all_workspaces[subfolder]})")
        else:
            logging.warning(f"Workspace locale '{subfolder}' non trovato tra quelli dell'organizzazione. Ignorato.")

    if not valid_workspaces:
        logging.warning("Nessun workspace locale corrisponde a un workspace valido sul server.")

    return valid_workspaces



if __name__ == "__main__":
    params.update(read_config('data/config.json'))
  
    setup_logging(params['file_log_path'])
    
    headers = {
        'X-api-key': params['api_key'],
        'Organization-ID': params['organization_id'],
        'Workspace-ID': params['workspace_id']
    }

    check_params()
    api_check(params['endpoint'], headers)

    # === Ricava workspaces dinamici dalle cartelle ===
    valid_workspaces = get_dynamic_workspaces(params, headers)
    if not valid_workspaces:
        logging.error("Nessun workspace valido trovato. Terminazione script.")
        exit(1)

    # === Ciclo multi-workspace ===
    for ws_name, ws_id in valid_workspaces.items():
        try:
            logging.info("=" * 70)
            logging.info(f"Avvio elaborazione per workspace: {ws_name} (ID {ws_id})")
            logging.info("=" * 70)

            # Imposta dinamicamente il workspace per le chiamate successive
            params["workspace_id"] = ws_id
            headers["Workspace-ID"] = str(ws_id)

            ws_folder_path = os.path.join(params["folder_path"], ws_name)
            logging.info(f"Cartella di lavoro: {ws_folder_path}")

            # Elabora i file nel workspace
            process_files(ws_folder_path, params["destination_path"], params["endpoint"], headers)

        except Exception as e:
            logging.error(f"Errore durante l'elaborazione del workspace '{ws_name}': {e}")
            continue

    logging.info("Tutti i workspace locali sono stati elaborati con successo.")
