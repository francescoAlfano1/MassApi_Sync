import os
import sys
import json
import logging

# Aggiungo la cartella "functions" al path
sys.path.append(os.path.join(os.path.dirname(__file__), "functions"))

from functions.sql_reader import fetch_clients, fetch_users
from functions.client_manager import group_clients_by_key
from functions.signer_manager import group_users_by_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("Avvio test struttura finale controparti + firmatari")

# ---------------------------------------------------------
# 1. LETTURA DATI GREZZI DAL DB
# ---------------------------------------------------------
clients_raw = fetch_clients()
users_raw = fetch_users()

logging.info(f"Controparti grezze: {len(clients_raw)}")
logging.info(f"Firmatari grezzi: {len(users_raw['externals']) + len(users_raw['naturals'])}")

# ---------------------------------------------------------
# 2. COSTRUZIONE STRUTTURA FINALE CONTROPARTI
# ---------------------------------------------------------
final_clients = group_clients_by_key(clients_raw)
logging.info(f"Controparti logiche finali: {len(final_clients)}")

# ---------------------------------------------------------
# 3. COSTRUZIONE STRUTTURA FINALE FIRMATARI
# ---------------------------------------------------------
final_users = group_users_by_key(users_raw)
logging.info(f"Firmatari logici finali: {len(final_users)}")

# ---------------------------------------------------------
# 4. SALVATAGGIO STRUTTURA FINALE
# ---------------------------------------------------------
output = {
    "final_clients": final_clients,
    "final_users": final_users
}

try:
    os.makedirs("data", exist_ok=True)
    with open("data/output_final_structure.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logging.info("Struttura finale salvata in data/output_final_structure.json")
except Exception as e:
    logging.error(f"Errore nel salvataggio JSON: {e}")

# ---------------------------------------------------------
# 5. RIEPILOGO
# ---------------------------------------------------------
print("\n=== STRUTTURA FINALE CONTROPARTI ===")
for key, info in final_clients.items():
    print(f"- {key}: {info['record']['controparte_name']} → WS: {info['workspaces']}")

print("\n=== STRUTTURA FINALE FIRMATARI ===")
for key, info in final_users.items():
    rec = info["record"]
    print(f"- {rec['mail']} ({rec['cf']}) → Controparti: {rec['controparti_keys']}")

logging.info("Test struttura finale completato.")
