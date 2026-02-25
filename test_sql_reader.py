import logging
import json
import csv
from functions.sql_reader import fetch_users, fetch_clients

# ---------------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("Avvio test sql_reader.py")

# ---------------------------------------------------------------------------------
# LETTURA FIRMATARI DAL DB
# ---------------------------------------------------------------------------------
# fetch_users() restituisce:
# {
#   "externals": [...],
#   "naturals": [...]
# }
#
# NOTA IMPORTANTE:
# La distinzione external/natural rimane SOLO a livello di sorgente dati.
# Nel flusso di sincronizzazione, TUTTI i firmatari vengono trattati come external.
# Questo test serve solo a verificare la qualità e la coerenza dei dati letti dal DB.
# ---------------------------------------------------------------------------------

users_dict = fetch_users()
externals = users_dict.get("externals", [])
naturals = users_dict.get("naturals", [])

# Ordino per cognome+nome per leggibilità
externals = sorted(externals, key=lambda x: (x.get('surname') or '', x.get('name') or ''))
naturals = sorted(naturals, key=lambda x: (x.get('surname') or '', x.get('name') or ''))

# ---------------------------------------------------------------------------------
# LETTURA CONTROPARTI DAL DB
# ---------------------------------------------------------------------------------
clients = fetch_clients()
clients = sorted(clients, key=lambda x: x['controparte_name'] or '')

# ---------------------------------------------------------------------------------
# SOMMARIO
# ---------------------------------------------------------------------------------
tot_controparti_ext = sum(len(u.get('controparti_keys', [])) for u in externals)

print("\n=== SOMMARIO FIRMATARI ===")
print(f"External totali: {len(externals)} (controparti collegate: {tot_controparti_ext})")
print(f"Natural totali: {len(naturals)}")   # ← FIX parentesi

print("\n=== SOMMARIO CONTROPARTI ===")
print(f"Controparti totali: {len(clients)}")

# ---------------------------------------------------------------------------------
# SALVATAGGIO RISULTATI COMPLETI IN JSON
# ---------------------------------------------------------------------------------
output_data = {
    "externals": externals,
    "naturals": naturals,
    "clients": clients
}

try:
    with open("data/output_sql_reader.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    logging.info("Risultati completi salvati in data/output_sql_reader.json")
except Exception as e:
    logging.error(f"Errore nel salvataggio del file JSON: {e}")

# ---------------------------------------------------------------------------------
# CSV EXTERNAL USERS
# ---------------------------------------------------------------------------------
# NOTA:
# Gli external sono quelli che nel flusso di sincronizzazione vengono gestiti come:
# - firmatari multi-controparti
# - multi-workspace
# - associati tramite controparti_keys
# ---------------------------------------------------------------------------------

try:
    with open("data/output_externals.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "name", "surname", "mail", "phone", "cf",
            "workspace_id", "workspace_logico", "controparti_keys"
        ])
        for u in externals:
            writer.writerow([
                u.get("name"),
                u.get("surname"),
                u.get("mail"),
                u.get("phone"),
                u.get("cf"),
                u.get("workspace_id"),
                u.get("workspace_logico", ""),  # ← aggiunto
                ";".join(u.get("controparti_keys", []))
            ])
    logging.info("Firmatari external salvati in data/output_externals.csv")
except Exception as e:
    logging.error(f"Errore nel salvataggio CSV external: {e}")

# ---------------------------------------------------------------------------------
# CSV NATURAL USERS
# ---------------------------------------------------------------------------------
# NOTA:
# Anche se i natural vengono trattati come external nel flusso di sincronizzazione,
# qui manteniamo la distinzione per verificare la sorgente dati.
# ---------------------------------------------------------------------------------

try:
    with open("data/output_naturals.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "name", "surname", "mail", "phone", "cf",
            "workspace_id", "workspace_logico"
        ])
        for u in naturals:
            writer.writerow([
                u.get("name"),
                u.get("surname"),
                u.get("mail"),
                u.get("phone"),
                u.get("cf"),
                u.get("workspace_id"),
                u.get("workspace_logico", "")  # ← aggiunto
            ])
    logging.info("Firmatari natural salvati in data/output_naturals.csv")
except Exception as e:
    logging.error(f"Errore nel salvataggio CSV natural: {e}")

# ---------------------------------------------------------------------------------
# CSV CONTROPARTI
# ---------------------------------------------------------------------------------
# NOTA:
# Le controparti ora sono multi-workspace.
# workspace_id è già tradotto tramite workspace_map.json.
# key è la chiave logica (PIVA/CF).
# ---------------------------------------------------------------------------------

try:
    with open("data/output_clients.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "controparte_name", "controparte_piva", "controparte_cf",
            "controparte_city", "controparte_address",
            "workspace_id", "workspace_logico", "key"
        ])
        for c in clients:
            writer.writerow([
                c.get("controparte_name"),
                c.get("controparte_piva"),
                c.get("controparte_cf"),
                c.get("controparte_city"),
                c.get("controparte_address"),
                c.get("workspace_id"),
                c.get("workspace_logico", ""),  # ← aggiunto
                c.get("key")
            ])
    logging.info("Controparti salvate in data/output_clients.csv")
except Exception as e:
    logging.error(f"Errore nel salvataggio CSV controparti: {e}")

# ---------------------------------------------------------------------------------
# COMPLETAMENTO
# ---------------------------------------------------------------------------------
logging.info("Test sql_reader completato.")
