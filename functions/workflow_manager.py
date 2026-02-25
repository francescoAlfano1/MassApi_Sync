import logging
import os
import json
from typing import Dict

from classes.Controparte import Controparte, ControparteUser
from classes.Workflow import Workflow
from classes.Data import SignBoxPlaceholder
from functions.file_manager import get_page_count, move_file
from functions.http_requests import get_request, post_request, put_request
from functions.setup import read_user_map, read_signbox_map  # read_signbox_map opzionale
from functions.tag_locator import generate_signbox_data_and_json  # nuova funzione OCR

# === CONFIGURAZIONE SWITCH: Se True, legge le coordinate da JSON, altrimenti usa direttamente il dict ===
USE_JSON_FILE = False

# === Impostazione cartella di log coordinate OCR accanto a main.py ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_COORDINATE_DIR = os.path.join(BASE_DIR, "logcoordinate")
os.makedirs(LOG_COORDINATE_DIR, exist_ok=True)

def get_workflow(endpoint: str, headers: Dict[str, str], workflow_id: int) -> Workflow:
    response = get_request(f"{endpoint}/Workflow/{workflow_id}", headers)
    return Workflow(response.json())


def create_workflow(endpoint: str, headers: Dict[str, str], controparte: int, filename: str, file_path: str) -> int:
    with open(file_path, "rb") as file:
        files = {"file": (filename, file)}
        response = post_request(f"{endpoint}/Workflow?controparte_id={controparte}", headers=headers, files=files)
        workflow_id = int(response.text)
        logging.info(f"Workflow {workflow_id} created for file {filename} on Contract Geek.")
        return workflow_id


def update_workflow(endpoint: str, headers: Dict[str, str], workflow: Workflow) -> None:
    headers["Content-Type"] = "application/json"
    put_request(f"{endpoint}/Workflow", headers, data=workflow.to_json())
    headers.pop("Content-Type")
    logging.info(f"Workflow {workflow.workflow_id} updated")


def start_workflow(endpoint: str, headers: Dict[str, str], workflow_id: int) -> None:
    response = post_request(f"{endpoint}/Workflow/Start/{workflow_id}", headers)
    if response.status_code == 200:
        logging.info(f"Workflow {workflow_id} started successfully.")
    else:
        logging.error(f"Failed to start workflow {workflow_id}: {response.text}")


def get_controparti(endpoint: str, headers: Dict[str, str]) -> Dict[str, int]:
    response = get_request(f"{endpoint}/controparte", headers)
    controparti = [Controparte(data) for data in response.json()]
    return {
        controparte.get_dict_key_att(): controparte.controparte_id
        for controparte in controparti
    }


def get_controparte_user(endpoint: str, headers: Dict[str, str], controparte_id: int) -> list[ControparteUser]:
    response = get_request(f"{endpoint}/controparte/{controparte_id}/User", headers)
    return [ControparteUser(data) for data in response.json()]


def get_workspaces(endpoint: str, headers: Dict[str, str]) -> Dict[str, int]:
    response = get_request(f"{endpoint}/Organization/Workspace", headers)
    return {data["workspace_name"]: data["workspace_id"] for data in response.json()}


def validate_get_workspace(workspace: str, workspaces: Dict[str, int]) -> int:
    if workspace not in workspaces:
        raise ValueError(f"Invalid workspace: {workspace}")
    return workspaces[workspace]


def validate_get_controparte(controparte: str, controparti: Dict[str, int]) -> int:
    if controparte not in controparti:
        raise ValueError(f"Invalid controparte: {controparte}")
    return controparti[controparte]


