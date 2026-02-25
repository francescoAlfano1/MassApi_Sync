import pyodbc
import logging
import json
import os
from typing import List, Dict
import datetime
import shutil

# ==============================================================================
# PATH ASSOLUTI BASATI SUL FILE CORRENTE (ROBUSTI PER VS CODE E PER RUN DA ROOT)
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "data"))

# ==============================================================================
# CARICAMENTO CONFIGURAZIONE DB
# ==============================================================================

db_config_path = os.path.join(DATA_DIR, "db_config.json")

try:
    with open(db_config_path, "r", encoding="utf-8") as f:
        db_config = json.load(f)
    CONNECTION_STRING = db_config.get("connection_string")
except Exception as e:
    logging.error(f"Errore nel caricamento di db_config.json: {e}")
    CONNECTION_STRING = None

# ==============================================================================
# CARICAMENTO WORKSPACE MAP
# ==============================================================================

workspace_map_path = os.path.join(DATA_DIR, "workspace_map.json")

try:
    with open(workspace_map_path, "r", encoding="utf-8") as f:
        WORKSPACE_MAP = json.load(f)
    logging.info("Mappa workspace caricata correttamente.")
except Exception as e:
    logging.error(f"Errore nel caricamento della mappa workspace: {e}")
    WORKSPACE_MAP = {}

# ==============================================================================
# LOG DIRECTORY (ASSOLUTA)
# ==============================================================================

LOG_ROOT = os.path.abspath(os.path.join(DATA_DIR, "logs"))


def get_log_file() -> str:
    """Restituisce il percorso del file di log corrente con cartella giornaliera e timestamp."""
    today = datetime.date.today().strftime("%Y-%m-%d")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    day_folder = os.path.join(LOG_ROOT, today)
    os.makedirs(day_folder, exist_ok=True)
    return os.path.join(day_folder, f"log_{timestamp}.txt")

LOG_FILE = get_log_file()

