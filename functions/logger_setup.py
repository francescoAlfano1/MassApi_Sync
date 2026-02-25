import logging
import os
from datetime import datetime, timedelta

LOG_RETENTION_DAYS = 30

def setup_logging(log_folder: str="log_MAIN_USER_SYNC"):
    os.makedirs(log_folder, exist_ok=True)
    log_file = os.path.join(log_folder, f"{datetime.utcnow().strftime('%Y-%m-%d')}_sync.log")

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ],
        force=True   # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    )

    logging.info(f"Logger inizializzato. File di log: {log_file}")
    print("SETUP LOGGING CHIAMATO DA:", __import__("inspect").stack()[1].filename)

    cutoff = datetime.utcnow() - timedelta(days=LOG_RETENTION_DAYS)
    for fname in os.listdir(log_folder):
        fpath = os.path.join(log_folder, fname)
        try:
            if os.path.isfile(fpath):
                date_str = fname.split("_")[0]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    os.remove(fpath)
                    logging.info(f"Log vecchio rimosso: {fname}")
        except Exception as e:
            logging.warning(f"Impossibile rimuovere {fname}: {e}")