def process_files(folder_path: str, destination_path: str, endpoint: str, headers: Dict[str, str]) -> None:
    try:
        controparti = get_controparti(endpoint, headers)
        workspaces = get_workspaces(endpoint, headers)
    except Exception as e:
        logging.error(f"Errore nel recupero di controparti o workspace: {e}")
        return

    user_map = read_user_map("data/user_map.json")

    # Ricava il nome del workspace dalla cartella di input
    workspace_name = os.path.basename(os.path.normpath(folder_path))

    for root, _dirs, files in os.walk(folder_path):
        for file in files:
            logging.info(f"Processing file: {file}")
            if not file.lower().endswith(".pdf"):
                logging.warning(f"Skipping non-PDF file: {file}")
                continue

            try:
                relative_path = os.path.relpath(root, folder_path).split(os.sep)
                if len(relative_path) != 2:
                    logging.warning(f"Invalid Path: {root}")
                    continue

                controparte, tipodoc = relative_path
                workspace_id = validate_get_workspace(workspace_name, workspaces)
                controparte_id = validate_get_controparte(controparte, controparti)

                abspath = os.path.join(root, file).replace("\\", "/")
                headers["Workspace-ID"] = str(workspace_id)
                final_filename = f"{file}_{tipodoc}.pdf"

                workflow_id = create_workflow(endpoint, headers, controparte_id, final_filename, abspath)
                controparte_users = get_controparte_user(endpoint, headers, controparte_id)

                if not controparte_users:
                    logging.warning(
                        f"Controparte {controparte} has 0 associated users.\nBlocked process for Workflow {workflow_id}:{final_filename}"
                    )
                    continue

                workflow = get_workflow(endpoint, headers, workflow_id)
                document_id = workflow.workflow_documents[0].document_id
                get_page_count(abspath)  # Solo per forzare la lettura

                has_error = False
                try:
                    workflow.add_approver(user_map[workspace_name])
                except KeyError:
                    logging.warning(
                        f'Workspace {workspace_name} does not have an associated approver.\nWorkflow {workflow_id}:{final_filename} left in "Bozza" Status'
                    )
                    has_error = True

                # === OCR: GENERAZIONE COORDINATE FIRME ===
                try:
                    json_path, ocr_box_map = generate_signbox_data_and_json(
                        abspath,
                        tags=["@@firmacna@@", "@@firmacliente@@"],
                        output_dir="data/ocr_debug",
                        debug_folder=None,
                        write_file=USE_JSON_FILE
                    )

                    # Usa JSON o dict direttamente in base a switch
                    box_map = read_signbox_map(json_path) if USE_JSON_FILE else ocr_box_map

                    # --- LOGGING coordinate su file dedicato ---
                    log_file_path = os.path.join(LOG_COORDINATE_DIR, f"{os.path.splitext(file)[0]}_coordinates.log")
                    with open(log_file_path, "w", encoding="utf-8") as log_f:
                        log_f.write(f"Coordinate OCR generate per il file {file}:\n")
                        json.dump(box_map, log_f, indent=4, ensure_ascii=False)

                    logging.info(f"Coordinate OCR generate e salvate su log per il file {file}")

                except Exception as e:
                    logging.error(f"Errore nella generazione delle coordinate OCR: {e}")
                    box_map = {}

                    # Scriviamo l'errore anche nel file di log coordinate
                    log_file_path = os.path.join(LOG_COORDINATE_DIR, f"{os.path.splitext(file)[0]}_coordinates.log")
                    with open(log_file_path, "w", encoding="utf-8") as log_f:
                        log_f.write(f"Errore nella generazione delle coordinate OCR per il file {file}:\n{str(e)}\n")

                # === APPLICAZIONE DEI BOX DI FIRMA ===
                # === APPLICAZIONE DEI BOX DI FIRMA ORDINATI ===
                try:
                    # Ordina le chiavi: prima @@firmacna@@, poi tutte le altre
                    ordered_keys = sorted(box_map.keys(), key=lambda k: 0 if k.lower() == "@@firmacna@@" else 1)

                    for key in ordered_keys:
                        if key == "_pdf_source":
                            continue

                        value = box_map[key]
                        items = value if isinstance(value, list) else [value]

                        for p in items:
                            page = p.get("pag") if isinstance(p, dict) else getattr(p, "pag", None)
                            placeholder_dict = {k: v for k, v in (p if isinstance(p, dict) else vars(p)).items() if k != "pag"}

                            try:
                                placeholder_obj = SignBoxPlaceholder(**placeholder_dict)
                            except Exception as e:
                                logging.error(f"Errore nella creazione del SignBoxPlaceholder: {e}")
                                continue

                            normalized_key = key.lower()
                            CNA_SIGNER_ROLE = os.environ.get("CNA_SIGNER_ROLE", "YOUR_SIGNER_ROLE_KEY")

                            target_user = user_map[CNA_SIGNER_ROLE] if normalized_key == "@@firmacna@@" else controparte_users[0].id

                            logging.info(f"Chiave placeholder: '{key}', user target: {target_user}")

                            workflow.add_signbox_from_placeholder(
                                document_id,
                                target_user,
                                page,
                                placeholder_obj
                            )


                    # Imposta firma sequenziale
                    workflow.sequential_sign = True

                    # Imposta status_id = 2 se non ci sono errori (come nella vecchia versione)
                    if not has_error:
                        workflow.status_id = 2
                        # Aggiorna e avvia il workflow
                        update_workflow(endpoint, headers, workflow)
                        start_workflow(endpoint, headers, workflow.workflow_id)

                except Exception as e:
                    logging.error(f"Errore durante l'applicazione dei placeholder ordinati: {e}")

                # Sposta il file nella cartella di destinazione
                move_file(abspath, destination_path, final_filename)
                
                logging.info(f"Workflow {workflow_id} completato per il file {final_filename}")

            except Exception as e:
                logging.error(f"Errore nel processing del file {file}: {e}")
                continue

