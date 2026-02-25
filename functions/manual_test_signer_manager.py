import json
import time
import os
os.makedirs("logs", exist_ok=True)

from signer_manager import (
    load_remote_signers,
    sync_external_signer
)

from client_manager import (
    load_workspaces,
    load_remote_controparti_per_workspace
)

# =====================================================
# CONFIGURAZIONE API
# =====================================================
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

# =====================================================
# STRUTTURE DI TEST (FIRMATARI)
# =====================================================
TEST_SIGNERS = {
    "test.user@example.com|TSTCMP00A00A000A": {
        "record": {
            "mail": "test.user@example.com",
            "name": "Test",
            "surname": "User",
            "phone": "0000000000",
            "cf": "TSTCMP00A00A000A",
            "metadata": '{"note":"test manuale"}',
            "controparti_keys": ["00000000001", "00000000002", "TSTCMP00A00A000B"]
        }
    }
}

# =====================================================
# LOG FILE
# =====================================================
LOG_PATH = "logs/manual_test_signer_sync.log"

def write_log(lines):
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

# =====================================================
# ESECUZIONE TEST
# =====================================================
if __name__ == "__main__":
    log = []
    log.append("=== TEST SINCRONIZZAZIONE FIRMATARI ===")

    # 1️⃣ Carico firmatari remoti
    remote_signers = load_remote_signers(ENDPOINT, HEADERS)
    log.append(f"Firmatari remoti iniziali: {len(remote_signers)}")

    # 2️⃣ Carico controparti multi-workspace
    workspaces = load_workspaces(ENDPOINT, HEADERS, ORGANIZATION_ID)
    controparti_map_all = load_remote_controparti_per_workspace(ENDPOINT, HEADERS, workspaces)
    controparti_map_all = {str(k): v for k, v in controparti_map_all.items()}

    # 3️⃣ Sincronizzo ogni firmatario definito nel test
    for key, data in TEST_SIGNERS.items():
        record = data["record"]
        signer_mail = record["mail"].strip().lower()

        log.append("\n" + "="*70)
        log.append(f"--- SINCRONIZZAZIONE FIRMATARIO {record['mail']} ---")
        log.append("="*70)

        log.append(f"Controparti richieste: {record['controparti_keys']}")

        # Risoluzione controparti (solo diagnostica)
        resolved_ids = {}
        for cont_key in record["controparti_keys"]:
            cid = None
            for ws_map in controparti_map_all.values():
                if cont_key in ws_map:
                    cid = ws_map[cont_key][0]
                    break
            resolved_ids[cont_key] = cid

        log.append(f"ID controparti risolti: {resolved_ids}")

        missing = [k for k, v in resolved_ids.items() if v is None]
        if missing:
            log.append(f"⚠ Controparti non trovate: {missing}")

        # Stato prima della sync
        before = remote_signers.get(signer_mail)
        if before:
            log.append(f"Stato PRIMA: ID={before['user_id']}, controparti={before['controparti_ids']}")
        else:
            log.append("Stato PRIMA: firmatario NON presente")

        # 3️⃣ Sincronizzo il firmatario
        start = time.perf_counter()
        remote_id = sync_external_signer(
            record_firmatario=record,
            remote_signers=remote_signers,
            controparti_map_all=controparti_map_all,
            endpoint=ENDPOINT,
            headers=HEADERS
        )
        elapsed = time.perf_counter() - start

        # 🔄 Ricarico firmatari remoti e controparti
        remote_signers = load_remote_signers(ENDPOINT, HEADERS)
        controparti_map_all = load_remote_controparti_per_workspace(ENDPOINT, HEADERS, workspaces)
        controparti_map_all = {str(k): v for k, v in controparti_map_all.items()}

        # Stato dopo la sync
        after = remote_signers.get(signer_mail)
        if after:
            log.append(f"Stato DOPO: ID={after['user_id']}, controparti={after['controparti_ids']}")
        else:
            log.append("Stato DOPO: firmatario NON presente (ERRORE)")

        # Differenze
        if before and after:
            added = set(after["controparti_ids"]) - set(before["controparti_ids"])
            removed = set(before["controparti_ids"]) - set(after["controparti_ids"])
            if added:
                log.append(f"  ➕ Controparti aggiunte: {list(added)}")
            if removed:
                log.append(f"  ➖ Controparti rimosse: {list(removed)}")

        if remote_id:
            log.append(f"  ✔ Firmatario sincronizzato con ID {remote_id}")
        else:
            log.append(f"  ✘ Errore nella sync del firmatario {record['mail']}")

        log.append(f"Durata operazione: {elapsed:.2f}s")

    # 4️⃣ Scrivo log finale
    write_log(log)
    print("\n=== TEST COMPLETATO ===")
    print(f"Log generato in: {LOG_PATH}")