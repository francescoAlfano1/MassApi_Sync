import json
import time
import os
os.makedirs("logs", exist_ok=True)
from client_manager import (
    load_workspaces,
    load_remote_controparti_per_workspace,
    sync_client
)

ENDPOINT = os.environ.get("API_ENDPOINT", "https://api.example.com")
API_KEY = os.environ.get("API_KEY", "YOUR_API_KEY")
ORGANIZATION_ID = os.environ.get("ORGANIZATION_ID", "YOUR_ORGANIZATION_ID")

HEADERS = {
    "X-api-key": API_KEY,
    "Organization-ID": ORGANIZATION_ID,
    "Workspace-ID": "0",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

TEST_CONTROPARTI = {
    "00000000000": {
        "record": {
            "controparte_name": "test_company",
            "controparte_piva": "00000000000",
            "controparte_cf": "TSTCMP00A00A000A",
            "controparte_city": "Test City",
            "controparte_address": "Via Test 1",
            "controparte_mail": "test@example.com",
            "controparte_pec": "",
            "controparte_phone": "0000000000"
        },
        "workspaces": ["111", "222", "333"]
    }
}

LOG_PATH = "logs/manual_test_client_sync.log"

def write_log(lines):
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

if __name__ == "__main__":
    log = []
    log.append("=== TEST SINCRONIZZAZIONE CONTROPARTI ===")

    # 1️⃣ Carico TUTTI i workspace
    all_ws = load_workspaces(ENDPOINT, HEADERS, ORGANIZATION_ID)

    # 2️⃣ Carico controparti remote per TUTTI i workspace
    controparti_map = load_remote_controparti_per_workspace(ENDPOINT, HEADERS, all_ws)

    # 3️⃣ Sincronizzo ogni controparte
    for key, data in TEST_CONTROPARTI.items():
        record = data["record"]
        target_ws_ids = data["workspaces"]

        log.append(f"\n--- Sincronizzazione {key} ---")
        log.append(f"Workspace ID reali: {target_ws_ids}")

        client_payload = {
            "record": record,
            "workspaces": target_ws_ids
        }

        result = sync_client(
            client_payload,
            controparti_map,
            ENDPOINT,
            HEADERS
        )

        log.append(f"  Stato: {result['status']}")
        log.append(f"  Controparte: {result['key']} ({result['name']})")
        log.append(f"  ID remoto: {result['cont_id']}")

        if result["added_ws"]:
            log.append("  Aggiunta ai workspace:")
            for ws in result["added_ws"]:
                log.append(f"    → WS {ws}")

        if result["status"] == "error":
            log.append("  ✘ Errore nella sincronizzazione")

        # 🔄 Ricarico la mappa dopo ogni sync
        controparti_map = load_remote_controparti_per_workspace(ENDPOINT, HEADERS, all_ws)

    write_log(log)
    print("\n=== TEST COMPLETATO ===")
    print(f"Log generato in: {LOG_PATH}")