def append_to_log(message: str):
    """Scrive un messaggio dettagliato nel file di log corrente."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def cleanup_old_logs(days: int = 7):
    """Cancella le sottocartelle di log più vecchie di 'days' giorni."""
    if not os.path.exists(LOG_ROOT):
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    for folder in os.listdir(LOG_ROOT):
        folder_path = os.path.join(LOG_ROOT, folder)
        try:
            folder_date = datetime.datetime.strptime(folder, "%Y-%m-%d")
            if folder_date < cutoff:
                shutil.rmtree(folder_path)
                logging.info(f"Cartella log {folder_path} rimossa (più vecchia di {days} giorni).")
        except ValueError:
            continue

cleanup_old_logs()

def get_db_connection() -> pyodbc.Connection:
    """Apro la connessione al database SQL Server."""
    return pyodbc.connect(CONNECTION_STRING)

# --------------------------------------------------------------------------------
def fetch_clients() -> List[Dict]:
    query = """
       SELECT 
        RE_vw_TicketAnagraficheClienti.Ragione_sociale AS controparte_name,
        RE_vw_TicketAnagraficheClienti.Partita_iva AS controparte_piva,
        RE_vw_TicketAnagraficheClienti.Cod_fiscale AS controparte_cf,
        '' AS controparte_nation,
        RE_vw_TicketAnagraficheClienti.comune_sl AS controparte_city,
        RE_vw_TicketAnagraficheClienti.indirizzo_sl AS controparte_address,
        '' AS controparte_webpage,
        RE_vw_TicketAnagraficheClienti.mail AS controparte_mail,
        RE_vw_TicketAnagraficheClienti.NomePec AS controparte_pec,
        RE_vw_TicketAnagraficheClienti.telefono AS controparte_phone,
        TicketServizi.CodUffServizio AS workspace
    FROM RE_vw_TicketAnagraficheClienti
    LEFT JOIN (
        SELECT codcliente, ragione_sociale, coduffservizio
        FROM dbo.RE_vw_CGServizi
        GROUP BY codcliente, ragione_sociale, coduffservizio
    ) AS TicketServizi
        ON TicketServizi.CodCliente = RE_vw_TicketAnagraficheClienti.CodCliente
    WHERE TicketServizi.CodUffServizio IN (
        '001','002','003','021','025','030','032','033','037','038',
        '040','050','053','057','060','061','062','064','066','070',
        '071','073','074','075','080','085','090','099','111','112',
        '113','130','150'
    )
    AND RE_vw_TicketAnagraficheClienti.Data_Agg >= DATEADD(DAY, -4, CAST(GETDATE() AS DATE))
    """

    clients = []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, r)) for r in cursor.fetchall()]

        for c in rows:
            append_to_log(f"[RAW CLIENT] {json.dumps(c, ensure_ascii=False)}")
            piva = (c.get("controparte_piva") or "").strip()
            cf = (c.get("controparte_cf") or "").strip()
            coduff = str(c.get("workspace")) if c.get("workspace") else None

            if not coduff or coduff not in WORKSPACE_MAP:
                msg = f"Controparte {c.get('controparte_name')} scartata: workspace mancante o non mappato ({coduff})"
                logging.warning(msg)
                append_to_log(msg)
                continue
            workspace_id = WORKSPACE_MAP[coduff]

            if piva and piva != "00000000000":
                key = piva
            elif cf and not cf.startswith("000000"):
                key = cf
            else:
                msg = (f"Controparte {c.get('controparte_name')} scartata: "
                       f"P.IVA è {'NULL' if not piva else piva} e CF è fittizio ({cf}) → nessuna chiave logica valida")
                logging.warning(msg)
                append_to_log(msg)
                continue

            clients.append({
                "controparte_name": c.get("controparte_name"),
                "controparte_piva": piva,
                "controparte_cf": cf,
                "controparte_city": c.get("controparte_city"),
                "controparte_address": c.get("controparte_address"),
                "controparte_mail": c.get("controparte_mail"),
                "controparte_pec": c.get("controparte_pec"),
                "controparte_phone": c.get("controparte_phone"),
                "workspace_id": workspace_id,
                "workspace_logico": coduff,
                "key": key
            })

        logging.info(f"Recuperate {len(clients)} controparti valide dal database.")
        return clients

    except Exception as e:
        msg = f"Errore nel recupero controparti: {e}"
        logging.error(msg)
        append_to_log(msg)
        return []

# --------------------------------------------------------------------------------
def fetch_users() -> Dict[str, List[Dict]]:
    query = """
     SELECT 
        RE_vw_TicketAnagraficheClienti.Nome AS name,
        RE_vw_TicketAnagraficheClienti.Cognome AS surname,
        COALESCE(NULLIF(RE_vw_TicketAnagraficheClienti.EmailIndip, ''), RE_vw_TicketAnagraficheClienti.Mail) AS mail,
        COALESCE(NULLIF(RE_vw_TicketAnagraficheClienti.Num_cellulareIndip, ''), RE_vw_TicketAnagraficheClienti.Cellulare) AS phone,
        RE_vw_TicketAnagraficheClienti.CodFiscaleIndip AS cf,
        RE_vw_TicketAnagraficheClienti.Ragione_sociale AS controparte,
        RE_vw_TicketAnagraficheClienti.Partita_iva AS controparte_piva,
        RE_vw_TicketAnagraficheClienti.Cod_fiscale AS controparte_cf,
        TicketServizi.CodUffServizio AS workspace,
        CASE 
            WHEN UPPER(LTRIM(RTRIM(REPLACE(RE_vw_TicketAnagraficheClienti.Ragione_sociale,'  ',' ')))) =
                 UPPER(LTRIM(RTRIM(RE_vw_TicketAnagraficheClienti.Nome + ' ' + RE_vw_TicketAnagraficheClienti.Cognome)))
              OR UPPER(LTRIM(RTRIM(REPLACE(RE_vw_TicketAnagraficheClienti.Ragione_sociale,'  ',' ')))) =
                 UPPER(LTRIM(RTRIM(RE_vw_TicketAnagraficheClienti.Cognome + ' ' + RE_vw_TicketAnagraficheClienti.Nome)))
            THEN 'natural'
            ELSE 'external'
        END AS user_type
    FROM RE_vw_TicketAnagraficheClienti
    LEFT JOIN (
        SELECT codcliente, ragione_sociale, coduffservizio
        FROM dbo.RE_vw_CGServizi
        GROUP BY codcliente, ragione_sociale, coduffservizio
    ) AS TicketServizi
        ON TicketServizi.CodCliente = RE_vw_TicketAnagraficheClienti.CodCliente
    WHERE RE_vw_TicketAnagraficheClienti.Nome IS NOT NULL 
      AND RE_vw_TicketAnagraficheClienti.Cognome IS NOT NULL
      AND RE_vw_TicketAnagraficheClienti.mail IS NOT NULL
      AND TicketServizi.CodUffServizio IN (
            '001','002','003','021','025','030','032','033','037','038',
            '040','050','053','057','060','061','062','064','066','070',
            '071','073','074','075','080','085','090','099','111','112',
            '113','130','150'
        )
      AND RE_vw_TicketAnagraficheClienti.DataAggIndip >= DATEADD(DAY, -4, CAST(GETDATE() AS DATE))
    """

    externals, naturals = [], []
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, r)) for r in cursor.fetchall()]

        for u in rows:
            append_to_log(f"[RAW USER] {json.dumps(u, ensure_ascii=False)}")

            name = (u.get("name") or "").strip()
            surname = (u.get("surname") or "").strip()
            mail = (u.get("mail") or "").strip().lower()
            phone = (u.get("phone") or "").strip()
            cf = (u.get("cf") or "").strip()
            coduff = str(u.get("workspace")) if u.get("workspace") else None

            piva = (u.get("controparte_piva") or "").strip()
            cf_cont = (u.get("controparte_cf") or "").strip()

            if piva and piva != "00000000000":
                key_logica = piva
            elif cf_cont and not cf_cont.startswith("000000"):
                key_logica = cf_cont
            else:
                key_logica = None

            if not mail:
                msg = f"Firmatario {name} {surname} scartato: mail mancante"
                logging.warning(msg)
                append_to_log(msg)
                continue

            if not coduff or coduff not in WORKSPACE_MAP:
                msg = f"Firmatario {name} {surname} scartato: workspace mancante o non mappato ({coduff})"
                logging.warning(msg)
                append_to_log(msg)
                continue

            workspace_id = WORKSPACE_MAP[coduff]
            cont_keys = [key_logica] if key_logica else []

            if u.get("user_type") == "natural":
                existing = [n for n in naturals if n["cf"] == cf or n["mail"] == mail]
                if existing:
                    msg = f"Firmatario {name} {surname} appare su più workspace → trattato come external"
                    logging.warning(msg)
                    append_to_log(msg)
                    externals.append({
                        "mail": mail,
                        "name": name,
                        "surname": surname,
                        "phone": phone,
                        "cf": cf,
                        "controparti_keys": cont_keys,
                        "workspace_id": workspace_id,
                        "workspace_logico": coduff,
                        "type": "external"
                    })
                else:
                    naturals.append({
                        "mail": mail,
                        "name": name,
                        "surname": surname,
                        "phone": phone,
                        "cf": cf,
                        "controparti_keys": [key_logica] if key_logica else [],
                        "workspace_id": workspace_id,
                        "workspace_logico": coduff,
                        "type": "natural"
                    })
            else:
                externals.append({
                    "mail": mail,
                    "name": name,
                    "surname": surname,
                    "phone": phone,
                    "cf": cf,
                    "controparti_keys": cont_keys,
                    "workspace_id": workspace_id,
                    "workspace_logico": coduff,
                    "type": "external"
                })

        logging.info(f"Recuperati {len(externals)} external e {len(naturals)} natural dal database.")
        append_to_log(f"Recuperati {len(externals)} external e {len(naturals)} natural dal database.")
        return {"externals": externals, "naturals": naturals}

    except Exception as e:
        msg = f"Errore nel recupero firmatari: {e}"
        logging.error(msg)
        append_to_log(msg)
        return {"externals": [], "naturals": []}