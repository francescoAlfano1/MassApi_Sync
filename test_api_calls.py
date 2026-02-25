import logging
import random
import json
from datetime import datetime
import requests
import os

from functions.http_requests import get_request, put_request, post_request

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("=== AVVIO test_api_calls.py ===")

# ============================================================
# CONFIGURAZIONE API
# ============================================================
ENDPOINT = "https://api-demo.contractgeek.it"
API_KEY = "YOUR_API_KEY"
ORGANIZATION_ID = "YOUR_ORGANIZATION_ID"

HEADERS = {
    "X-api-key": API_KEY,
    "Organization-ID": ORGANIZATION_ID,
    "Workspace-ID": "0",   # GET globali
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ============================================================
# UTILITY
# ============================================================
def safe_json(response):
    if not response:
        logging.error("safe_json: response è None")
        return None
    try:
        return response.json()
    except Exception as e:
        logging.error(f"Errore parsing JSON: {e}")
        return None


def load_workspace_map():
    """
    Carica workspace_map.json dalla cartella /data
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(base_dir, "data", "workspace_map.json")

    try:
        with open(map_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Errore caricamento workspace_map.json: {e}")
        return {}


# ============================================================
# CHECK ENDPOINT
# ============================================================
def check_endpoint():
    url = f"{ENDPOINT}/ping"
    logging.info(f"Verifica raggiungibilità endpoint: {url}")
    try:
        r = requests.get(url, timeout=15)
        logging.info(f"Ping status: {r.status_code}, body: {r.text}")
        return r.status_code == 200
    except Exception as e:
        logging.error(f"Endpoint non raggiungibile: {e}")
        return False


# ============================================================
# GET CONTROPARTI
# ============================================================
def fetch_all_clients():
    url = f"{ENDPOINT}/Controparte"
    response = get_request(url, HEADERS, timeout=15)

    if response and response.status_code == 200:
        clients = safe_json(response) or []
        logging.info(f"Recuperate {len(clients)} controparti.")
        return clients

    logging.error(f"GET Controparti fallita. Status: {response.status_code if response else 'None'}")
    return []


# ============================================================
# GET FIRMATARI
# ============================================================
def fetch_all_users():
    url = f"{ENDPOINT}/Controparte/User"
    response = get_request(url, HEADERS, timeout=15)

    if response and response.status_code == 200:
        users = safe_json(response) or []
        logging.info(f"Recuperati {len(users)} firmatari.")
        return users

    logging.error(f"GET Users fallita. Status: {response.status_code if response else 'None'}")
    return []


# ============================================================
# POST CONTROPARTE
# ============================================================
def test_post_client():
    random_num = random.randint(1000, 9999)
    new_client = {
        "controparte_id": 0,
        "controparte_name": f"Test Controparte {random_num}",
        "controparte_nation": "Italia",
        "controparte_city": "Roma",
        "controparte_mail": f"test_client_{random_num}@example.com",
        "controparte_last_edit": datetime.utcnow().isoformat() + "Z",
        "controparte_piva": f"{random_num}1234567",
        "controparte_type": 0,
    }

    url = f"{ENDPOINT}/Controparte"
    response = post_request(url, headers=HEADERS, json=new_client, timeout=15)

    if response and response.status_code in (200, 201):
        created = safe_json(response)
        logging.info(f"Controparte creata con ID {created.get('controparte_id')}")
        return created

    logging.error(f"POST fallito. Status: {response.status_code if response else 'None'}")
    return None


# ============================================================
# PUT CONTROPARTI RANDOM
# ============================================================
def test_put_clients(clients, n=2):
    if not clients:
        logging.warning("Nessuna controparte trovata.")
        return

    sample = random.sample(clients, min(n, len(clients)))

    for client in sample:
        client_id = client.get("controparte_id")
        if not client_id:
            continue

        payload = {
            "controparte_id": client_id,
            "controparte_name": client.get("controparte_name", ""),
            "controparte_last_edit": datetime.utcnow().isoformat() + "Z",
        }

        url = f"{ENDPOINT}/Controparte"
        response = put_request(url, headers=HEADERS, json=payload, timeout=15)

        if response and response.status_code in (200, 204):
            logging.info(f"PUT riuscito per cliente {client_id}")
        else:
            logging.error(f"PUT fallito per cliente {client_id}")


# ============================================================
# PUT INTERATTIVO CONTROPARTE
# ============================================================
def test_put_single_client():
    print("\n=== MODIFICA CONTROPARTE (PUT) ===")

    clients = fetch_all_clients()
    if not clients:
        print("Nessuna controparte trovata.")
        return

    print("\nSeleziona la controparte da modificare:")
    for i, c in enumerate(clients[:20]):
        print(f"{i+1}) {c['controparte_name']} (ID {c['controparte_id']})")

    try:
        scelta = int(input("\nNumero controparte: ")) - 1
        client = clients[scelta]
    except Exception:
        print("Selezione non valida.")
        return

    client_id = client["controparte_id"]

    print("\nCampi modificabili:")
    print("1) Nome")
    print("2) Città")
    print("3) Email")
    print("4) PEC")
    print("5) Indirizzo")
    print("6) Telefono")

    campo = input("\nCampo da modificare: ").strip()
    nuovo_valore = input("Nuovo valore: ").strip()

    payload = {
        "controparte_id": client_id,
        "controparte_name": client.get("controparte_name", ""),
        "controparte_nation": client.get("controparte_nation", "Italia"),
        "controparte_city": client.get("controparte_city", ""),
        "controparte_mail": client.get("controparte_mail", ""),
        "controparte_pec": client.get("controparte_pec", ""),
        "controparte_address": client.get("controparte_address", ""),
        "controparte_phone": client.get("controparte_phone", ""),
        "controparte_last_edit": datetime.utcnow().isoformat() + "Z",
        "controparte_piva": client.get("controparte_piva", ""),
        "controparte_webpage": client.get("controparte_webpage", ""),
        "controparte_type": client.get("controparte_type", 0),
        "controparte_cf": client.get("controparte_cf", None)
    }

    if campo == "1":
        payload["controparte_name"] = nuovo_valore
    elif campo == "2":
        payload["controparte_city"] = nuovo_valore
    elif campo == "3":
        payload["controparte_mail"] = nuovo_valore
    elif campo == "4":
        payload["controparte_pec"] = nuovo_valore
    elif campo == "5":
        payload["controparte_address"] = nuovo_valore
    elif campo == "6":
        payload["controparte_phone"] = nuovo_valore
    else:
        print("Campo non valido.")
        return

    print("\n=== PAYLOAD INVIATO ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    conferma = input("\nProcedere con il PUT? (s/n): ").strip().lower()
    if conferma != "s":
        print("Annullato.")
        return

    url = f"{ENDPOINT}/Controparte"
    response = put_request(url, headers=HEADERS, json=payload, timeout=15)

    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")


# ============================================================
# POST FIRMATARIO EXTERNAL
# ============================================================
def test_post_external_user():
    print("\n=== CREAZIONE FIRMATARIO EXTERNAL ===")

    name = input("Nome: ").strip()
    surname = input("Cognome: ").strip()

    random_num = random.randint(1000, 9999)
    email = f"{name.lower()}.{surname.lower()}{random_num}@example.com"

    clients = fetch_all_clients()
    if not clients:
        print("Nessuna controparte trovata.")
        return

    print("\nSeleziona una controparte:")
    for i, c in enumerate(clients[:10]):
        print(f"{i+1}) {c['controparte_name']} (ID {c['controparte_id']})")

    try:
        scelta = int(input("\nNumero controparte: ")) - 1
        cont_id = clients[scelta]["controparte_id"]
    except Exception:
        print("Selezione non valida.")
        return

    payload = {
        "user_id": 0,
        "mail": email,
        "name": name,
        "surname": surname,
        "phone": "3331234567",
        "cf": "RSSMRA80A01H501Z",
        "controparte_ids": [cont_id],
        "metadata": "{\"sync\":\"manual_test\"}"
    }

    print("\n=== PAYLOAD ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    conferma = input("\nProcedere con POST? (s/n): ").strip().lower()
    if conferma != "s":
        print("Annullato.")
        return

    url = f"{ENDPOINT}/Controparte/User"
    response = post_request(url, headers=HEADERS, json=payload, timeout=15)

    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")


# ============================================================
# PUT FIRMATARIO
# ============================================================
def test_put_single_user():
    print("\n=== MODIFICA FIRMATARIO (PUT) ===")

    users = fetch_all_users()
    if not users:
        print("Nessun firmatario trovato.")
        return

    print("\nSeleziona il firmatario:")
    for i, u in enumerate(users[:20]):
        print(f"{i+1}) {u.get('name')} {u.get('surname')} - {u.get('mail')} (ID {u.get('user_id')})")

    try:
        scelta = int(input("\nNumero firmatario: ")) - 1
        user = users[scelta]
    except Exception:
        print("Selezione non valida.")
        return

    print("\nCampi modificabili:")
    print("1) Nome")
    print("2) Cognome")
    print("3) Email")
    print("4) Telefono")
    print("5) Codice fiscale")

    campo = input("\nCampo da modificare: ").strip()
    nuovo_valore = input("Nuovo valore: ").strip()

    payload = {
        "id": user.get("user_id"),
        "mail": user.get("mail", ""),
        "name": user.get("name", ""),
        "surname": user.get("surname", ""),
        "phone": user.get("phone", ""),
        "cf": user.get("cf", ""),
        # niente controparte_ids nel PUT
        "metadata": "{\"sync\":\"manual_test_put\"}"
    }

    if campo == "1":
        payload["name"] = nuovo_valore
    elif campo == "2":
        payload["surname"] = nuovo_valore
    elif campo == "3":
        payload["mail"] = nuovo_valore
    elif campo == "4":
        payload["phone"] = nuovo_valore
    elif campo == "5":
        payload["cf"] = nuovo_valore
    else:
        print("Campo non valido.")
        return

    print("\n=== PAYLOAD ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    conferma = input("\nProcedere con PUT? (s/n): ").strip().lower()
    if conferma != "s":
        print("Annullato.")
        return

    url = f"{ENDPOINT}/Controparte/User"
    response = put_request(url, headers=HEADERS, json=payload, timeout=15)

    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")


# ============================================================
# POST AGGIUNTA CONTROPARTE A WORKSPACE (CON MAPPA)
# ============================================================
def test_add_client_to_workspace_with_map():
    print("\n=== AGGIUNTA CONTROPARTE A WORKSPACE ===")

    workspace_map = load_workspace_map()

    print("\nWorkspace disponibili:")
    for name, wid in workspace_map.items():
        print(f"{name} → ID {wid}")

    ws_name = input("\nInserisci workspace logico (es. 001): ").strip()

    if ws_name not in workspace_map:
        print("Workspace non trovato nella mappa.")
        return

    ws_id = workspace_map[ws_name]

    clients = fetch_all_clients()
    if not clients:
        print("Nessuna controparte trovata.")
        return

    print("\nSeleziona la controparte:")
    for i, c in enumerate(clients[:20]):
        print(f"{i+1}) {c['controparte_name']} (ID {c['controparte_id']})")

    scelta = int(input("\nNumero controparte: ")) - 1
    cont_id = clients[scelta]["controparte_id"]

    url = f"{ENDPOINT}/Controparte/{cont_id}/workspace/{ws_id}"

    print(f"\nInvio POST a: {url}")

    response = post_request(url, headers=HEADERS, timeout=15)

    print(f"Status: {response.status_code if response else 'None'}")
    print(f"Body: {response.text if response else 'None'}")


# ============================================================
# MENU INTERATTIVO
# ============================================================
if __name__ == "__main__":
    logging.info("=== AVVIO TEST API CALLS INTERATTIVO ===")

    if not check_endpoint():
        logging.critical("Endpoint non raggiungibile → stop")
        exit(1)

    while True:
        print("\nScegli un'operazione:")
        print("1) GET controparti")
        print("2) GET firmatari")
        print("3) POST nuova controparte")
        print("4) PUT controparti random")
        print("5) POST nuovo firmatario external")
        print("6) PUT modifica singola controparte")
        print("7) PUT modifica singolo firmatario")
        print("8) POST aggiungi controparte a workspace")
        print("9) Esci")

        scelta = input("\nNumero operazione: ").strip()

        if scelta == "1":
            fetch_all_clients()

        elif scelta == "2":
            fetch_all_users()

        elif scelta == "3":
            test_post_client()

        elif scelta == "4":
            clients = fetch_all_clients()
            test_put_clients(clients)

        elif scelta == "5":
            test_post_external_user()

        elif scelta == "6":
            test_put_single_client()

        elif scelta == "7":
            test_put_single_user()

        elif scelta == "8":
            test_add_client_to_workspace_with_map()

        elif scelta == "9":
            logging.info("Uscita dal test interattivo")
            break

        else:
            print("Scelta non valida.")
